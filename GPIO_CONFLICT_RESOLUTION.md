# GPIO Conflict Resolution - LCD and Buzzer

## Overview
This document describes the GPIO pin conflict between the 3.5" LCD display and the buzzer-error service, and how to resolve it.

## The Conflict

### GPIO17 Usage
- **LCD Display (tft35a overlay)**: Uses GPIO17 for LCD control signals
- **Buzzer Error Service**: Default configuration uses GPIO17 for buzzer control

When both the LCD and buzzer-error service attempt to use GPIO17 simultaneously, conflicts occur that can cause:
- LCD malfunction or white screen
- Buzzer failure
- System instability
- Service startup failures

## Automatic Detection

The buzzer-error service now includes automatic conflict detection:

1. **At service startup**: Checks if `/dev/fb2` exists (LCD present)
2. **Driver detection**: Checks if `fb_ili9486` kernel module is loaded
3. **GPIO validation**: Prevents GPIO17 use when LCD is detected
4. **Clear error messages**: Informs user of conflict and suggests alternatives

## Resolution Options

### Option 1: Automatic (Recommended)
The system is configured to automatically prevent conflicts:

- **LCD present**: `lcd-display.service` starts, uses GPIO17
- **LCD absent**: `buzzer-error.service` can use GPIO17
- Services include conditions to prevent simultaneous use

### Option 2: Manual GPIO Reconfiguration

If you have the LCD attached, reconfigure the buzzer to use a different GPIO pin:

```bash
# Check current configuration and conflicts
buzzererror --check

# Change to alternative GPIO pin (permanently)
buzzererror --gpio 22

# Restart buzzer service to apply changes
systemctl restart buzzer-error.service
```

**Suggested alternative GPIO pins:**
- GPIO22 (Physical pin 15)
- GPIO23 (Physical pin 16)
- GPIO24 (Physical pin 18)
- GPIO25 (Physical pin 22)
- GPIO27 (Physical pin 13)

### Option 3: Disable Buzzer When Using LCD

If you don't need the buzzer while using the LCD:

```bash
# Disable buzzer service
systemctl disable buzzer-error.service
systemctl stop buzzer-error.service
```

## New Features in buzzererror Command

### Command-line Options

```bash
buzzererror [OPTION] [VALUE]

Options:
  -e, --enable         Enable buzzer
  -d, --disable        Disable buzzer
  -g, --gpio <pin>     Set GPIO pin number (permanently)
  -c, --check          Check current GPIO configuration and conflicts
  -h, --help           Show this help
```

### Usage Examples

```bash
# Check for conflicts
buzzererror --check

# Change GPIO pin to avoid conflict
buzzererror --gpio 22

# Enable/disable buzzer
buzzererror --enable
buzzererror --disable

# Show help and current configuration
buzzererror --help
```

### Conflict Check Output

The `--check` option provides detailed information:

```
Buzzer Configuration Check
==========================
GPIO Pin: 17
Config file: /etc/buzzer-pin.conf

Buzzer Status: ENABLED

LCD Status: DETECTED (/dev/fb2 exists)
LCD Driver: fb_ili9486 (uses GPIO17)

GPIO17: Already exported
  Direction: out

Conflict Check: WARNING - Conflicts detected (see above)
```

## Service Behavior

### buzzer-error.service
- Checks for GPIO conflicts at startup
- Fails with clear error message if conflict detected
- Automatically retries after 10 seconds (allows time for reconfiguration)
- Restarts successfully after GPIO reconfiguration

### lcd-display.service
- Only starts if `/dev/fb2` exists (LCD detected)
- Prevents startup when LCD not present
- Avoids unnecessary GPIO17 reservation

## Configuration File

Location: `/etc/buzzer-pin.conf`

```bash
# Buzzer GPIO pin configuration
# Physical pin 11 = GPIO 17
# 
# WARNING: GPIO17 conflicts with 3.5" LCD display (tft35a overlay)
# If you have the LCD attached, use a different GPIO pin:
#   Suggested alternatives: 22, 23, 24, 25, 27
# 
# To change GPIO pin permanently:
#   buzzererror --gpio <pin_number>
#
BUZZER_GPIO_PIN=17
```

## Troubleshooting

### Buzzer service fails to start
1. Check for GPIO conflicts:
   ```bash
   buzzererror --check
   ```

2. If LCD is present and using GPIO17, reconfigure:
   ```bash
   buzzererror --gpio 22
   systemctl restart buzzer-error.service
   ```

3. Check service status:
   ```bash
   systemctl status buzzer-error.service
   ```

