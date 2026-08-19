================================================================================
                     YOCTO GOMULU LINUX SISTEMI
                           Hosgeldiniz Efendim / Welcome
================================================================================

COK DILLI DESTEK | MULTI-LANGUAGE SUPPORT
------------------------------------------
Bu yardim dosyasi farkli dillerde mevcuttur:

  help en    - English (Ingilizce)
  help tr    - Turkce (suanki)
  help de    - Deutsch (Almanca)
  help fr    - Francais (Fransizca)
  help ar    - Arabic (Arapca)
  help hi    - Hindi (Hintce)

Ornek: Ingilizce icin 'help en' yazin

================================================================================

Bu cihaz Yocto Project ile olusturulmus gomulu bir Linux sistemidir.

## TEMEL KOMUTLAR

- help [dil]       : Bu yardim mesajini belirtilen dilde gosterir
- telemetry        : Telemetri servisini kontrol eder
- buzzererror      : Hata bildirimleri icin buzzer'i kontrol eder
- systemctl        : Sistem servislerini yonetir

## TELEMETRY SERVISI

Cihaz metriklerini periyodik olarak uzak sunucuya gonderir.

### Kullanim:
  telemetry [SECENEK]

### Secenekler:
  -s, --stop      : Servisi durdur
  -c, --continue  : Servisi baslat/devam ettir
  -e, --enable    : Servisi aktif et ve baslat
  -d, --disable   : Servisi devre disi birak ve durdur
  -r, --restart   : Servisi yeniden baslat
  -h, --help      : Yardim mesajini goster

### Ornekler:
  telemetry --stop       # Servisi durdur
  telemetry --enable     # Aktif et ve baslat
  telemetry --restart    # Yeniden baslat

## BUZZER HATA SERVISI

GPIO pinine bagli buzzer'i hata bildirimleri icin kontrol eder.

### Kullanim:
  buzzererror [SECENEK]

### Secenekler:
  -e, --enable  : Buzzer'i aktif et
  -d, --disable : Buzzer'i devre disi birak
  -h, --help    : Yardim mesajini goster

### Ornekler:
  buzzererror --enable   # Buzzer'i aktif et
  buzzererror -d         # Buzzer'i devre disi birak
  buzzererror 2          # 2 kere bip (script'lerde)

## ONEMLI DOSYALAR

- /home/root/resize-rootfs.log  : Root dosya sistemi boyutlandirma log'u
- /etc/README.*.md              : Yardim dosyalari (cok dilli)

## SISTEM BILGISI

Sistem detaylari:
  uname -a        # Kernel surum bilgisi
  df -h           # Disk kullanimi
  free -h         # RAM kullanimi
  uptime          # Sistem calisma suresi
  info            # Ozel kirpi ASCII sanatli sistem bilgisi (neofetch)

================================================================================
Daha fazla bilgi icin: telemetry --help
================================================================================

