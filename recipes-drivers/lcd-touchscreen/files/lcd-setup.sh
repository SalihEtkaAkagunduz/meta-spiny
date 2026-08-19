#!/bin/bash
# LCD First Boot Setup Script
# Ensures all LCD files are present on first boot

BOOT_PATH="/boot"
OVERLAYS_PATH="${BOOT_PATH}/overlays"
CONFIG_FILE="${BOOT_PATH}/config.txt"
SETUP_DONE="/var/lib/lcd-setup-done"

# Embedded overlay files (base64 encoded)
TFT35A_B64="__TFT35A_OVERLAY_BASE64__"
ADS7846_B64="__ADS7846_OVERLAY_BASE64__"

log_msg() {
    echo "[LCD-SETUP] $1"
    logger -t lcd-setup "$1"
}

# Check if setup already completed
if [ -f "$SETUP_DONE" ]; then
    log_msg "LCD setup already completed, skipping"
    exit 0
fi

log_msg "Starting LCD first-boot setup"

# Ensure directories exist
mkdir -p "$OVERLAYS_PATH"

# Check and install tft35a overlay
if [ ! -f "${OVERLAYS_PATH}/tft35a.dtbo" ]; then
    log_msg "Installing tft35a.dtbo overlay"
    
    # Try to copy from system directory if available
    if [ -f "/usr/share/lcd-overlays/tft35a.dtbo" ]; then
        cp /usr/share/lcd-overlays/tft35a.dtbo "${OVERLAYS_PATH}/tft35a.dtbo"
    else
        log_msg "ERROR: tft35a.dtbo not found in /usr/share/lcd-overlays/"
        exit 1
    fi
    
    chmod 644 "${OVERLAYS_PATH}/tft35a.dtbo"
    log_msg "tft35a.dtbo installed successfully"
else
    log_msg "tft35a.dtbo already exists"
fi

# Check and install ads7846 overlay
if [ ! -f "${OVERLAYS_PATH}/ads7846.dtbo" ]; then
    log_msg "Installing ads7846.dtbo overlay"
    
    if [ -f "/usr/share/lcd-overlays/ads7846.dtbo" ]; then
        cp /usr/share/lcd-overlays/ads7846.dtbo "${OVERLAYS_PATH}/ads7846.dtbo"
    else
        log_msg "ERROR: ads7846.dtbo not found in /usr/share/lcd-overlays/"
        exit 1
    fi
    
    chmod 644 "${OVERLAYS_PATH}/ads7846.dtbo"
    log_msg "ads7846.dtbo installed successfully"
else
    log_msg "ads7846.dtbo already exists"
fi

# Check and update config.txt
if ! grep -q "dtoverlay=tft35a" "$CONFIG_FILE"; then
    log_msg "Adding LCD configuration to config.txt"
    
    # Disable VC4 KMS if present
    sed -i 's/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d # Disabled for LCD/' "$CONFIG_FILE"
    
    # Add LCD configuration
    cat >> "$CONFIG_FILE" << 'EOF'

# ========================================
# 3.5" TFT LCD Display Configuration
# Added by lcd-setup service
# ========================================
dtoverlay=tft35a:rotate=90,speed=32000000,fps=30,fbdev=2
dtparam=spi=on
dtparam=i2c_arm=on
enable_uart=1
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt 480 320 60 6 0 0 0
hdmi_drive=2
EOF
    
    log_msg "LCD configuration added to config.txt"
    sync
else
    log_msg "LCD configuration already in config.txt"
fi

# Set default LCD mode to Terminal (Mode 1)
echo "1" > /var/lib/lcd-mode
log_msg "LCD mode set to Terminal (Mode 1) - use 'lcd-screen -m 2' for Touchscreen UI"

# Mark setup as completed
touch "$SETUP_DONE"
log_msg "LCD setup completed successfully"
log_msg "System will reboot to apply LCD configuration"

# Reboot to apply changes
sleep 2
systemctl reboot
