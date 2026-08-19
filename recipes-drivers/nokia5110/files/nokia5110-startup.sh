#!/bin/bash
# Nokia 5110 startup display script

# Check if SPI device exists
if [ ! -e "/dev/spidev0.0" ]; then
    echo "Nokia 5110: SPI device not available, skipping display initialization"
    echo "Run 'systemctl restart nokia-spi-enabler.service' and reboot if needed"
    exit 0
fi

python3 << 'EOF'
import sys
sys.path.insert(0, "/usr/bin")

try:
    from nokia5110_driver import Nokia5110
    import time
    import socket
    
    # Initialize display
    lcd = Nokia5110()
    lcd.clear()
    
    # Show SpinyOS logo
    lcd.draw_text_centered(5, "SpinyOS")
    lcd.draw_text_centered(15, "Raspberry")
    lcd.draw_text_centered(25, "Pi 4")
    
    # Get hostname
    hostname = socket.gethostname()
    lcd.draw_text(0, 38, hostname[:14])
    
    lcd.display()
    
    # Keep display on (don't cleanup)
    # User can update display later with other scripts
    
except Exception as e:
    print(f"Nokia 5110 startup error: {e}")
    sys.exit(0)  # Exit 0 to not fail the service

EOF
