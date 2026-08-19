# Nokia 5110 LCD Display - Hızlı Başlangıç Kılavuzu

## Bağlantı Tablosu

Nokia 5110 ekranınızı aşağıdaki şemaya göre Raspberry Pi'ye bağlayın:

```
┌─────────────────┐         ┌──────────────────┐
│ Raspberry Pi    │         │   Nokia 5110     │
├─────────────────┤         ├──────────────────┤
│ Pin 1  (3.3V)   │ ─────── │ VCC              │
│ Pin 6  (GND)    │ ─────── │ GND              │
│ Pin 23 (GPIO11) │ ─────── │ CLK (SCLK)       │
│ Pin 19 (GPIO10) │ ─────── │ DIN (MOSI)       │
│ Pin 24 (GPIO8)  │ ─────── │ CE  (CS)         │
│ Pin 16 (GPIO23) │ ─────── │ DC  (D/C)        │
│ Pin 18 (GPIO24) │ ─────── │ RST (Reset)      │
│ Pin 22 (GPIO25) │ ─────── │ LIGHT (LED)      │
└─────────────────┘         └──────────────────┘
```

## ⚠️ ÖNEMLİ UYARILAR

1. **Nokia 5110 3.3V ile çalışır!** 5V bağlarsanız ekranınız yanar!
2. SPI'yi etkinleştirmeyi unutmayın
3. Kabloları mümkün olduğunca kısa tutun

## Adım 1: SPI Etkinleştirme

```bash
# Yocto image'da zaten etkin olmalı
# Kontrol için:
ls /dev/spi*

# Eğer yoksa config.txt'ye ekleyin:
# dtparam=spi=on
```

## Adım 2: İlk Test

```bash
# Basit metin gösterimi
nokia5110-text.py "Merhaba!"

# Demo programı
nokia5110-demo.py

# Sistem monitörü
nokia5110-monitor.py
```

## Kullanım Örnekleri

### 1. Ekrana Metin Yazdırma

```bash
# Tek satır
nokia5110-text.py "Hello World"

# Çok satırlı
nokia5110-text.py "Satir 1\nSatir 2\nSatir 3"

# Türkçe karakter
nokia5110-text.py "Merhaba\nDünya!"
```

### 2. Python'dan Kullanım

```python
#!/usr/bin/env python3
from nokia5110_driver import Nokia5110
import time

# Başlat
lcd = Nokia5110()

# Temizle ve yaz
lcd.clear()
lcd.draw_text(0, 0, "Raspberry", 1)
lcd.draw_text(0, 10, "Pi", 1)
lcd.draw_text(0, 20, "Nokia 5110", 1)

# Ekrana gönder
lcd.display()

time.sleep(5)
lcd.cleanup()
```

### 3. Saat Gösterimi

```python
#!/usr/bin/env python3
from nokia5110_driver import Nokia5110
import time

lcd = Nokia5110()

try:
    while True:
        lcd.clear()
        current_time = time.strftime("%H:%M:%S")
        lcd.draw_text_centered(20, current_time, 1)
        lcd.display()
        time.sleep(1)
except KeyboardInterrupt:
    lcd.cleanup()
```

### 4. Sıcaklık Gösterimi

```python
#!/usr/bin/env python3
from nokia5110_driver import Nokia5110

def get_cpu_temp():
    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
        return float(f.read().strip()) / 1000.0

lcd = Nokia5110()
lcd.clear()

temp = get_cpu_temp()
lcd.draw_text_centered(10, "CPU SICAKLIK", 1)
lcd.draw_text_centered(25, f"{temp:.1f} C", 1)
lcd.display()

input("Devam etmek için Enter'a basın...")
lcd.cleanup()
```

## Kontrast Ayarlama

Ekran çok soluk veya çok koyu görünüyorsa kontrastı ayarlayın:

```python
from nokia5110_driver import Nokia5110

lcd = Nokia5110(contrast=0x40)  # 0x00-0x7F arası
# veya
lcd.set_contrast(0x40)
```

Önerilen değerler:
- **Çok açık**: 0x30
- **Normal**: 0x3F (varsayılan)
- **Koyu**: 0x50

## Pin Yapılandırmasını Değiştirme

Farklı pinler kullanmak isterseniz:

```python
lcd = Nokia5110(
    rst=24,   # Reset pin
    dc=23,    # Data/Command pin
    led=25,   # LED pin (None = arka ışık yok)
    spi_bus=0,
    spi_device=0
)
```

## Sorun Giderme

