================================================================================
                     YOCTO EMBEDDED LINUX SYSTEM
                           Willkommen / Welcome
================================================================================

MEHRSPRACHIGE UNTERSTUTZUNG | MULTI-LANGUAGE SUPPORT
-----------------------------------------------------
Diese Hilfe ist in mehreren Sprachen verfugbar:

  help en    - English (Englisch)
  help tr    - Turkce (Turkisch)
  help de    - Deutsch (aktuell)
  help fr    - Francais (Franzosisch)
  help ar    - Arabic (Arabisch)
  help hi    - Hindi

Beispiel: Geben Sie 'help en' fur Englisch ein

================================================================================

Dieses Gerat ist ein eingebettetes Linux-System, das mit dem Yocto Project erstellt wurde.

## GRUNDLEGENDE BEFEHLE

- help [sprache]   : Diese Hilfemeldung in der angegebenen Sprache anzeigen
- telemetry        : Telemetriedienst steuern
- buzzererror      : Summer fur Fehlerbenachrichtigungen steuern
- systemctl        : Systemdienste verwalten

## TELEMETRIE-DIENST

Sendet periodisch Geratemetriken an einen Remote-Endpunkt.

### Verwendung:
  telemetry [OPTION]

### Optionen:
  -s, --stop      : Dienst stoppen
  -c, --continue  : Dienst starten/fortsetzen
  -e, --enable    : Dienst aktivieren und starten
  -d, --disable   : Dienst deaktivieren und stoppen
  -r, --restart   : Dienst neu starten
  -h, --help      : Hilfemeldung anzeigen

### Beispiele:
  telemetry --stop       # Dienst stoppen
  telemetry --enable     # Aktivieren und starten
  telemetry --restart    # Dienst neu starten

## SUMMER-FEHLERDIENST

Steuert Summer an GPIO-Pin fur Fehlerbenachrichtigungen.

### Verwendung:
  buzzererror [OPTION]

### Optionen:
  test          : Summer mit 3 Signaltönen testen
  -e, --enable  : Summer aktivieren
  -d, --disable : Summer deaktivieren
  -h, --help    : Hilfemeldung anzeigen

### Beispiele:
  buzzererror test       # Mit 3 Signaltönen testen
  buzzererror --enable   # Summer aktivieren
  buzzererror -d         # Summer deaktivieren

## WICHTIGE DATEIEN

- /home/root/resize-rootfs.log  : Root-Dateisystem Resize-Protokoll
- /etc/README.*.md              : Hilfedateien (mehrsprachig)

## SYSTEMINFORMATIONEN

Systemdetails:
  uname -a        # Kernel-Version
  df -h           # Festplattennutzung
  free -h         # RAM-Nutzung
  uptime          # System-Betriebszeit
  info            # Systeminfo mit benutzerdefiniertem Igel-ASCII-Art (neofetch)

================================================================================
Fur weitere Informationen: telemetry --help
================================================================================

