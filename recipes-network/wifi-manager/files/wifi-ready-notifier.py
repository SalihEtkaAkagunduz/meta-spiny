#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


def _get_device_ips() -> list:
    """Return all non-loopback IPv4 addresses of this device."""
    try:
        out = subprocess.getoutput("ip -4 addr show scope global")
        return [p.split()[1].split('/')[0]
                for p in out.splitlines()
                if p.strip().startswith("inet ") and "127." not in p]
    except Exception:
        return []


def main() -> int:
    if len(sys.argv) != 8:
        return 1

    callback_url = sys.argv[1]
    ack_file = sys.argv[2]
    device_id = sys.argv[3]
    hostname = sys.argv[4]
    target_ssid = sys.argv[5]
    api_base_url = sys.argv[6]
    interval = int(sys.argv[7])

    # Build payload once; device_ips refreshed on each attempt
    base_payload = {
        "event": "device_ready",
        "device_id": device_id,
        "hostname": hostname,
        "mdns": f"{hostname}.local",
        "target_ssid": target_ssid,
        "api_base_url": api_base_url,
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    while True:
        if os.path.exists(ack_file):
            return 0

        # Refresh device_ips on every attempt so app gets current IPs
        payload = json.dumps({
            **base_payload,
            "device_ips": _get_device_ips(),
        }).encode()

        request = urllib.request.Request(
            callback_url,
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5):
                pass
        except (urllib.error.URLError, TimeoutError, ValueError):
            pass

        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())