### Ekran hiçbir şey göstermiyor

1. **Bağlantıları kontrol edin**
   ```bash
   # GPIO pinlerini kontrol et
   gpio readall
   ```

2. **SPI çalışıyor mu?**
   ```bash
   ls -l /dev/spi*
   # Görmelisiniz: /dev/spidev0.0
   ```

3. **Voltaj doğru mu?**
   - Multimetre ile VCC pininde 3.3V ölçün
   - 5V BAĞLAMAYIN!

4. **Kontrast düşük mü?**
   ```python
   lcd.set_contrast(0x50)  # Daha koyu
   ```

### "Permission denied" hatası

```bash
# Kullanıcıyı gruplara ekle
sudo usermod -a -G spi,gpio $USER

# Çıkış yap ve tekrar giriş yap
```

### Ekran titriyor/bozuk görüntü

1. Kabloları kısaltın (maksimum 10-15 cm)
2. GND bağlantısını kontrol edin
3. SPI hızını düşürün:
   ```python
   # nokia5110_driver.py dosyasında
   DEFAULT_SPI_MAX_SPEED = 2000000  # 2 MHz
   ```

### Arka ışık çalışmıyor

```python
# Arka ışığı manuel kontrol et
lcd.set_backlight(True)   # Aç
lcd.set_backlight(False)  # Kapat
```

## API Fonksiyonları

### Temel Fonksiyonlar
```python
lcd.clear()                    # Ekranı temizle
lcd.display()                  # Buffer'ı ekrana gönder
lcd.set_contrast(0x3F)         # Kontrast ayarla (0-127)
lcd.set_backlight(True)        # Arka ışık aç/kapa
lcd.invert_display(True)       # Renkleri ters çevir
lcd.cleanup()                  # Kaynakları temizle
```

### Çizim Fonksiyonları
```python
lcd.set_pixel(x, y, 1)                    # Piksel çiz
lcd.draw_line(x0, y0, x1, y1, 1)          # Çizgi çiz
lcd.draw_rect(x, y, w, h, 1)              # Dikdörtgen çiz
lcd.fill_rect(x, y, w, h, 1)              # Dolu dikdörtgen
lcd.draw_char(x, y, ord('A'), 1)          # Karakter yaz
lcd.draw_text(x, y, "Metin", 1)           # Metin yaz
lcd.draw_text_centered(y, "Metin", 1)     # Ortalı metin
```

### Koordinat Sistemi
```
(0,0) ────────────────► X (83)
  │
  │   ┌─────────────────┐
  │   │                 │
  │   │   84 x 48       │
  │   │   piksel        │
  │   │                 │
  │   └─────────────────┘
  ▼
  Y (47)
```

## Örnek Projeler

### Logo Gösterme

```python
from nokia5110_driver import Nokia5110

lcd = Nokia5110()
lcd.clear()

# 8x8 kalp logosu
logo = [
    0b01101100,
    0b11111110,
    0b11111110,
    0b11111110,
    0b01111100,
    0b00111000,
    0b00010000,
    0b00000000,
]

# Ortaya çiz
for y, byte in enumerate(logo):
    for x in range(8):
        if byte & (1 << (7-x)):
            lcd.set_pixel(38 + x, 20 + y, 1)

lcd.display()
```

### Çubuk Grafik

```python
from nokia5110_driver import Nokia5110
import random

lcd = Nokia5110()

for _ in range(10):
    lcd.clear()
    
    # 5 rastgele çubuk
    for i in range(5):
        height = random.randint(5, 40)
        lcd.fill_rect(i * 16 + 2, 48 - height, 14, height, 1)
    
    lcd.display()
    time.sleep(1)

lcd.cleanup()
```

## Performans İpuçları

1. **display() çağrısını minimize edin** - Her değişiklikten sonra değil, toplu çizimlerin sonunda çağırın
2. **Animasyonlar için**, sadece değişen kısımları güncelleyin
3. **SPI hızını optimize edin** - Kararlı çalışma için 4 MHz iyi bir değer

## Yardım

Daha fazla bilgi için:
```bash
# README dosyasını okuyun
cat /usr/share/doc/nokia5110/README-NOKIA5110.md

# Demo programını inceleyin
cat /usr/bin/nokia5110-demo.py
```

## Yararlı Linkler

- PCD8544 Datasheet
- Raspberry Pi SPI Dokümantasyonu
- Nokia 5110 Pinout Şeması

---

**Keyifli kodlamalar! 🚀**
