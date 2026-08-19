#!/usr/bin/env python3

import sys
import subprocess
import os

SERVICE_NAME = 'device-ingest.service'

def run_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, '', str(e)

def is_enabled():
    success, out, err = run_command(f'systemctl is-enabled {SERVICE_NAME}')
    return out == 'enabled'

def stop_service():
    success, out, err = run_command(f'systemctl stop {SERVICE_NAME}')
    if success:
        print("Device ingest service stopped.")
    else:
        print(f"Failed to stop service: {err}")

def start_service():
    success, out, err = run_command(f'systemctl start {SERVICE_NAME}')
    if success:
        print("Device ingest service started.")
    else:
        print(f"Failed to start service: {err}")

def enable_service():
    success, out, err = run_command(f'systemctl enable {SERVICE_NAME}')
    if success:
        print("Device ingest service enabled for boot.")
    else:
        print(f"Failed to enable service: {err}")

def disable_service():
    success, out, err = run_command(f'systemctl disable {SERVICE_NAME}')
    if success:
        print("Device ingest service disabled for boot.")
    else:
        print(f"Failed to disable service: {err}")

def restart_service():
    success, out, err = run_command(f'systemctl restart {SERVICE_NAME}')
    if success:
        print("Device ingest service restarted.")
    else:
        print(f"Failed to restart service: {err}")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        print("""Telemetry Control for Device Ingest Service

Usage: telemetry [OPTION]

Options:
  -s, --stop          Stop the device ingest service immediately
  -c, --continue      Start/continue the service (only if not disabled)
  -e, --enable        Enable the service for boot and start it
  -d, --disable       Disable the service for boot and stop it
  -r, --restart       Restart the service (only if not disabled)
  -h, --help          Show this help message

Note: When the service is disabled, only --enable is allowed.
""")
        sys.exit(0 if sys.argv[1] in ['-h', '--help'] else 1)

    arg = sys.argv[1]

    if arg in ['-s', '--stop']:
        stop_service()
    elif arg in ['-c', '--continue']:
        if not is_enabled():
            print("Service is disabled. Only --enable is allowed.")
            sys.exit(1)
        start_service()
    elif arg in ['--enable', '-e']:
        enable_service()
        start_service()
    elif arg in ['--disable', '-d']:
        disable_service()
        stop_service()
    elif arg in ['--restart', '-r']:
        if not is_enabled():
            print("Service is disabled. Only --enable is allowed.")
            sys.exit(1)
        restart_service()
    else:
        print("Invalid argument.")
        sys.exit(1)

if __name__ == '__main__':
    main()