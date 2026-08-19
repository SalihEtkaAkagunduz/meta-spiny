================================================================================
                     YOCTO EMBEDDED LINUX SYSTEM
                           Welcome / Marhaban
================================================================================

MULTI-LANGUAGE SUPPORT | Da'm Muta'addid al-Lughat
---------------------------------------------------
This help is available in multiple languages:

  help en    - English
  help tr    - Turkce (Turkish)
  help de    - Deutsch (German)
  help fr    - Francais (French)
  help ar    - Arabic (current)
  help hi    - Hindi

Example: Type 'help en' for English version

================================================================================

This device is an embedded Linux system built with Yocto Project.

## AL-AWAMIR AL-ASASIYAH (BASIC COMMANDS)

- help [language]  : Show this help message in specified language
- telemetry        : Control the telemetry service
- buzzererror      : Control buzzer for error notifications
- systemctl        : Manage system services

## KHIDMAT AL-TELEMETRY (TELEMETRY SERVICE)

Periodically sends device metrics to remote endpoint.

### Al-Isti'mal (Usage):
  telemetry [OPTION]

### Al-Khiyarat (Options):
  -s, --stop      : Stop the service (Iqaf al-khidmah)
  -c, --continue  : Start/continue the service (Tabda' al-khidmah)
  -e, --enable    : Enable and start the service (Taf'il wa tabda')
  -d, --disable   : Disable and stop the service (Ta'til wa iqaf)
  -r, --restart   : Restart the service (I'adat tabda')
  -h, --help      : Show help message (Idhar rasa'il al-musa'adah)

### Amthilah (Examples):
  telemetry --stop       # Stop service
  telemetry --enable     # Enable and start
  telemetry --restart    # Restart service

## KHIDMAT KHATA' BUZZER (BUZZER ERROR SERVICE)

Yudir al-buzzer al-muttasil bi-dabbus GPIO li-ikhbarat al-khata'.

### Al-Istikhdam (Usage):
  buzzererror [OPTION]

### Al-Khiyarat (Options):
  test          : Ikhtibar al-buzzer bi-3 aswaat
  -e, --enable  : Taf'il al-buzzer
  -d, --disable : Ta'til al-buzzer
  -h, --help    : Idhar rasa'il al-musa'adah

### Amthilah (Examples):
  buzzererror test       # Ikhtibar bi-3 aswaat
  buzzererror --enable   # Taf'il al-buzzer
  buzzererror -d         # Ta'til al-buzzer

## MALAFF MUHIMMAH (IMPORTANT FILES)

- /home/root/resize-rootfs.log  : Root filesystem resize log
- /etc/README.*.md              : Help files (multi-language)

## MA'LUMAT AL-NIDHAM (SYSTEM INFORMATION)

System details:
  uname -a        # Kernel version (Isdar al-kernel)
  df -h           # Disk usage (Isti'mal al-qurs)
  free -h         # RAM usage (Isti'mal al-RAM)
  uptime          # System uptime (Waqt tashghil al-nidham)
  info            # Ma'lumat al-nidham bi-fann ASCII mukhtas kirpi (neofetch)

================================================================================
For more information: telemetry --help
================================================================================

