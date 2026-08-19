================================================================================
                     YOCTO EMBEDDED LINUX SYSTEM
                           Welcome / Hosgeldiniz
================================================================================

MULTI-LANGUAGE SUPPORT | COK DILLI DESTEK
------------------------------------------
This help is available in multiple languages:

  help en    - English (current)
  help tr    - Turkce (Turkish)
  help de    - Deutsch (German)
  help fr    - Francais (French)
  help ar    - Arabic
  help hi    - Hindi

Example: Type 'help tr' for Turkish version

================================================================================

This device is an embedded Linux system built with Yocto Project.

## BASIC COMMANDS

- help [lang]      : Show this help message in specified language
- telemetry        : Control the telemetry service
- buzzererror      : Control buzzer for error notifications
- systemctl        : Manage system services

## TELEMETRY SERVICE

Periodically sends device metrics to remote endpoint.

### Usage:
  telemetry [OPTION]

### Options:
  -s, --stop      : Stop the service
  -c, --continue  : Start/continue the service
  -e, --enable    : Enable and start the service
  -d, --disable   : Disable and stop the service
  -r, --restart   : Restart the service
  -h, --help      : Show help message

### Examples:
  telemetry --stop       # Stop service
  telemetry --enable     # Enable and start
  telemetry --restart    # Restart service

## BUZZER ERROR SERVICE

Controls buzzer connected to GPIO pin for error notifications.

### Usage:
  buzzererror [OPTION]

### Options:
  -e, --enable  : Enable buzzer
  -d, --disable : Disable buzzer
  -h, --help    : Show help message

### Examples:
  buzzererror --enable   # Enable buzzer
  buzzererror -d         # Disable buzzer
  buzzererror 2          # Beep 2 times (in scripts)

## IMPORTANT FILES

- /home/root/resize-rootfs.log  : Root filesystem resize log
- /etc/README.*.md              : Help files (multi-language)
- /var/log/ip-address.log       : Current IP address log

## CONNECTING TO THE SYSTEM

After boot, find the system IP address:
  cat /var/log/ip-address.log    # Check IP log
  ip addr show                   # Show all network interfaces
  hostname -I                    # Show IP addresses

SSH connection (replace X.X.X.X with actual IP):
  ssh root@X.X.X.X

Or use mDNS (if supported by your network):
  ssh root@SpinyOS-RaspberryPi4.local

## SYSTEM INFORMATION

System details:
  uname -a        # Kernel version
  df -h           # Disk usage
  free -h         # RAM usage
  uptime          # System uptime
  info            # System info with custom hedgehog ASCII art (neofetch)

================================================================================
For more information: telemetry --help
================================================================================

