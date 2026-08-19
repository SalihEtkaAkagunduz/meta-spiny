# Buzzer error function for system-wide use
buzzererror_system() {
    # Check if buzzer is disabled
    if [ -f "/tmp/buzzer_disabled" ]; then
        return 0
    fi
    
    local count=${1:-1}  # Default to 1 beep if no parameter given
    
    for ((i=1; i<=count; i++)); do
        /usr/sbin/buzzer-error.sh beep 0.2
        if [ $i -lt $count ]; then
            sleep 0.1
        fi
    done
}

# Alias for backward compatibility
alias buzzererror='buzzererror_system'