### LCD not working
1. Verify LCD is detected:
   ```bash
   ls -l /dev/fb2
   ```

2. Check if device tree overlay is loaded:
   ```bash
   lsmod | grep fb_ili9486
   ```

3. Verify config.txt includes LCD overlay:
   ```bash
   grep tft35a /boot/config.txt
   ```

### Both services showing conflicts
1. Check which GPIO pins are in use:
   ```bash
   ls /sys/class/gpio/
   ```

2. Manually unexport conflicting GPIO:
   ```bash
   echo 17 > /sys/class/gpio/unexport
   ```

3. Restart services:
   ```bash
   systemctl restart buzzer-error.service
   systemctl restart lcd-display.service
   ```

## Technical Details

### GPIO Pin Mapping (BCM)
| BCM GPIO | Physical Pin | Alternative Function |
|----------|--------------|---------------------|
| GPIO17   | 11           | LCD control (tft35a)|
| GPIO22   | 15           | Available           |
| GPIO23   | 16           | Available           |
| GPIO24   | 18           | Available           |
| GPIO25   | 22           | Available (was LCD conflict) |
| GPIO27   | 13           | Available           |

### Device Tree Overlays
- **tft35a-overlay.dtb**: Combined LCD and touchscreen overlay
  - Uses GPIO17 for LCD control
  - Uses SPI for display data
  - Uses GPIO25 for touchscreen interrupt (if enabled)

### Kernel Modules
- **fb_ili9486**: Framebuffer driver for ILI9486 LCD chip
- **fbtft**: Framebuffer TFT driver subsystem
- **ads7846**: Touchscreen controller driver

## Build System Integration

The conflict detection is integrated into the Yocto build:

### Modified Files
1. `recipes-support/buzzer-error/files/buzzererror`
   - Added `check_gpio_conflict()` function
   - Added `--gpio/-g` parameter support
   - Added `--check/-c` status display
   - Added configuration persistence

2. `recipes-support/buzzer-error/files/buzzer-error.sh`
   - Added GPIO conflict detection at service start
   - Added error handling for GPIO conflicts
   - Added automatic retry mechanism

3. `recipes-support/buzzer-error/files/buzzer-error.service`
   - Added restart on failure
   - Added documentation comments

4. `recipes-support/buzzer-error/files/buzzer-pin.conf`
   - Added conflict warning comments
   - Added alternative GPIO suggestions

5. `recipes-apps/lcd-touchscreen/files/lcd-display.service`
   - Added `ConditionPathExists=/dev/fb2`
   - Only starts when LCD is physically present

### Recipe Files
- `recipes-support/buzzer-error/buzzer-error_git.bb`: No changes needed
- `recipes-apps/lcd-touchscreen/lcd-touchscreen_1.0.bb`: No changes needed

## Testing

### Test Scenario 1: LCD Present
1. Boot system with LCD connected
2. Verify `/dev/fb2` exists
3. Check `lcd-display.service` is active
4. Check `buzzer-error.service` fails with GPIO17 conflict
5. Reconfigure buzzer: `buzzererror --gpio 22`
6. Restart: `systemctl restart buzzer-error.service`
7. Verify both services active

### Test Scenario 2: LCD Absent
1. Boot system without LCD
2. Verify `/dev/fb2` does not exist
3. Check `lcd-display.service` is inactive
4. Check `buzzer-error.service` is active on GPIO17
5. Buzzer should function normally

### Test Scenario 3: Manual Check
1. Run: `buzzererror --check`
2. Verify output shows correct status
3. If conflict detected, follow suggested resolution

## References

- **LCD Documentation**: `/home/s2344/yocto/poky/meta-spiny/recipes-bsp/bootfiles/rpi-config/lcd-35.txt`
- **Buzzer Recipe**: `/home/s2344/yocto/poky/meta-spiny/recipes-support/buzzer-error/buzzer-error_git.bb`
- **LCD Recipe**: `/home/s2344/yocto/poky/meta-spiny/recipes-apps/lcd-touchscreen/lcd-touchscreen_1.0.bb`
- **goodtft LCD-show**: https://github.com/goodtft/LCD-show.git

## Summary

The GPIO conflict resolution provides:
- ✅ Automatic conflict detection
- ✅ Clear error messages
- ✅ Easy reconfiguration via command-line
- ✅ Persistent configuration storage
- ✅ Service-level conflict prevention
- ✅ Comprehensive status checking

Users can now safely use both LCD and buzzer by simply reconfiguring the buzzer GPIO pin when needed.
