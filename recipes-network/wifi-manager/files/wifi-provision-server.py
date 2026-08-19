#!/usr/bin/env python3
"""
SpinyOS WiFi Provisioning Server
Runs in AP mode (192.168.73.1) to accept WiFi credentials from the desktop app.

Endpoints:
  GET  /api/wifi/status       – device state: first_setup | wifi_error | ok
  GET  /api/system/info       – hostname, device, firmware version
  POST /api/wifi/configure    – save WiFi credentials and restart wifi-manager
  POST /api/wifi/forget       – clear saved credentials, back to first_setup
"""

import http.server
import json
import os
import re
import subprocess
import sys
import time
import traceback
import urllib.parse

PORT        = int(sys.argv[1]) if len(sys.argv) > 1 else 7373
BIND_ADDR   = "0.0.0.0"
STATE_FILE  = "/etc/spiny/wifi-state"
CRED_FILE   = "/etc/spiny/wifi-credentials"
IDENTITY_FILE = "/run/spiny/device-id"  # written by device-identity.service
READY_ACK_FILE = "/run/spiny/ready-ack"
LOG_FILE = "/var/log/wifi-provision.log"

# Allowed characters for SSID and PSK — reject anything shell-dangerous
_SAFE_RE = re.compile(r'^[\x20-\x7E]{1,64}$')
_CALLBACK_URL_RE = re.compile(r'^https?://[\x21-\x7E]{1,500}$')


def _log(message: str) -> None:
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except OSError:
        pass


def _get_device_ips() -> list:
    """Return all non-loopback IPv4 addresses of this device."""
    try:
        out = subprocess.getoutput("ip -4 addr show scope global")
        return [p.split()[1].split('/')[0]
                for p in out.splitlines()
                if p.strip().startswith("inet ") and "127." not in p]
    except Exception:
        return []


def _read_device_id() -> str:
    """Return the unique SPINY_DEVICE_ID; fallback to '00000000'."""
    for path in (IDENTITY_FILE, "/etc/spiny/device-id"):
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("SPINY_DEVICE_ID="):
                        return line.split("=", 1)[1].strip()
        except OSError:
            pass
    return "00000000"


def _read_state() -> dict:
    state = {
        "CONFIGURED": "false",
        "LAST_ERROR": "",
        "STATUS": "first_setup",
        "TARGET_SSID": "",
        "CALLBACK_URL": "",
        "READY_NOTIFIED": "false",
    }
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    state[k.strip()] = v.strip()
    return state


def _write_state(
    configured: bool,
    last_error: str = "",
    status: str = "first_setup",
    target_ssid: str = "",
    callback_url: str = "",
    ready_notified: bool = False,
) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        f.write(f"CONFIGURED={'true' if configured else 'false'}\n")
        f.write(f"LAST_ERROR='{last_error}'\n")
        f.write(f"STATUS='{status}'\n")
        f.write(f"TARGET_SSID='{target_ssid}'\n")
        f.write(f"CALLBACK_URL='{callback_url}'\n")
        f.write(f"READY_NOTIFIED={'true' if ready_notified else 'false'}\n")
    os.chmod(STATE_FILE, 0o600)


def _write_credentials(
    ssid: str,
    password: str,
    identity: str = "",
    key_mgmt: str = "",
    eap: str = "",
    phase2: str = "",
) -> None:
    os.makedirs(os.path.dirname(CRED_FILE), exist_ok=True)
    with open(CRED_FILE, "w") as f:
        json.dump(
            {
                "WIFI_SSID": ssid,
                "WIFI_PASSWORD": password,
                "WIFI_IDENTITY": identity,
                "WIFI_KEY_MGMT": key_mgmt,
                "WIFI_EAP": eap,
                "WIFI_PHASE2": phase2,
            },
            f,
        )
    os.chmod(CRED_FILE, 0o600)


