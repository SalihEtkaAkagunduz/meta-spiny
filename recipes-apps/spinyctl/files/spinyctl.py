#!/usr/bin/env python3
import asyncio
import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.parse
import uuid
from pathlib import Path


DEVICE_ID_FILES = ["/run/spiny/device-id", "/etc/spiny/device-id"]
WIFI_STATE_FILE = "/etc/spiny/wifi-state"
CUSTOM_COMMAND_DIR = "/usr/libexec/spinyctl/commands"
ORCHESTRATOR_POLICY_FILE = "/etc/spiny/orchestrator-policy.json"
ORCHESTRATOR_MANIFEST_FILE = "/etc/spiny/orchestrator-manifest.json"
ORCHESTRATOR_AUTH_FILE = "/etc/spiny/orchestrator-auth.json"
ORCHESTRATOR_WS_URL = "ws://127.0.0.1:8765"
SAFE_SERVICE_RE = re.compile(r"^[A-Za-z0-9_.@-]+(?:\.service)?$")


def print_output(payload, as_json=False):
    if as_json:
        print(json.dumps(payload, ensure_ascii=True))
    elif isinstance(payload, str):
        print(payload)
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=True))


def parse_shell_kv_file(path):
    result = {}
    if not os.path.exists(path):
        return result
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            result[key] = value.strip().strip("\"").strip("'")
    return result


def run_command(command):
    completed = subprocess.run(command, capture_output=True, text=True)
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def read_device_identity():
    for path in DEVICE_ID_FILES:
        state = parse_shell_kv_file(path)
        if "SPINY_DEVICE_ID" in state:
            return state
    return {"SPINY_DEVICE_ID": "00000000", "SPINY_HOSTNAME": socket.gethostname()}


def get_ip_for_interface(interface):
    result = run_command(["ip", "-4", "addr", "show", "dev", interface])
    if not result["ok"]:
        return ""
    for line in result["stdout"].splitlines():
        line = line.strip()
        if line.startswith("inet "):
            return line.split()[1].split("/", 1)[0]
    return ""


def get_device_info(as_json):
    identity = read_device_identity()
    os_release = parse_shell_kv_file("/etc/os-release")
    payload = {
        "device": os_release.get("NAME", "SpinyOS"),
        "version": os_release.get("VERSION_ID", ""),
        "hostname": identity.get("SPINY_HOSTNAME", socket.gethostname()),
        "device_id": identity.get("SPINY_DEVICE_ID", "00000000"),
        "mdns": f"{identity.get('SPINY_HOSTNAME', socket.gethostname())}.local",
        "wlan0_ip": get_ip_for_interface("wlan0"),
        "eth0_ip": get_ip_for_interface("eth0"),
    }
    print_output(payload, as_json)
    return 0


def get_wifi_status(as_json):
    state = parse_shell_kv_file(WIFI_STATE_FILE)
    wlan_status = run_command(["wpa_cli", "-i", "wlan0", "status"]) if shutil_which("wpa_cli") else {"ok": False, "stdout": "", "stderr": "wpa_cli not found"}
    payload = {
        "status": state.get("STATUS", "unknown"),
        "configured": state.get("CONFIGURED", "false") == "true",
        "last_error": state.get("LAST_ERROR", ""),
        "target_ssid": state.get("TARGET_SSID", ""),
        "ready_notified": state.get("READY_NOTIFIED", "false") == "true",
        "wlan0_ip": get_ip_for_interface("wlan0"),
        "eth0_ip": get_ip_for_interface("eth0"),
        "wpa_cli": wlan_status["stdout"],
    }
    print_output(payload, as_json)
    return 0


def shutil_which(binary):
    for directory in os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin").split(":"):
        candidate = os.path.join(directory, binary)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ""


