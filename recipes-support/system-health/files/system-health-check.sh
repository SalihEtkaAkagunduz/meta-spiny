#!/bin/bash
# System Health Check Script
# Runs on every boot to verify system integrity

LOG_TAG="system-health"
HEALTH_CHECK_LOG="/var/log/system-health.log"

log_msg() {
    local level="$1"
    local msg="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $msg" | tee -a "$HEALTH_CHECK_LOG"
    logger -t "$LOG_TAG" -p "user.$level" "$msg"
}

check_lcd_files() {
    log_msg "info" "=== LCD Files Check ==="
    
    local issues=0
    
    # Check overlay files
    if [ ! -f "/boot/overlays/tft35a.dtbo" ]; then
        log_msg "warn" "Missing: /boot/overlays/tft35a.dtbo"
        issues=$((issues + 1))
    else
        log_msg "info" "OK: tft35a.dtbo present"
    fi
    
    if [ ! -f "/boot/overlays/ads7846.dtbo" ]; then
        log_msg "warn" "Missing: /boot/overlays/ads7846.dtbo"
        issues=$((issues + 1))
    else
        log_msg "info" "OK: ads7846.dtbo present"
    fi
    
    # Check config.txt
    if ! grep -q "dtoverlay=tft35a" /boot/config.txt; then
        log_msg "warn" "LCD configuration missing in config.txt"
        issues=$((issues + 1))
    else
        log_msg "info" "OK: LCD config in config.txt"
    fi
    
    # If issues found, trigger lcd-setup service
    if [ $issues -gt 0 ]; then
        log_msg "warn" "Found $issues LCD configuration issues"
        log_msg "info" "Triggering lcd-setup service"
        rm -f /var/lib/lcd-setup-done
        systemctl start lcd-setup.service
        return 1
    fi
    
    return 0
}

check_lcd_hardware() {
    log_msg "info" "=== LCD Hardware Check ==="
    
    # Check if LCD framebuffer exists
    if [ -e "/dev/fb2" ]; then
        log_msg "info" "OK: LCD framebuffer /dev/fb2 detected"
        
        # Check driver
        if lsmod 2>/dev/null | grep -q "fb_ili9486"; then
            log_msg "info" "OK: fb_ili9486 driver loaded"
        else
            log_msg "warn" "fb_ili9486 driver not loaded"
        fi
        
        # Check touchscreen
        if [ -e "/dev/input/event0" ]; then
            log_msg "info" "OK: Touchscreen device detected"
        else
            log_msg "warn" "Touchscreen device not found"
        fi
        
    else
        log_msg "info" "LCD framebuffer not detected (LCD may not be connected)"
    fi
}

check_buzzer_gpio() {
    log_msg "info" "=== Buzzer GPIO Check ==="
    
    # Check buzzer configuration
    if [ -f "/etc/buzzer-pin.conf" ]; then
        source /etc/buzzer-pin.conf
        log_msg "info" "Buzzer configured on GPIO${BUZZER_GPIO_PIN}"
        
        # Check for GPIO conflicts with LCD
        if [ "$BUZZER_GPIO_PIN" = "17" ] && [ -e "/dev/fb2" ]; then
            log_msg "warn" "GPIO17 conflict: Both LCD and buzzer trying to use GPIO17"
            log_msg "info" "Recommendation: Run 'buzzererror --gpio 22' to change buzzer pin"
        fi
    else
        log_msg "warn" "Buzzer configuration file missing"
    fi
}

check_services() {
    log_msg "info" "=== Service Status Check ==="
    
    local services=("lcd-display.service" "buzzer-error.service" "dropbear.socket")
    
    for service in "${services[@]}"; do
        if systemctl is-enabled "$service" >/dev/null 2>&1; then
            if systemctl is-active "$service" >/dev/null 2>&1; then
                log_msg "info" "OK: $service is active"
            else
                log_msg "warn" "$service is enabled but not active"
                # Try to get status
                systemctl status "$service" --no-pager -l >> "$HEALTH_CHECK_LOG" 2>&1
            fi
        else
            log_msg "info" "$service is not enabled"
        fi
    done
}

check_network() {
    log_msg "info" "=== Network Check ==="
    
    # Check if any network interface is up
    if ip link show | grep -q "state UP"; then
        log_msg "info" "OK: Network interface is up"
        
        # Check for IP address
        if ip addr show | grep -q "inet "; then
            local ip=$(ip addr show | grep "inet " | grep -v "127.0.0.1" | awk '{print $2}' | cut -d'/' -f1 | head -1)
            log_msg "info" "OK: IP address assigned: $ip"
        else
            log_msg "warn" "No IP address assigned"
        fi
    else
        log_msg "warn" "No network interface is up"
    fi
}

check_storage() {
    log_msg "info" "=== Storage Check ==="
    
    # Check root filesystem usage
    local root_usage=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')
    log_msg "info" "Root filesystem usage: ${root_usage}%"
    
    if [ "$root_usage" -gt 90 ]; then
        log_msg "warn" "Root filesystem is ${root_usage}% full (>90%)"
    fi
    
    # Check boot partition
    if [ -d "/boot" ]; then
        local boot_usage=$(df -h /boot | tail -1 | awk '{print $5}' | sed 's/%//')
        log_msg "info" "Boot partition usage: ${boot_usage}%"
        
        if [ "$boot_usage" -gt 80 ]; then
            log_msg "warn" "Boot partition is ${boot_usage}% full (>80%)"
        fi
    fi
}

# Main execution
main() {
    log_msg "info" "======================================"
    log_msg "info" "System Health Check Started"
    log_msg "info" "======================================"
    
    check_lcd_files
    check_lcd_hardware
    check_buzzer_gpio
    check_services
    check_network
    check_storage
    
    log_msg "info" "======================================"
    log_msg "info" "System Health Check Completed"
    log_msg "info" "======================================"
}

# Run main function
main
