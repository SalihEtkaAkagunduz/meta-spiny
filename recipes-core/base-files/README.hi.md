================================================================================
                     YOCTO EMBEDDED LINUX SYSTEM
                           Welcome / Swaagat
================================================================================

MULTI-LANGUAGE SUPPORT | Bahu-Bhaasha Samarthan
------------------------------------------------
This help is available in multiple languages:

  help en    - English (Angrezi)
  help tr    - Turkce (Turkish)
  help de    - Deutsch (German)
  help fr    - Francais (French)
  help ar    - Arabic (Arabi)
  help hi    - Hindi (vartamaan)

Udaharan: Angrezi ke liye 'help en' likhein

================================================================================

Yah upakaran Yocto Project ke saath banaya gaya ek embedded Linux system hai.

## MOOL AADESH (BASIC COMMANDS)

- help [bhaasha]   : Is sahayata sandesh ko nirdishta bhaasha mein dikhaaen
- telemetry        : Telemetry seva ko niyantrit karein
- buzzererror      : Galati adhirtiyon ke liye buzzer ko niyantrit karein
- systemctl        : System sevon ko prabandhit karein

## TELEMETRY SEVA (TELEMETRY SERVICE)

Upakaran metrics ko niyamit roop se door ke endpoint par bhejta hai.

### Upayog (Usage):
  telemetry [VIKALP]

### Vikalp (Options):
  -s, --stop      : Seva ko band karein
  -c, --continue  : Seva ko shuru/jaari rakhein
  -e, --enable    : Seva ko sakriya aur shuru karein
  -d, --disable   : Seva ko nishkriya aur band karein
  -r, --restart   : Seva ko punah shuru karein
  -h, --help      : Sahayata sandesh dikhaaen

### Udaharan (Examples):
  telemetry --stop       # Seva band karein
  telemetry --enable     # Sakriya aur shuru karein
  telemetry --restart    # Punah shuru karein

## BUZZER GALATI SEVA (BUZZER ERROR SERVICE)

Galati adhirtiyon ke liye GPIO pin se judi buzzer ko niyantrit karein.

### Upayog (Usage):
  buzzererror [OPTION]

### Vikalp (Options):
  test          : Buzzer ko 3 beep ke saath test karein
  -e, --enable  : Buzzer ko sakriya karein
  -d, --disable : Buzzer ko nishkriya karein
  -h, --help    : Sahayata sandesh dikhaaen

### Udaharan (Examples):
  buzzererror test       # 3 beep ke saath test karein
  buzzererror --enable   # Buzzer ko sakriya karein
  buzzererror -d         # Buzzer ko nishkriya karein

## MAHATVAPURNA FILE (IMPORTANT FILES)

- /home/root/resize-rootfs.log  : Root filesystem resize log
- /etc/README.*.md              : Sahayata files (bahu-bhaasha)

## SYSTEM JAANKARI (SYSTEM INFORMATION)

System vivaran:
  uname -a        # Kernel sansakaran
  df -h           # Disk upayog
  free -h         # RAM upayog
  uptime          # System chalane ka samay
  info            # Kustom hedgehog ASCII art ke saath system jaankari (neofetch)

================================================================================
Adhik jaankari ke liye: telemetry --help
================================================================================

