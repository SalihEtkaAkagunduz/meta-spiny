#!/usr/bin/env python3

import time
import requests
import json
import subprocess
import sys
import os
import logging

# Configuration
ENDPOINT_URL = os.getenv('DEVICE_INGEST_URL', 'https://spinyfunc-gsf8g4h2gzf8ecbe.francecentral-01.azurewebsites.net/api/deviceingest?code=3rzXvu4yPasnnbPYFG83gApv0wNJkH3OVMzEsri1zErrAzFuJYPcrA==')
INTERVAL = int(os.getenv('DEVICE_INGEST_INTERVAL', '60'))  # seconds

logging.basicConfig(filename='/home/root/device-ingest.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_cpu_usage():
    """Get CPU usage percentage"""
    try:
        with open('/proc/stat', 'r') as f:
            line = f.readline().split()
        total = sum(int(x) for x in line[1:8])
        idle = int(line[4])
        return round((1 - idle / total) * 100, 1)
    except:
        return 0.0

def get_cpu_temperature():
    """Get CPU temperature in Celsius"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = int(f.read().strip()) / 1000.0
        return round(temp, 1)
    except:
        return 0.0

def get_ram_usage():
    """Get RAM usage percentage"""
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        total = int([l for l in lines if l.startswith('MemTotal:')][0].split()[1])
        available = int([l for l in lines if l.startswith('MemAvailable:')][0].split()[1])
        return round((total - available) / total * 100, 1)
    except:
        return 0.0

def get_disk_usage():
    """Get disk usage percentage for SD card (including unallocated space)"""
    try:
        # Get total SD card size in bytes
        total_bytes = int(subprocess.getoutput('blockdev --getsize64 /dev/mmcblk0'))
        total_kb = total_bytes // 1024

        # Get used space from all partitions on the SD card
        df_output = subprocess.getoutput('df -k').split('\n')
        used_kb = 0
        for line in df_output[1:]:
            parts = line.split()
            if len(parts) >= 6 and parts[0].startswith('/dev/mmcblk0'):
                used_kb += int(parts[2])

        return round(used_kb / total_kb * 100, 1) if total_kb > 0 else 0.0
    except:
        # Fallback to root partition
        try:
            df = subprocess.getoutput('df /').split('\n')[1].split()
            used = int(df[2])
            total = int(df[1])
            return round(used / total * 100, 1)
        except:
            return 0.0

def get_ip_address():
    """Get IP address"""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

def get_network():
    """Get network name (simplified)"""
    try:
        # Determine default interface
        iface = subprocess.getoutput("ip route 2>/dev/null | awk '/default/ {print $5; exit}'").strip()
        if not iface:
            iface = subprocess.getoutput("route -n 2>/dev/null | awk '/^0.0.0.0/ {print $8; exit}'").strip()

        # If it's a wireless interface, try several ways to get SSID
        if iface and (iface.startswith('wl') or iface.startswith('wlan')):
            # 1) iwgetid
            ssid = subprocess.getoutput('iwgetid -r 2>/dev/null').strip()
            if ssid:
                return ssid

            # 2) nmcli (NetworkManager)
            try:
                nm = subprocess.getoutput("nmcli -t -f TYPE,DEVICE,STATE,CONNECTION dev status 2>/dev/null | awk -F: '$1==\"wifi\" && $3==\"connected\" {print $4; exit}'").strip()
                if nm:
                    return nm
            except:
                pass

            # 3) iw (modern wireless tools)
            try:
                out = subprocess.getoutput(f'iw dev {iface} link 2>/dev/null')
                for line in out.splitlines():
                    if line.strip().startswith('SSID:'):
                        return line.split('SSID:')[1].strip()
            except:
                pass

            # fallback to interface name if no SSID
            return iface

        # Not wireless: return interface or 'wired'
        if iface:
            return iface
        return 'unknown'
    except:
        return 'unknown'

def get_ping():
    """Get ping time to 8.8.8.8"""
    try:
        output = subprocess.getoutput('ping -c 1 -W 1 8.8.8.8')
        if 'time=' in output:
            time_str = output.split('time=')[1].split()[0]
            return float(time_str)
        return 0.0
    except:
        return 0.0

def get_uptime_formatted():
    """Get uptime in HH:MM:SS format"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except:
        return "00:00:00"

def get_device_metrics():
    """Collect device metrics in required format"""
    hostname = subprocess.getoutput('hostname').strip()
    metrics = {
        "deviceId": hostname,
        "cpuUsage": get_cpu_usage(),
        "cpuTemperature": get_cpu_temperature(),
        "ramUsage": get_ram_usage(),
        "diskUsage": get_disk_usage(),
        "ipAddress": get_ip_address(),
        "network": get_network(),
        "ping": get_ping(),
        "connectionQuality": "Good",  # Simplified
        "uptime": get_uptime_formatted()
    }
    return metrics

def send_metrics(metrics):
    """Send metrics to the endpoint"""
    try:
        logging.info(f"Sending metrics: {json.dumps(metrics)}")
        response = requests.post(ENDPOINT_URL, json=metrics, timeout=10)
        if response.status_code == 200:
            logging.info("Metrics sent successfully")
        else:
            logging.error(f"Failed to send metrics: HTTP {response.status_code}, Response: {response.text}")
    except Exception as e:
        logging.error(f"Error sending metrics: {e}")

def check_internet():
    """Check if internet is available"""
    try:
        requests.get('https://www.google.com', timeout=5)
        return True
    except:
        return False


def run_mqtt_mode(config):
    logging.info("Starting in MQTT/TCP mode...")
    server_address = config.get("server_address", "")
    port = config.get("port", 1883)
    device_id = config.get("device_id", "")
    auth_token = config.get("auth_token", "")
    
    host = server_address
    if "://" in server_address:
        import urllib.parse
        parsed = urllib.parse.urlparse(server_address)
        host = parsed.hostname or parsed.path

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        logging.error("paho-mqtt library is not installed! Cannot run in MQTT mode.")
        try:
            with open("/etc/spiny/tcp-state.json", "w") as f:
                json.dump({"status": "failed", "last_error": "mqtt_library_missing"}, f)
        except:
            pass
        return

    backoff = 2
    max_backoff = 60

    while True:
        # Check network connectivity
        while not check_internet():
            logging.info("Waiting for internet connection in MQTT mode...")
            try:
                with open("/etc/spiny/tcp-state.json", "w") as f:
                    json.dump({"status": "failed", "last_error": "network_unavailable"}, f)
            except:
                pass
            time.sleep(10)
            
        logging.info(f"Connecting to MQTT broker {host}:{port}...")
        try:
            with open("/etc/spiny/tcp-state.json", "w") as f:
                json.dump({"status": "connecting", "last_error": ""}, f)
        except:
            pass

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
                logging.info("Connected to MQTT broker. Subscribing and sending handshake...")
                client.subscribe(f"spiny/devices/{device_id}/handshake_response", qos=1)
                payload = json.dumps({
                    "type": "handshake_request",
                    "device_id": device_id,
                    "token": password  # Send only the parsed password/token part
                })
                client.publish(f"spiny/devices/{device_id}/handshake", payload, qos=1)
            else:
                logging.error(f"MQTT connection failed with code {rc}")
                handshake_status["status"] = f"connection_failed_rc_{rc}"

        def on_message(client, userdata, msg):
            topic = msg.topic
            payload_str = msg.payload.decode()
            logging.info(f"Received message on {topic}: {payload_str}")
            try:
                data = json.loads(payload_str)
            except Exception as e:
                logging.error(f"Error parsing JSON payload: {e}")
                return

            if topic == f"spiny/devices/{device_id}/handshake_response":
                if data.get("type") == "handshake_approve" and data.get("status") == "approved":
                    handshake_status["status"] = "approved"
                else:
                    handshake_status["status"] = "rejected"
            elif topic == f"spiny/devices/{device_id}/ping":
                # Respond to ping immediately with pong
                pong_topic = f"spiny/devices/{device_id}/pong"
                pong_payload = json.dumps({"status": "online"})
                logging.info(f"Responding to ping: publishing {pong_payload} to {pong_topic}")
                client.publish(pong_topic, pong_payload, qos=0)

        client.on_connect = on_connect
        client.on_message = on_message

        try:
            client.connect(host, port, keepalive=60)
        except Exception as e:
            err_msg = str(e)
            logging.error(f"Failed to connect to MQTT broker: {err_msg}")
            try:
                with open("/etc/spiny/tcp-state.json", "w") as f:
                    json.dump({"status": "failed", "last_error": f"connection_failed: {err_msg}"}, f)
            except:
                pass
            logging.info(f"Retrying connection in {backoff} seconds...")
            time.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
            continue

        # Wait for handshake approval
        client.loop_start()
        start_handshake = time.time()
        handshake_ok = False

        while time.time() - start_handshake < 10.0:
            if handshake_status["status"] == "approved":
                handshake_ok = True
                break
            elif handshake_status["status"] is not None:
                break
            time.sleep(0.1)

        if not handshake_ok:
            err_detail = handshake_status["status"] or "timeout"
            logging.error(f"Handshake failed or timed out. Reason: {err_detail}")
            try:
                with open("/etc/spiny/tcp-state.json", "w") as f:
                    json.dump({"status": "failed", "last_error": f"handshake_failed: {err_detail}"}, f)
            except:
                pass
            client.loop_stop()
            client.disconnect()
            logging.info(f"Retrying connection in {backoff} seconds...")
            time.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
            continue

        # Handshake approved! Reset backoff and publish telemetry
        logging.info("Handshake approved! Transitioning to telemetry publishing phase.")
        backoff = 2
        try:
            with open("/etc/spiny/tcp-state.json", "w") as f:
                json.dump({"status": "connected", "last_error": ""}, f)
        except:
            pass

        # Subscribe to ping topic
        ping_topic = f"spiny/devices/{device_id}/ping"
        logging.info(f"Subscribing to ping topic: {ping_topic}")
        client.subscribe(ping_topic, qos=0)

        telemetry_topic = f"spiny/devices/{device_id}/telemetry"

        while True:
            if not client.is_connected():
                logging.warning("MQTT client disconnected.")
                try:
                    with open("/etc/spiny/tcp-state.json", "w") as f:
                        json.dump({"status": "failed", "last_error": "connection_lost"}, f)
                except:
                    pass
                break

            try:
                metrics = get_device_metrics()
                logging.info(f"Publishing telemetry to {telemetry_topic}...")
                client.publish(telemetry_topic, json.dumps(metrics), qos=1)
            except Exception as e:
                logging.error(f"Error publishing telemetry: {e}")

            time.sleep(INTERVAL)

        client.loop_stop()
        client.disconnect()
        logging.info(f"Retrying connection in {backoff} seconds...")
        time.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)


def main():
    logging.info("Device Ingest service starting...")
    
    tcp_config_path = "/etc/spiny/tcp_config.json"
    if os.path.exists(tcp_config_path):
        try:
            with open(tcp_config_path) as f:
                config = json.load(f)
            if config.get("active_status", False):
                run_mqtt_mode(config)
                return
        except Exception as e:
            logging.error(f"Error reading TCP config: {e}")
            
    # Fallback to HTTP mode
    logging.info("Running in HTTP mode...")
    while not check_internet():
        logging.info("Waiting for internet connection...")
        time.sleep(10)
    logging.info("Internet connected, starting metrics collection...")
    while True:
        try:
            logging.info("Collecting metrics...")
            metrics = get_device_metrics()
            logging.info(f"Collected metrics: {json.dumps(metrics)}")
            send_metrics(metrics)
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
        logging.info(f"Sleeping for {INTERVAL} seconds...")
        time.sleep(INTERVAL)


if __name__ == '__main__':
    main()
