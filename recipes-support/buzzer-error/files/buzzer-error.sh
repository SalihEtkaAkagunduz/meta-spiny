#!/bin/bash
# Buzzer Error Service Script

CONFIG_FILE="/etc/buzzer-pin.conf"
GPIO_PIN="17"
BUZZER_DISABLED="/tmp/buzzer_disabled"

# Load configuration
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
    GPIO_PIN="$BUZZER_GPIO_PIN"
else
    echo "Configuration file not found: $CONFIG_FILE, using default GPIO17"
fi

# Check for GPIO conflicts with LCD (fb_ili9486 uses GPIO17)
check_gpio_conflict() {
    local pin=$1
    
    # Check if LCD is present (fb2 device exists)
    if [ -e "/dev/fb2" ]; then
        # Check if fb_ili9486 driver is loaded
        if lsmod 2>/dev/null | grep -q "fb_ili9486"; then
            # GPIO17 is used by LCD overlay (tft35a)
            if [ "$pin" = "17" ]; then
                echo "ERROR: GPIO17 is currently in use by LCD display (fb_ili9486)"
                echo "Cannot start buzzer service on GPIO17 while LCD is active"
                echo "Please reconfigure buzzer to use a different GPIO pin:"
                echo "  buzzererror --gpio 22  # or 23, 24, 25, 27"
                return 1
            fi
        fi
    fi
    
    return 0
}

# GPIO setup function
setup_gpio() {
    # Check for conflicts before setup
    if ! check_gpio_conflict "$GPIO_PIN"; then
        echo "Cannot setup GPIO$GPIO_PIN due to conflict"
        return 1
    fi
    
    if [ ! -d "/sys/class/gpio/gpio$GPIO_PIN" ]; then
        echo "$GPIO_PIN" > /sys/class/gpio/export 2>/dev/null
        if [ $? -ne 0 ]; then
            echo "ERROR: Failed to export GPIO$GPIO_PIN"
            return 1
        fi
        echo "out" > /sys/class/gpio/gpio$GPIO_PIN/direction
    fi
    return 0
}

# Buzzer beep function
beep() {
    local duration=${1:-0.1}
    echo "1" > /sys/class/gpio/gpio$GPIO_PIN/value 2>/dev/null
    sleep "$duration"
    echo "0" > /sys/class/gpio/gpio$GPIO_PIN/value 2>/dev/null
}

# Buzzer error function (system-wide available) - accepts beep count parameter
buzzererror() {
    # Check if buzzer is disabled
    if [ -f "$BUZZER_DISABLED" ]; then
        return 0
    fi
    
    local count=${1:-1}  # Default to 1 beep if no parameter given
    
    if ! setup_gpio; then
        echo "WARNING: Buzzer unavailable due to GPIO conflict"
        return 1
    fi
    
    for ((i=1; i<=count; i++)); do
        beep 0.2
        if [ $i -lt $count ]; then
            sleep 0.1
        fi
    done
}

# Export function for system-wide use
export -f buzzererror

# Service start
start_service() {
    echo "Starting Buzzer Error Service on GPIO $GPIO_PIN..."
    
    if ! setup_gpio; then
        echo "Failed to start buzzer service due to GPIO conflict"
        echo "Service will not be available until GPIO conflict is resolved"
        exit 1
    fi
    
    echo "Buzzer Error Service started successfully on GPIO $GPIO_PIN"
    # Test beep to confirm functionality
    beep 0.1
}

# Service stop
stop_service() {
    if [ -d "/sys/class/gpio/gpio$GPIO_PIN" ]; then
        echo "0" > /sys/class/gpio/gpio$GPIO_PIN/value 2>/dev/null
        echo "$GPIO_PIN" > /sys/class/gpio/unexport 2>/dev/null
    fi
    echo "Buzzer Error Service stopped"
}

case "$1" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    beep)
        if ! setup_gpio; then
            echo "Cannot beep: GPIO conflict"
            exit 1
        fi
        beep "${2:-0.1}"
        ;;
    *)
        echo "Usage: $0 {start|stop|beep [duration]}"
        exit 1
        ;;
esac