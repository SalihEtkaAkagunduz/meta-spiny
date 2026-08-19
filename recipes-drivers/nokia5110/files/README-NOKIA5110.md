# Nokia 5110 LCD Display for Raspberry Pi

Nokia 5110 (PCD8544) LCD ekran sürücüsü ve örnek uygulamalar.

## Özellikler

- **Ekran Boyutu**: 84x48 piksel
- **Renk**: Monokrom (Siyah/Beyaz)
- **Sürücü**: PCD8544
- **Arayüz**: SPI
- **Arka Işık**: LED (isteğe bağlı)

## Pin Bağlantıları

Nokia 5110 ekranı Raspberry Pi'ye SPI üzerinden bağlanır:

| Nokia 5110 Pin | Raspberry Pi Pin | BCM GPIO | Açıklama |
|---------------|------------------|----------|----------|
| RST (Reset)   | Pin 18           | GPIO 24  | Reset    |
| CE (CS)       | Pin 24           | GPIO 8   | SPI CE0  |
| DC (D/C)      | Pin 16           | GPIO 23  | Data/Command |
| DIN (MOSI)    | Pin 19           | GPIO 10  | SPI MOSI |
| CLK (SCLK)    | Pin 23           | GPIO 11  | SPI SCLK |
| VCC           | Pin 1            | 3.3V     | Power    |
| LIGHT (LED)   | Pin 22           | GPIO 25  | Backlight |
| GND           | Pin 6            | GND      | Ground   |

**ÖNEMLİ**: Nokia 5110 ekranı 3.3V ile çalışır, 5V bağlamayın!

## Bağlantı Şeması

```
Raspberry Pi          Nokia 5110
                      
3.3V (Pin 1)  -----> VCC
GND (Pin 6)   -----> GND
GPIO 11       -----> CLK (SCLK)
GPIO 10       -----> DIN (MOSI)
GPIO 8        -----> CE  (CS)
GPIO 23       -----> DC  (D/C)
GPIO 24       -----> RST (Reset)
GPIO 25       -----> LIGHT (LED)
```

## SPI Ayarları

SPI'yi etkinleştirmek için:

```bash
# raspi-config kullanarak
sudo raspi-config
# Interface Options -> SPI -> Enable

# Veya doğrudan config.txt düzenleyerek
echo "dtparam=spi=on" | sudo tee -a /boot/config.txt
sudo reboot
```

## Kurulum

### Gerekli Paketler

```bash
# Python3 ve pip
sudo apt-get install python3 python3-pip

# SPI kütüphanesi
sudo pip3 install spidev

# GPIO kütüphanesi
sudo pip3 install RPi.GPIO
```

### Dosyalar

Proje dosyaları:

- `nokia5110_driver.py` - Ana sürücü kütüphanesi
- `nokia5110-demo.py` - Demo programı (grafik, animasyon)
- `nokia5110-monitor.py` - Sistem monitörü (CPU, RAM, sıcaklık)
- `nokia5110-text.py` - Basit metin gösterimi

## Kullanım

### 1. Basit Metin Gösterimi

```bash
# Varsayılan mesaj
python3 nokia5110-text.py

# Özel mesaj
python3 nokia5110-text.py "Merhaba Dünya!"
python3 nokia5110-text.py "Satir 1\nSatir 2\nSatir 3"
```

### 2. Demo Programı

```bash
python3 nokia5110-demo.py
```

Demo şunları gösterir:
- Hoş geldiniz mesajı
- Sistem bilgisi
- Grafik çizimleri (kutular, çizgiler)
- Animasyonlar (kayan yazı)
- Kontrast ayarı testi

### 3. Sistem Monitörü

```bash
python3 nokia5110-monitor.py
```

Ekranda gösterir:
- CPU kullanımı
- CPU sıcaklığı
- RAM kullanımı
- Sistem çalışma süresi
- IP adresi
- Saat ve tarih

### 4. Python Kodunda Kullanım

```python
from nokia5110_driver import Nokia5110
import time

# Display'i başlat
lcd = Nokia5110()

# Temizle
lcd.clear()

# Metin yaz
lcd.draw_text(0, 0, "Merhaba!", 1)
lcd.draw_text_centered(20, "Nokia 5110", 1)

# Grafik çiz
lcd.draw_rect(0, 0, 84, 48, 1)
lcd.draw_line(0, 0, 83, 47, 1)

# Ekrana gönder
lcd.display()

# Kontrast ayarla (0-127, tipik 0x30-0x50)
lcd.set_contrast(0x3F)

# Arka ışığı kapat
lcd.set_backlight(False)

time.sleep(5)

# Temizle ve kapat
lcd.cleanup()
```

## API Referansı

### Nokia5110 Sınıfı