def load_orchestrator_tokens(auth_file=ORCHESTRATOR_AUTH_FILE):
    if not os.path.exists(auth_file):
        return {}

    with open(auth_file, encoding="utf-8") as handle:
        try:
            parsed = json.load(handle)
        except json.JSONDecodeError:
            return {}

    tokens = parsed.get("tokens", {}) if isinstance(parsed, dict) else {}
    if not isinstance(tokens, dict):
        return {}

    return {str(token): str(role) for token, role in tokens.items() if isinstance(token, str)}


def pick_orchestrator_token(required_role, auth_file=ORCHESTRATOR_AUTH_FILE):
    tokens = load_orchestrator_tokens(auth_file=auth_file)
    if not tokens:
        return ""

    preferred_roles = {
        "viewer": ["viewer", "operator", "admin"],
        "operator": ["operator", "admin"],
        "admin": ["admin"],
    }.get(required_role, ["admin", "operator", "viewer"])

    for role in preferred_roles:
        for token, token_role in tokens.items():
            if token_role == role:
                return token
    return ""


async def orchestrator_ws_command(ws_url, token, action, payload, timeout_sec):
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("python websockets module not installed") from exc

    url = ws_url
    if token:
        parsed = urllib.parse.urlparse(ws_url)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query.append(("token", token))
        parsed = parsed._replace(query=urllib.parse.urlencode(query))
        url = urllib.parse.urlunparse(parsed)

    request_id = str(uuid.uuid4())
    request = {
        "v": 1,
        "type": "command",
        "action": action,
        "requestId": request_id,
        "payload": payload,
    }

    async with websockets.connect(url, max_size=None, ping_interval=20, ping_timeout=20) as websocket:
        await websocket.send(json.dumps(request, separators=(",", ":")))

        while True:
            raw = await asyncio.wait_for(websocket.recv(), timeout=max(1, timeout_sec))
            message = json.loads(raw)
            msg_request_id = message.get("requestId")

            if msg_request_id is None and message.get("action") == "connect":
                return message

            if msg_request_id != request_id:
                continue

            if message.get("type") == "ack":
                continue

            return message


async def orchestrator_ws_stream_watch(ws_url, token, node_id, fields, rate_hz, seconds, timeout_sec):
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("python websockets module not installed") from exc

    url = ws_url
    if token:
        parsed = urllib.parse.urlparse(ws_url)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query.append(("token", token))
        parsed = parsed._replace(query=urllib.parse.urlencode(query))
        url = urllib.parse.urlunparse(parsed)

    subscribe_request_id = str(uuid.uuid4())
    unsubscribe_request_id = str(uuid.uuid4())
    subscribe_request = {
        "v": 1,
        "type": "command",
        "action": "stream.subscribe",
        "requestId": subscribe_request_id,
        "payload": {
            "nodeId": node_id,
            "fields": fields,
            "rateHz": rate_hz,
        },
    }

    async with websockets.connect(url, max_size=None, ping_interval=20, ping_timeout=20) as websocket:
        await websocket.send(json.dumps(subscribe_request, separators=(",", ":")))

        subscription_id = ""
        started = time.monotonic()
        samples = []

        while True:
            now = time.monotonic()
            if subscription_id and now - started >= max(1, seconds):
                break

            wait_timeout = max(1.0, min(float(timeout_sec), 2.0))
            raw = await asyncio.wait_for(websocket.recv(), timeout=wait_timeout)
            message = json.loads(raw)

            if message.get("type") == "error" and message.get("requestId") == subscribe_request_id:
                return {
                    "ok": False,
                    "type": "error",
                    "action": message.get("action"),
                    "requestId": message.get("requestId"),
                    "payload": message.get("payload", {}),
                    "samples": [],
                }

            if message.get("requestId") == subscribe_request_id and message.get("type") == "event":
                subscription_id = str(message.get("payload", {}).get("subscriptionId", ""))
                continue

            if message.get("action") == "stream.data":
                payload = message.get("payload", {})
                if subscription_id and payload.get("subscriptionId") == subscription_id:
                    samples.append(payload)

        if subscription_id:
            unsubscribe_request = {
                "v": 1,
                "type": "command",
                "action": "stream.unsubscribe",
                "requestId": unsubscribe_request_id,
                "payload": {
                    "subscriptionId": subscription_id,
                },
            }
            await websocket.send(json.dumps(unsubscribe_request, separators=(",", ":")))

            unsubscribe_deadline = time.monotonic() + max(2, int(timeout_sec))
            while time.monotonic() < unsubscribe_deadline:
                raw = await asyncio.wait_for(websocket.recv(), timeout=1)
                message = json.loads(raw)
                if message.get("requestId") == unsubscribe_request_id:
                    break

        return {
            "ok": True,
            "type": "event",
            "action": "stream.watch",
            "requestId": subscribe_request_id,
            "payload": {
                "nodeId": node_id,
                "subscriptionId": subscription_id,
                "sampleCount": len(samples),
                "samples": samples,
            },
        }


