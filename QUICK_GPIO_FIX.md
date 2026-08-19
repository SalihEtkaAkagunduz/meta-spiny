# Quick Reference: Buzzer GPIO Reconfiguration

## Problem
LCD and buzzer both use GPIO17 → Conflict!

## Solution
Change buzzer to different GPIO pin.

## Quick Commands

### Check for conflicts
```bash
buzzererror --check
```

### Change GPIO pin (pick one)
```bash
buzzererror --gpio 22  # Physical pin 15
buzzererror --gpio 23  # Physical pin 16
buzzererror --gpio 24  # Physical pin 18
buzzererror --gpio 25  # Physical pin 22
buzzererror --gpio 27  # Physical pin 13
```

### Restart buzzer service
```bash
systemctl restart buzzer-error.service
```

### Verify both services running
```bash
systemctl status lcd-display.service
systemctl status buzzer-error.service
```

## Physical Pin Reference

| BCM GPIO | Physical Pin | Status |
|----------|--------------|--------|
| GPIO17   | 11          | Used by LCD (don't use) |
| GPIO22   | 15          | ✅ Available |
| GPIO23   | 16          | ✅ Available |
| GPIO24   | 18          | ✅ Available |
| GPIO25   | 22          | ✅ Available |
| GPIO27   | 13          | ✅ Available |

## If Buzzer Not Needed
```bash
systemctl disable buzzer-error.service
systemctl stop buzzer-error.service
```

## Help
```bash
buzzererror --help
```
