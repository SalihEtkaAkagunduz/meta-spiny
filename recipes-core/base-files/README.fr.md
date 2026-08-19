================================================================================
                     SYSTEME LINUX EMBARQUE YOCTO
                           Bienvenue / Welcome
================================================================================

SUPPORT MULTILINGUE | MULTI-LANGUAGE SUPPORT
---------------------------------------------
Cette aide est disponible en plusieurs langues:

  help en    - English (Anglais)
  help tr    - Turkce (Turc)
  help de    - Deutsch (Allemand)
  help fr    - Francais (actuel)
  help ar    - Arabic (Arabe)
  help hi    - Hindi

Exemple: Tapez 'help en' pour la version anglaise

================================================================================

Cet appareil est un systeme Linux embarque construit avec Yocto Project.

## COMMANDES DE BASE

- help [langue]    : Afficher ce message d'aide dans la langue specifiee
- telemetry        : Controler le service de telemetrie
- buzzererror      : Controler le buzzer pour les notifications d'erreur
- systemctl        : Gerer les services systeme

## SERVICE DE TELEMETRIE

Envoie periodiquement les metriques de l'appareil a un point distant.

### Utilisation:
  telemetry [OPTION]

### Options:
  -s, --stop      : Arreter le service
  -c, --continue  : Demarrer/continuer le service
  -e, --enable    : Activer et demarrer le service
  -d, --disable   : Desactiver et arreter le service
  -r, --restart   : Redemarrer le service
  -h, --help      : Afficher le message d'aide

### Exemples:
  telemetry --stop       # Arreter le service
  telemetry --enable     # Activer et demarrer
  telemetry --restart    # Redemarrer le service

## SERVICE D'ERREUR BUZZER

Controle le buzzer connecte a la broche GPIO pour les notifications d'erreur.

### Utilisation:
  buzzererror [OPTION]

### Options:
  test          : Tester le buzzer avec 3 bips
  -e, --enable  : Activer le buzzer
  -d, --disable : Desactiver le buzzer
  -h, --help    : Afficher le message d'aide

### Exemples:
  buzzererror test       # Tester avec 3 bips
  buzzererror --enable   # Activer le buzzer
  buzzererror -d         # Desactiver le buzzer

## FICHIERS IMPORTANTS

- /home/root/resize-rootfs.log  : Journal de redimensionnement du systeme de fichiers racine
- /etc/README.*.md              : Fichiers d'aide (multilingue)

## INFORMATIONS SYSTEME

Details du systeme:
  uname -a        # Version du noyau
  df -h           # Utilisation du disque
  free -h         # Utilisation de la RAM
  uptime          # Temps de fonctionnement du systeme
  info            # Infos systeme avec art ASCII personnalise herisson (neofetch)

================================================================================
Pour plus d'informations: telemetry --help
================================================================================