def normalize_service_name(name):
    if not SAFE_SERVICE_RE.match(name):
        raise ValueError("invalid_service_name")
    if not name.endswith(".service"):
        return f"{name}.service"
    return name


def handle_service(args):
    try:
        service_name = normalize_service_name(args.name)
    except ValueError as exc:
        print_output({"ok": False, "error": str(exc)}, args.json)
        return 1

    if args.action == "status":
        active = run_command(["systemctl", "is-active", service_name])
        enabled = run_command(["systemctl", "is-enabled", service_name])
        payload = {
            "ok": True,
            "service": service_name,
            "active": active["stdout"],
            "enabled": enabled["stdout"],
        }
        print_output(payload, args.json)
        return 0

    result = run_command(["systemctl", args.action, service_name])
    payload = {
        "ok": result["ok"],
        "service": service_name,
        "action": args.action,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }
    print_output(payload, args.json)
    return 0 if result["ok"] else 1


def handle_telemetry(args):
    service_args = argparse.Namespace(name="device-ingest", action=args.action, json=args.json)
    return handle_service(service_args)


def handle_orchestrator(args):
    if args.subcommand == "service":
        service_args = argparse.Namespace(name="spiny-orchestrator", action=args.action, json=args.json)
        return handle_service(service_args)

    if args.subcommand == "policy":
        policy = {}
        if os.path.exists(ORCHESTRATOR_POLICY_FILE):
            with open(ORCHESTRATOR_POLICY_FILE, encoding="utf-8") as handle:
                try:
                    policy = json.load(handle)
                except json.JSONDecodeError:
                    policy = {"error": "invalid_policy_json"}
        else:
            policy = {"error": "policy_not_found", "path": ORCHESTRATOR_POLICY_FILE}
        print_output(policy, args.json)
        return 0

    if args.subcommand == "user":
        token = args.token or pick_orchestrator_token("viewer", auth_file=args.auth_file)
        if not token:
            print_output(
                {
                    "ok": False,
                    "error": "token_not_found",
                    "message": f"Provide --token or configure {args.auth_file}",
                },
                args.json,
            )
            return 1

        try:
            message = asyncio.run(
                orchestrator_ws_command(
                    ws_url=args.url,
                    token=token,
                    action="user.info",
                    payload={},
                    timeout_sec=args.timeout,
                )
            )
        except (OSError, RuntimeError, json.JSONDecodeError, TimeoutError) as exc:
            print_output(
                {
                    "ok": False,
                    "error": "orchestrator_unreachable",
                    "message": str(exc),
                    "url": args.url,
                },
                args.json,
            )
            return 1

        output = {
            "ok": message.get("type") != "error",
            "type": message.get("type"),
            "action": message.get("action"),
            "requestId": message.get("requestId"),
            "payload": message.get("payload", {}),
        }
        print_output(output, args.json)
        return 0 if output["ok"] else 1

    if args.subcommand == "nodes":
        manifest_path = args.manifest or ORCHESTRATOR_MANIFEST_FILE
        manifest = {}
        ok = True

        if os.path.exists(manifest_path):
            with open(manifest_path, encoding="utf-8") as handle:
                try:
                    manifest = json.load(handle)
                except json.JSONDecodeError:
                    manifest = {"error": "invalid_manifest_json"}
                    ok = False
        else:
            manifest = {"error": "manifest_not_found", "path": manifest_path}
            ok = False

        nodes = manifest.get("nodes", {}) if isinstance(manifest, dict) else {}
        if not isinstance(nodes, dict):
            nodes = {}
            ok = False

        if args.details:
            node_payload = {name: nodes.get(name, {}) for name in sorted(nodes.keys())}
        else:
            node_payload = sorted(list(nodes.keys()))

        payload = {
            "ok": ok,
            "manifest": manifest_path,
            "nodeCount": len(nodes),
            "nodes": node_payload,
            "raw": manifest,
        }
        print_output(payload, args.json)
        return 0 if ok else 1

    if args.subcommand == "node":
        action_map = {
            "list": "node.list",
            "status": "node.status",
            "start": "node.start",
            "stop": "node.stop",
            "restart": "node.restart",
        }
        ws_action = action_map[args.action]

        if args.action in {"start", "stop", "restart"} and not args.node_id:
            print_output(
                {
                    "ok": False,
                    "error": "node_id_required",
                    "message": "node id is required for start/stop/restart",
                },
                args.json,
            )
            return 1

        required_role = "viewer" if args.action in {"list", "status"} else "operator"
        token = args.token or pick_orchestrator_token(required_role, auth_file=args.auth_file)
        if not token:
            print_output(
                {
                    "ok": False,
                    "error": "token_not_found",
                    "message": f"Provide --token or configure {args.auth_file}",
                },
                args.json,
            )
            return 1

        payload = {}
        if args.action in {"status", "start", "stop", "restart"} and args.node_id:
            payload["nodeId"] = args.node_id

        if args.action == "stop":
            payload["graceSec"] = max(1, int(args.grace_sec))

        try:
            message = asyncio.run(
                orchestrator_ws_command(
                    ws_url=args.url,
                    token=token,
                    action=ws_action,
                    payload=payload,
                    timeout_sec=args.timeout,
                )
            )
        except (OSError, RuntimeError, json.JSONDecodeError, TimeoutError) as exc:
            print_output(
                {
                    "ok": False,
                    "error": "orchestrator_unreachable",
                    "message": str(exc),
                    "url": args.url,
                },
                args.json,
            )
            return 1

        output = {
            "ok": message.get("type") != "error",
            "type": message.get("type"),
            "action": message.get("action"),
            "requestId": message.get("requestId"),
            "payload": message.get("payload", {}),
        }
        print_output(output, args.json)
        return 0 if output["ok"] else 1

    if args.subcommand == "graph":
        action_map = {
            "snapshot": "graph.snapshot",
        }
        ws_action = action_map[args.action]

        token = args.token or pick_orchestrator_token("viewer", auth_file=args.auth_file)
        if not token:
            print_output(
                {
                    "ok": False,
                    "error": "token_not_found",
                    "message": f"Provide --token or configure {args.auth_file}",
                },
                args.json,
            )
            return 1

        try:
            message = asyncio.run(
                orchestrator_ws_command(
                    ws_url=args.url,
                    token=token,
                    action=ws_action,
                    payload={},
                    timeout_sec=args.timeout,
                )
            )
        except (OSError, RuntimeError, json.JSONDecodeError, TimeoutError) as exc:
            print_output(
                {
                    "ok": False,
                    "error": "orchestrator_unreachable",
                    "message": str(exc),
                    "url": args.url,
                },
                args.json,
            )
            return 1

        output = {
            "ok": message.get("type") != "error",
            "type": message.get("type"),
            "action": message.get("action"),
            "requestId": message.get("requestId"),
            "payload": message.get("payload", {}),
        }
        print_output(output, args.json)
        return 0 if output["ok"] else 1

    if args.subcommand == "io":
        token = args.token or pick_orchestrator_token("viewer", auth_file=args.auth_file)
        if not token:
            print_output(
                {
                    "ok": False,
                    "error": "token_not_found",
                    "message": f"Provide --token or configure {args.auth_file}",
                },
                args.json,
            )
            return 1

        payload = {"nodeName": args.node_name}

        try:
            message = asyncio.run(
                orchestrator_ws_command(
                    ws_url=args.url,
                    token=token,
                    action="node.io.inspect",
                    payload=payload,
                    timeout_sec=args.timeout,
                )
            )
        except (OSError, RuntimeError, json.JSONDecodeError, TimeoutError) as exc:
            print_output(
                {
                    "ok": False,
                    "error": "orchestrator_unreachable",
                    "message": str(exc),
                    "url": args.url,
                },
                args.json,
            )
            return 1

        output = {
            "ok": message.get("type") != "error",
            "type": message.get("type"),
            "action": message.get("action"),
            "requestId": message.get("requestId"),
            "payload": message.get("payload", {}),
        }
        print_output(output, args.json)
        return 0 if output["ok"] else 1

    if args.subcommand == "capture":
        action_map = {
            "window": "capture.window",
        }
        ws_action = action_map[args.action]

        token = args.token or pick_orchestrator_token("viewer", auth_file=args.auth_file)
        if not token:
            print_output(
                {
                    "ok": False,
                    "error": "token_not_found",
                    "message": f"Provide --token or configure {args.auth_file}",
                },
                args.json,
            )
            return 1

        payload = {
            "durationSec": max(1, int(args.duration_sec)),
            "sampleIntervalSec": max(1, int(args.sample_interval_sec)),
            "nodeNames": list(args.node_name or []),
        }

        try:
            message = asyncio.run(
                orchestrator_ws_command(
                    ws_url=args.url,
                    token=token,
                    action=ws_action,
                    payload=payload,
                    timeout_sec=args.timeout,
                )
            )
        except (OSError, RuntimeError, json.JSONDecodeError, TimeoutError) as exc:
            print_output(
                {
                    "ok": False,
                    "error": "orchestrator_unreachable",
                    "message": str(exc),
                    "url": args.url,
                },
                args.json,
            )
            return 1

        output = {
            "ok": message.get("type") != "error",
            "type": message.get("type"),
            "action": message.get("action"),
            "requestId": message.get("requestId"),
            "payload": message.get("payload", {}),
        }
        print_output(output, args.json)
        return 0 if output["ok"] else 1

    if args.subcommand == "stream":
        if args.action != "watch":
            print_output({"ok": False, "error": "invalid_stream_action"}, args.json)
            return 1

        token = args.token or pick_orchestrator_token("viewer", auth_file=args.auth_file)
        if not token:
            print_output(
                {
                    "ok": False,
                    "error": "token_not_found",
                    "message": f"Provide --token or configure {args.auth_file}",
                },
                args.json,
            )
            return 1

        fields = list(args.field or [])
        try:
            message = asyncio.run(
                orchestrator_ws_stream_watch(
                    ws_url=args.url,
                    token=token,
                    node_id=args.node_id,
                    fields=fields,
                    rate_hz=float(args.rate_hz),
                    seconds=max(1, int(args.seconds)),
                    timeout_sec=args.timeout,
                )
            )
        except (OSError, RuntimeError, json.JSONDecodeError, TimeoutError, asyncio.TimeoutError) as exc:
            print_output(
                {
                    "ok": False,
                    "error": "orchestrator_unreachable",
                    "message": str(exc),
                    "url": args.url,
                },
                args.json,
            )
            return 1

        print_output(message, args.json)
        return 0 if message.get("ok") else 1

    if args.subcommand == "peer":
        action_map = {
            "list": "peer.list",
            "status": "peer.node.status",
            "start": "peer.node.start",
            "stop": "peer.node.stop",
            "restart": "peer.node.restart",
        }
        ws_action = action_map[args.action]

        if args.action != "list" and not args.peer_id:
            print_output(
                {
                    "ok": False,
                    "error": "peer_id_required",
                    "message": "peer id is required for status/start/stop/restart",
                },
                args.json,
            )
            return 1

        if args.action in {"start", "stop", "restart"} and not args.node_id:
            print_output(
                {
                    "ok": False,
                    "error": "node_id_required",
                    "message": "node id is required for start/stop/restart",
                },
                args.json,
            )
            return 1

        required_role = "viewer" if args.action in {"list", "status"} else "operator"
        token = args.token or pick_orchestrator_token(required_role, auth_file=args.auth_file)
        if not token:
            print_output(
                {
                    "ok": False,
                    "error": "token_not_found",
                    "message": f"Provide --token or configure {args.auth_file}",
                },
                args.json,
            )
            return 1

        payload = {}
        if args.action != "list":
            payload["peerId"] = args.peer_id
        if args.action in {"status", "start", "stop", "restart"} and args.node_id:
            payload["nodeId"] = args.node_id
        if args.action == "stop":
            payload["graceSec"] = max(1, int(args.grace_sec))
        payload["timeoutSec"] = max(1, int(args.peer_timeout))

        try:
            message = asyncio.run(
                orchestrator_ws_command(
                    ws_url=args.url,
                    token=token,
                    action=ws_action,
                    payload=payload,
                    timeout_sec=args.timeout,
                )
            )
        except (OSError, RuntimeError, json.JSONDecodeError, TimeoutError) as exc:
            print_output(
                {
                    "ok": False,
                    "error": "orchestrator_unreachable",
                    "message": str(exc),
                    "url": args.url,
                },
                args.json,
            )
            return 1

        output = {
            "ok": message.get("type") != "error",
            "type": message.get("type"),
            "action": message.get("action"),
            "requestId": message.get("requestId"),
            "payload": message.get("payload", {}),
        }
        print_output(output, args.json)
        return 0 if output["ok"] else 1

    print_output({"ok": False, "error": "invalid_orchestrator_subcommand"}, args.json)
    return 1


