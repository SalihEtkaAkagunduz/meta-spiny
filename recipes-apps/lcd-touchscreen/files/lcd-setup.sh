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

# Check for LCD enable flag
LCD_ENABLE_FLAG="/var/lib/lcd-enabled"
if [ ! -f "$LCD_ENABLE_FLAG" ]; then
    log_msg "LCD not enabled - skipping setup"
    log_msg "To enable LCD: touch /var/lib/lcd-enabled and reboot"
    exit 0
fi

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
    
    # Keep VC4 KMS enabled for HDMI support
    # Do NOT disable vc4-kms-v3d to maintain HDMI output
    
    # Add LCD configuration (both HDMI and LCD will work)
    cat >> "$CONFIG_FILE" << 'EOF'

# ========================================
# 3.5" TFT LCD Display Configuration
# Added by lcd-setup service
# Note: HDMI remains active (primary display)
# LCD is secondary display at /dev/fb1
# ========================================
dtoverlay=tft35a:rotate=90,speed=32000000,fps=30
dtparam=spi=on
dtparam=i2c_arm=on
enable_uart=1

# HDMI Configuration (keeps HDMI working)
hdmi_force_hotplug=1
hdmi_drive=2
EOF
    
    log_msg "LCD configuration added to config.txt"
    sync
else
    log_msg "LCD configuration already in config.txt"
fi

# Set default LCD mode to Terminal (Mode 1)
mkdir -p /var/lib
echo "1" > /var/lib/lcd-mode
log_msg "LCD mode set to Terminal (Mode 1)"

# Mark setup as completed
touch "$SETUP_DONE"
log_msg "LCD setup completed successfully"
log_msg "Please reboot to apply LCD configuration: sudo reboot"

exit 0
