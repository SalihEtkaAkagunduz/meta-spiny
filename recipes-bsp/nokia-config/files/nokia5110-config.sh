#!/bin/sh
# Nokia 5110 runtime configuration
# This ensures SPI kernel modules are loaded

# Load SPI modules if not already loaded
if ! lsmod | grep -q spi_bcm2835; then
    modprobe spi_bcm2835 2>/dev/null || true
fi

# Ensure SPI devices are accessible
if [ -e /dev/spidev0.0 ]; then
    chmod 666 /dev/spidev0.0 2>/dev/null || true
fi

if [ -e /dev/spidev0.1 ]; then
    chmod 666 /dev/spidev0.1 2>/dev/null || true
fi