def handle_package(args):
    manager_cmd = "opkg" if args.manager == "opkg" else "pip3"

    if args.subcommand == "list":
        if args.manager == "opkg":
            result = run_command([manager_cmd, "list-installed"])
        else:
            result = run_command([manager_cmd, "list", "--format=json"])

        payload = {
            "ok": result["ok"],
            "manager": args.manager,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }
        print_output(payload, args.json)
        return 0 if result["ok"] else 1

    if args.subcommand == "install":
        if not args.packages:
            print_output({"ok": False, "error": "no_packages_provided"}, args.json)
            return 1

        if args.manager == "opkg":
            cmd = [manager_cmd, "install", *args.packages]
        else:
            cmd = [manager_cmd, "install", "--no-input", *args.packages]

        result = run_command(cmd)
        payload = {
            "ok": result["ok"],
            "manager": args.manager,
            "packages": args.packages,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }
        print_output(payload, args.json)
        return 0 if result["ok"] else 1

    print_output({"ok": False, "error": "invalid_package_subcommand"}, args.json)
    return 1


def handle_custom(args):
    command_path = Path(CUSTOM_COMMAND_DIR) / args.command
    if not command_path.is_file() or not os.access(command_path, os.X_OK):
        print_output({"ok": False, "error": "custom_command_not_found", "command": args.command}, args.json)
        return 1

    env = os.environ.copy()
    env["SPINY_OUTPUT"] = "json" if args.json else "text"
    result = subprocess.run([str(command_path), *args.args], capture_output=True, text=True, env=env)
    if args.json:
        if result.stdout.strip():
            print(result.stdout.strip())
        else:
            print_output({"ok": result.returncode == 0, "stdout": "", "stderr": result.stderr.strip()}, True)
    else:
        sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
    return result.returncode


