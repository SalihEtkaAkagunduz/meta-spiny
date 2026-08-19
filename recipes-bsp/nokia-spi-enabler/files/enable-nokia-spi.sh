#!/bin/bash
# Enable SPI for Nokia 5110 display

set -u

CONFIG_FILE="/boot/config.txt"
SPI_LINE="dtparam=spi=on"

# Helper: print warning and exit success so systemd doesn't mark the unit as failed
warn_and_exit()
{
    echo "WARNING: $*"
    echo "(This script will not mark the unit as failed; fix manually or rerun when writable.)"
    exit 0
}

# Ensure the config file's directory exists
mkdir -p "$(dirname "$CONFIG_FILE")" || true

# If the config file exists but isn't writable, try remounting /boot only if it's a mountpoint
if [ -f "$CONFIG_FILE" ] && [ ! -w "$CONFIG_FILE" ]; then
    if mountpoint -q /boot; then
        echo "Remounting /boot as read-write..."
        if ! mount -o remount,rw /boot; then
            warn_and_exit "Failed to remount /boot as read-write; cannot modify $CONFIG_FILE"
        fi
    else
        warn_and_exit "$CONFIG_FILE exists but is not writable and /boot is not a separate mount. Cannot enable SPI automatically."
    fi
fi

# If the config file doesn't exist try creating it (may still fail if FS is read-only)
if [ ! -f "$CONFIG_FILE" ]; then
    touch "$CONFIG_FILE" 2>/dev/null || warn_and_exit "Cannot create $CONFIG_FILE (filesystem may be read-only)"
fi

# At this point $CONFIG_FILE should exist and be writable (or we've exited)

# Check if SPI is already enabled (allow possible leading whitespace)
if grep -q "^[[:space:]]*${SPI_LINE}" "$CONFIG_FILE"; then
    echo "SPI already enabled in $CONFIG_FILE"
    exit 0
fi

# Check if SPI line exists but is commented
if grep -q "^[[:space:]]*#${SPI_LINE}" "$CONFIG_FILE"; then
    # Uncomment the line
    sed -i "s/^[[:space:]]*#\(${SPI_LINE}\)/\1/" "$CONFIG_FILE"
    echo "SPI enabled (uncommented) in $CONFIG_FILE"
else
    # Add SPI line
    printf "\n# Nokia 5110 SPI Configuration\n%s\n" "$SPI_LINE" >> "$CONFIG_FILE"
    echo "SPI enabled (added) in $CONFIG_FILE"
fi

sync
echo "SPI configuration complete"