def _verify_tcp_connection(server_address: str, port: int, device_id: str, auth_token: str) -> tuple:
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        return False, "mqtt_library_missing"

    host = server_address
    if "://" in server_address:
        parsed = urllib.parse.urlparse(server_address)
        host = parsed.hostname or parsed.path

    handshake_status = {"status": None}
    client = mqtt.Client()

    # 1. Parse auth_token for Username/Password authentication
    username = None
    password = auth_token
    if ":" in auth_token:
        username, password = auth_token.split(":", 1)

    if username is not None or password:
        client.username_pw_set(username, password)

    # 2. Check and configure TLS/SSL
    is_tls = False
    if port in (8883, 8884) or server_address.startswith("ssl://") or server_address.startswith("mqtts://") or "hivemq.cloud" in server_address:
        is_tls = True

    if is_tls:
        import ssl
        try:
            client.tls_set_context(ssl._create_unverified_context())
        except AttributeError:
            client.tls_set()

    # 3. Setup callbacks
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(f"spiny/devices/{device_id}/handshake_response", qos=1)
            payload = json.dumps({
                "type": "handshake_request",
                "device_id": device_id,
                "token": password  # Send only the parsed password/token part
            })
            client.publish(f"spiny/devices/{device_id}/handshake", payload, qos=1)
        else:
            handshake_status["status"] = f"connection_failed_rc_{rc}"

    def on_message(client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            if data.get("type") == "handshake_approve" and data.get("status") == "approved":
                handshake_status["status"] = "approved"
            else:
                handshake_status["status"] = "rejected"
        except Exception:
            handshake_status["status"] = "invalid_payload"

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(host, port, keepalive=10)
    except Exception as e:
        return False, f"connection_failed: {str(e)}"

    # Run loop for up to 10 seconds
    start_time = time.time()
    while time.time() - start_time < 10.0:
        client.loop(timeout=0.2)
        if handshake_status["status"] is not None:
            break
        time.sleep(0.1)

    client.disconnect()

    if handshake_status["status"] == "approved":
        return True, "Handshake successful"
    else:
        return False, handshake_status["status"] or "timeout"


class ProvisionHandler(http.server.BaseHTTPRequestHandler):
    # Silence default access log; errors still go to stderr → journal
    def log_message(self, fmt, *args):  # noqa: N802
        pass

    # ------------------------------------------------------------------ helpers
    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")

    def _send_json(self, code: int, data: dict) -> None:
        body = (json.dumps(data) + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _handle_exception(self, action: str) -> None:
        _log(f"request error during {action}:\n{traceback.format_exc()}")
        try:
            self._send_json(500, {"error": "internal_server_error"})
        except BrokenPipeError:
            pass

    def _read_json_body(self, max_bytes: int = 4096):
        length = int(self.headers.get("Content-Length", 0))
        if length > max_bytes:
            return None, "payload_too_large"
        raw = self.rfile.read(length)
        try:
            return json.loads(raw), None
        except (ValueError, UnicodeDecodeError):
            return None, "invalid_json"

    # ------------------------------------------------------------------ GET
    def do_GET(self):  # noqa: N802
        try:
            _log(f"GET {self.path}")
            if self.path == "/api/wifi/status":
                state = _read_state()
                configured  = state.get("CONFIGURED", "false") == "true"
                last_error  = state.get("LAST_ERROR", "")
                status = state.get("STATUS", "first_setup")
                self._send_json(200, {
                    "status":       status,
                    "configured":   configured,
                    "last_error":   last_error,
                    "target_ssid":  state.get("TARGET_SSID", ""),
                    "ready_notified": state.get("READY_NOTIFIED", "false") == "true",
                    "device_ips":   _get_device_ips(),
                })

            elif self.path == "/api/system/info":
                hostname = subprocess.getoutput("hostname").strip()
                device_id = _read_device_id()
                version  = "1.0"
                try:
                    with open("/etc/os-release") as f:
                        for line in f:
                            if line.startswith("VERSION_ID="):
                                version = line.split("=", 1)[1].strip().strip('"')
                                break
                except OSError:
                    pass
                self._send_json(200, {
                    "hostname":   hostname,
                    "device":     "SpinyOS",
                    "device_id":  device_id,
                    "version":    version,
                    "device_ips": _get_device_ips(),
                })

            elif self.path == "/api/tcp/status":
                tcp_config_path = "/etc/spiny/tcp_config.json"
                tcp_state_path = "/etc/spiny/tcp-state.json"
                
                config = {}
                if os.path.exists(tcp_config_path):
                    try:
                        with open(tcp_config_path) as f:
                            config = json.load(f)
                    except Exception:
                        pass
                
                state = {}
                if os.path.exists(tcp_state_path):
                    try:
                        with open(tcp_state_path) as f:
                            state = json.load(f)
                    except Exception:
                        pass
                
                self._send_json(200, {
                    "configured": bool(config),
                    "active_status": config.get("active_status", False),
                    "server_address": config.get("server_address", ""),
                    "port": config.get("port", 0),
                    "device_id": config.get("device_id", ""),
                    "connection_status": state.get("status", "disconnected"),
                    "last_error": state.get("last_error", "")
                })

            else:
                self._send_json(404, {"error": "not_found"})
        except Exception:
            self._handle_exception("GET")

    # ------------------------------------------------------------------ POST
    def do_POST(self):  # noqa: N802
        try:
            _log(f"POST {self.path}")
            if self.path == "/api/wifi/configure":
                data, err = self._read_json_body()
                if err:
                    self._send_json(400, {"error": err})
                    return

                ssid = str(data.get("ssid", "")).strip()
                password = str(data.get("password", "")).strip()
                identity = str(data.get("identity", "")).strip()
                key_mgmt = str(data.get("key_mgmt", "")).strip().upper()
                eap = str(data.get("eap", "")).strip().upper()
                phase2 = str(data.get("phase2", "")).strip()
                callback_url = str(data.get("callback_url", "")).strip()

                if not ssid or not password:
                    self._send_json(400, {"error": "ssid_and_password_required"})
                    return

                # Input validation — reject shell-dangerous characters and too-long strings
                fields = [ssid, password]
                if identity:
                    fields.append(identity)
                if key_mgmt:
                    fields.append(key_mgmt)
                if eap:
                    fields.append(eap)
                if phase2:
                    fields.append(phase2)
                if any(not _SAFE_RE.match(value) for value in fields):
                    self._send_json(400, {"error": "invalid_characters"})
                    return
                if callback_url and not _CALLBACK_URL_RE.match(callback_url):
                    self._send_json(400, {"error": "invalid_callback_url"})
                    return

                # Enterprise Wi-Fi: identity geldiyse WPA-EAP varsay
                if identity:
                    if not key_mgmt:
                        key_mgmt = "WPA-EAP"
                    if not eap:
                        eap = "PEAP"
                    if not phase2:
                        phase2 = "auth=MSCHAPV2"
                else:
                    key_mgmt = "WPA-PSK"
                    eap = ""
                    phase2 = ""

                _write_credentials(ssid, password, identity, key_mgmt, eap, phase2)
                _write_state(
                    configured=True,
                    last_error="",
                    status="credentials_received",
                    target_ssid=ssid,
                    callback_url=callback_url,
                    ready_notified=False,
                )

                self._send_json(200, {
                    "status":  "credentials_received",
                    "target_ssid": ssid,
                    "callback_registered": bool(callback_url),
                    "message": (
                        "Credentials received. Switch the app host to the selected "
                        "Wi-Fi and wait for device status to become connected."
                    ),
                })

                # Restart wifi-manager so it picks up the new credentials.
                # Use Popen (non-blocking) — response is already sent.
                subprocess.Popen(
                    ["/bin/sh", "-c", "sleep 1; systemctl restart wifi-manager"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            elif self.path == "/api/wifi/forget":
                # Clear saved credentials — puts device back into first_setup state
                try:
                    os.remove(CRED_FILE)
                except FileNotFoundError:
                    pass
                _write_state(configured=False, last_error="", status="first_setup", target_ssid="")
                self._send_json(200, {"status": "forgotten"})

                subprocess.Popen(
                    ["systemctl", "restart", "wifi-manager"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            elif self.path == "/api/provision/ack":
                os.makedirs(os.path.dirname(READY_ACK_FILE), exist_ok=True)
                with open(READY_ACK_FILE, "w") as f:
                    f.write("ack\n")

                state = _read_state()
                _write_state(
                    configured=state.get("CONFIGURED", "false") == "true",
                    last_error=state.get("LAST_ERROR", ""),
                    status=state.get("STATUS", "connected"),
                    target_ssid=state.get("TARGET_SSID", ""),
                    callback_url=state.get("CALLBACK_URL", ""),
                    ready_notified=True,
                )
                self._send_json(200, {"status": "acknowledged"})

            elif self.path == "/api/tcp/configure":
                data, err = self._read_json_body()
                if err:
                    self._send_json(400, {"error": err})
                    return

                server_address = str(data.get("server_address", "")).strip()
                port = data.get("port")
                device_id = str(data.get("device_id", "")).strip()
                auth_token = str(data.get("auth_token", "")).strip()
                active_status = data.get("active_status", True)

                if not server_address or not port or not device_id or not auth_token:
                    self._send_json(400, {"error": "missing_required_fields"})
                    return

                try:
                    port = int(port)
                except ValueError:
                    self._send_json(400, {"error": "invalid_port"})
                    return

                # If active_status is true, verify connection
                if active_status:
                    _log("Verifying TCP connection...")
                    success, detail = _verify_tcp_connection(server_address, port, device_id, auth_token)
                    if not success:
                        self._send_json(400, {"error": "handshake_failed", "details": detail})
                        return

                # Connection verified! Save config
                tcp_config_path = "/etc/spiny/tcp_config.json"
                os.makedirs(os.path.dirname(tcp_config_path), exist_ok=True)
                with open(tcp_config_path, "w") as f:
                    json.dump({
                        "server_address": server_address,
                        "port": port,
                        "device_id": device_id,
                        "auth_token": auth_token,
                        "active_status": active_status
                    }, f)
                os.chmod(tcp_config_path, 0o600)

                # Initialize connection status file
                tcp_state_path = "/etc/spiny/tcp-state.json"
                with open(tcp_state_path, "w") as f:
                    json.dump({
                        "status": "connected" if active_status else "disabled",
                        "last_error": ""
                    }, f)
                os.chmod(tcp_state_path, 0o600)

                self._send_json(200, {
                    "status": "configured",
                    "active_status": active_status,
                    "message": "TCP/Broker connection verified and configured successfully."
                })

                # Restart services to apply new config
                subprocess.Popen(
                    ["/bin/sh", "-c", "sleep 1; systemctl restart wifi-manager; systemctl restart device-ingest"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            else:
                self._send_json(404, {"error": "not_found"})
        except Exception:
            self._handle_exception("POST")

    # Handle pre-flight CORS (Electron apps may send OPTIONS)
    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()


if __name__ == "__main__":
    _log(f"wifi-provision-server starting on {BIND_ADDR}:{PORT}")
    server = http.server.HTTPServer((BIND_ADDR, PORT), ProvisionHandler)
    server.serve_forever()