def build_parser():
    parser = argparse.ArgumentParser(prog="spinyctl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    device = subparsers.add_parser("device")
    device_sub = device.add_subparsers(dest="subcommand", required=True)
    device_info = device_sub.add_parser("info")
    device_info.add_argument("--json", action="store_true")

    wifi = subparsers.add_parser("wifi")
    wifi_sub = wifi.add_subparsers(dest="subcommand", required=True)
    wifi_status = wifi_sub.add_parser("status")
    wifi_status.add_argument("--json", action="store_true")

    service = subparsers.add_parser("service")
    service.add_argument("action", choices=["status", "start", "stop", "restart", "enable", "disable"])
    service.add_argument("name")
    service.add_argument("--json", action="store_true")

    telemetry = subparsers.add_parser("telemetry")
    telemetry.add_argument("action", choices=["status", "start", "stop", "restart", "enable", "disable"])
    telemetry.add_argument("--json", action="store_true")

    orchestrator = subparsers.add_parser("orchestrator")
    orchestrator_sub = orchestrator.add_subparsers(dest="subcommand", required=True)
    orchestrator_service = orchestrator_sub.add_parser("service")
    orchestrator_service.add_argument("action", choices=["status", "start", "stop", "restart", "enable", "disable"])
    orchestrator_service.add_argument("--json", action="store_true")
    orchestrator_policy = orchestrator_sub.add_parser("policy")
    orchestrator_policy.add_argument("--json", action="store_true")
    orchestrator_user = orchestrator_sub.add_parser("user")
    orchestrator_user.add_argument("action", choices=["info"])
    orchestrator_user.add_argument("--token")
    orchestrator_user.add_argument("--auth-file", default=ORCHESTRATOR_AUTH_FILE)
    orchestrator_user.add_argument("--url", default=os.getenv("SPINY_ORCH_URL", ORCHESTRATOR_WS_URL))
    orchestrator_user.add_argument("--timeout", type=int, default=15)
    orchestrator_user.add_argument("--json", action="store_true")
    orchestrator_nodes = orchestrator_sub.add_parser("nodes")
    orchestrator_nodes.add_argument("--json", action="store_true")
    orchestrator_nodes.add_argument("--details", action="store_true")
    orchestrator_nodes.add_argument("--manifest", default=ORCHESTRATOR_MANIFEST_FILE)

    orchestrator_node = orchestrator_sub.add_parser("node")
    orchestrator_node.add_argument("action", choices=["list", "status", "start", "stop", "restart"])
    orchestrator_node.add_argument("node_id", nargs="?")
    orchestrator_node.add_argument("--grace-sec", type=int, default=5)
    orchestrator_node.add_argument("--token")
    orchestrator_node.add_argument("--auth-file", default=ORCHESTRATOR_AUTH_FILE)
    orchestrator_node.add_argument("--url", default=os.getenv("SPINY_ORCH_URL", ORCHESTRATOR_WS_URL))
    orchestrator_node.add_argument("--timeout", type=int, default=15)
    orchestrator_node.add_argument("--json", action="store_true")

    orchestrator_graph = orchestrator_sub.add_parser("graph")
    orchestrator_graph.add_argument("action", choices=["snapshot"])
    orchestrator_graph.add_argument("--token")
    orchestrator_graph.add_argument("--auth-file", default=ORCHESTRATOR_AUTH_FILE)
    orchestrator_graph.add_argument("--url", default=os.getenv("SPINY_ORCH_URL", ORCHESTRATOR_WS_URL))
    orchestrator_graph.add_argument("--timeout", type=int, default=15)
    orchestrator_graph.add_argument("--json", action="store_true")

    orchestrator_io = orchestrator_sub.add_parser("io")
    orchestrator_io.add_argument("node_name")
    orchestrator_io.add_argument("--token")
    orchestrator_io.add_argument("--auth-file", default=ORCHESTRATOR_AUTH_FILE)
    orchestrator_io.add_argument("--url", default=os.getenv("SPINY_ORCH_URL", ORCHESTRATOR_WS_URL))
    orchestrator_io.add_argument("--timeout", type=int, default=15)
    orchestrator_io.add_argument("--json", action="store_true")

    orchestrator_capture = orchestrator_sub.add_parser("capture")
    orchestrator_capture.add_argument("action", choices=["window"])
    orchestrator_capture.add_argument("--duration-sec", type=int, default=5)
    orchestrator_capture.add_argument("--sample-interval-sec", type=int, default=1)
    orchestrator_capture.add_argument("--node-name", action="append", default=[])
    orchestrator_capture.add_argument("--token")
    orchestrator_capture.add_argument("--auth-file", default=ORCHESTRATOR_AUTH_FILE)
    orchestrator_capture.add_argument("--url", default=os.getenv("SPINY_ORCH_URL", ORCHESTRATOR_WS_URL))
    orchestrator_capture.add_argument("--timeout", type=int, default=120)
    orchestrator_capture.add_argument("--json", action="store_true")

    orchestrator_stream = orchestrator_sub.add_parser("stream")
    orchestrator_stream.add_argument("action", choices=["watch"])
    orchestrator_stream.add_argument("node_id")
    orchestrator_stream.add_argument("--field", action="append", default=[])
    orchestrator_stream.add_argument("--rate-hz", type=float, default=1.0)
    orchestrator_stream.add_argument("--seconds", type=int, default=10)
    orchestrator_stream.add_argument("--token")
    orchestrator_stream.add_argument("--auth-file", default=ORCHESTRATOR_AUTH_FILE)
    orchestrator_stream.add_argument("--url", default=os.getenv("SPINY_ORCH_URL", ORCHESTRATOR_WS_URL))
    orchestrator_stream.add_argument("--timeout", type=int, default=30)
    orchestrator_stream.add_argument("--json", action="store_true")

    orchestrator_peer = orchestrator_sub.add_parser("peer")
    orchestrator_peer.add_argument("action", choices=["list", "status", "start", "stop", "restart"])
    orchestrator_peer.add_argument("peer_id", nargs="?")
    orchestrator_peer.add_argument("node_id", nargs="?")
    orchestrator_peer.add_argument("--grace-sec", type=int, default=5)
    orchestrator_peer.add_argument("--peer-timeout", type=int, default=15)
    orchestrator_peer.add_argument("--token")
    orchestrator_peer.add_argument("--auth-file", default=ORCHESTRATOR_AUTH_FILE)
    orchestrator_peer.add_argument("--url", default=os.getenv("SPINY_ORCH_URL", ORCHESTRATOR_WS_URL))
    orchestrator_peer.add_argument("--timeout", type=int, default=20)
    orchestrator_peer.add_argument("--json", action="store_true")

    package = subparsers.add_parser("package")
    package_sub = package.add_subparsers(dest="subcommand", required=True)
    package_list = package_sub.add_parser("list")
    package_list.add_argument("--manager", choices=["opkg", "pip"], default="opkg")
    package_list.add_argument("--json", action="store_true")
    package_install = package_sub.add_parser("install")
    package_install.add_argument("--manager", choices=["opkg", "pip"], default="opkg")
    package_install.add_argument("--json", action="store_true")
    package_install.add_argument("packages", nargs="+")

    custom = subparsers.add_parser("custom")
    custom.add_argument("--json", action="store_true")
    custom.add_argument("command")
    custom.add_argument("args", nargs=argparse.REMAINDER)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "device" and args.subcommand == "info":
        return get_device_info(args.json)
    if args.command == "wifi" and args.subcommand == "status":
        return get_wifi_status(args.json)
    if args.command == "service":
        return handle_service(args)
    if args.command == "telemetry":
        return handle_telemetry(args)
    if args.command == "orchestrator":
        return handle_orchestrator(args)
    if args.command == "package":
        return handle_package(args)
    if args.command == "custom":
        return handle_custom(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())