#### Başlatma
```python
lcd = Nokia5110(rst=24, dc=23, led=25, spi_bus=0, spi_device=0, contrast=0x3F)
```

#### Temel Fonksiyonlar
- `clear()` - Ekranı temizle
- `display()` - Buffer'ı ekrana gönder
- `set_contrast(contrast)` - Kontrast ayarla (0-127)
- `set_backlight(state)` - Arka ışık aç/kapa
- `invert_display(inverted)` - Renkleri ters çevir
- `cleanup()` - Kaynakları temizle

#### Çizim Fonksiyonları
- `set_pixel(x, y, value)` - Tek piksel ayarla
- `draw_line(x0, y0, x1, y1, value)` - Çizgi çiz
- `draw_rect(x, y, width, height, value)` - Dikdörtgen çiz
- `fill_rect(x, y, width, height, value)` - Dolu dikdörtgen çiz
- `draw_char(x, y, char, value)` - Karakter yaz
- `draw_text(x, y, text, value)` - Metin yaz
- `draw_text_centered(y, text, value)` - Ortalanmış metin yaz

## Pin Yapılandırması Değiştirme

Varsayılan pinleri değiştirmek için:

```python
lcd = Nokia5110(
    rst=24,      # Reset pin
    dc=23,       # Data/Command pin
    led=25,      # LED pin (None = devre dışı)
    spi_bus=0,   # SPI bus
    spi_device=0 # SPI device
)
```

## Sorun Giderme

### Ekran boş görünüyor
1. SPI etkin mi kontrol edin: `ls /dev/spi*`
2. Bağlantıları kontrol edin
3. 3.3V kullandığınızdan emin olun (5V DEĞIL!)
4. Kontrast ayarını değiştirin: `lcd.set_contrast(0x40)`

### "Permission denied" hatası
```bash
# Kullanıcıyı spi ve gpio gruplarına ekleyin
sudo usermod -a -G spi,gpio $USER
# Çıkış yapıp tekrar giriş yapın
```

### Ekran titrek veya kararsız
- Kabloları kısaltın
- Topraklama bağlantısını kontrol edin
- SPI hızını düşürün (nokia5110_driver.py içinde)

## Teknik Detaylar

### Ekran Özellikleri
- Çözünürlük: 84x48 piksel
- Görüntüleme Alanı: 43.4mm x 43.4mm
- Çalışma Voltajı: 2.7V - 3.3V
- Akım Tüketimi: ~6mA (arka ışık kapalı), ~80mA (arka ışık açık)
- SPI Hızı: 4 MHz (maksimum)

### Buffer Yapısı
- Toplam: 504 byte (84 x 48 / 8)
- 6 satır x 84 sütun
- Her byte 8 dikey piksel

## Örnek Projeler

### 1. Saat ve Tarih Göstergesi
```python
import time
from nokia5110_driver import Nokia5110

lcd = Nokia5110()

while True:
    lcd.clear()
    lcd.draw_text_centered(10, time.strftime("%H:%M:%S"), 1)
    lcd.draw_text_centered(25, time.strftime("%d/%m/%Y"), 1)
    lcd.display()
    time.sleep(1)
```

### 2. CPU Sıcaklık Göstergesi
```python
from nokia5110_driver import Nokia5110

def get_cpu_temp():
    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
        return float(f.read().strip()) / 1000.0

lcd = Nokia5110()
temp = get_cpu_temp()

lcd.clear()
lcd.draw_text_centered(15, "CPU TEMP", 1)
lcd.draw_text_centered(27, f"{temp:.1f}C", 1)
lcd.display()
```

### 3. Logo Gösterimi
```python
from nokia5110_driver import Nokia5110

lcd = Nokia5110()
lcd.clear()

# 8x8 logo (örnek: kalp)
logo = [
    0b00000000,
    0b01101100,
    0b11111110,
    0b11111110,
    0b01111100,
    0b00111000,
    0b00010000,
    0b00000000,
]

# Logo'yu çiz
for y, byte in enumerate(logo):
    for x in range(8):
        if byte & (1 << x):
            lcd.set_pixel(38 + x, 20 + y, 1)

lcd.display()
```

## Lisans

MIT License - Detaylar için COPYING.MIT dosyasına bakın.

## Referanslar

- [PCD8544 Datasheet](https://www.sparkfun.com/datasheets/LCD/Monochrome/Nokia5110.pdf)
- [Nokia 5110 LCD Tutorial](https://learn.adafruit.com/nokia-5110-3310-monochrome-lcd)
- [Raspberry Pi SPI Documentation](https://www.raspberrypi.org/documentation/hardware/raspberrypi/spi/)

## Katkıda Bulunma

Hata bildirimleri ve geliştirme önerileri için issue açabilirsiniz.
