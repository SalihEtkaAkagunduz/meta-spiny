# Nokia 5110 LCD Ekran Entegrasyonu

## ✅ Yapılanlar

Nokia 5110 (PCD8544) LCD ekranı için komple bir sürücü ve uygulama seti hazırlandı.

## 📦 Oluşturulan Dosyalar

### 1. Sürücü ve Kütüphaneler
- **nokia5110_driver.py** - Ana sürücü modülü
  - SPI iletişimi
  - Grafik çizim fonksiyonları (piksel, çizgi, dikdörtgen)
  - Metin gösterimi (5x7 font)
  - Kontrast ve arka ışık kontrolü

### 2. Uygulamalar
- **nokia5110-demo.py** - Kapsamlı demo
  - Hoş geldiniz ekranı
  - Grafik gösterileri
  - Animasyonlar
  - Kontrast testi

- **nokia5110-monitor.py** - Sistem monitörü
  - CPU kullanımı ve sıcaklık
  - RAM kullanımı
  - Disk kullanımı
  - Uptime
  - IP adresi
  - Saat ve tarih

- **nokia5110-text.py** - Basit metin gösterimi
  - Komut satırından metin yazma
  - Hızlı test için ideal

### 3. Dokümantasyon
- **README-NOKIA5110.md** - Detaylı kullanım kılavuzu (İngilizce)
  - Pin bağlantıları
  - SPI yapılandırması
  - API referansı
  - Örnek projeler
  - Sorun giderme

- **HIZLI-BASLANGIC.md** - Hızlı başlangıç kılavuzu (Türkçe)
  - Bağlantı şeması
  - İlk test adımları
  - Pratik örnekler
  - Sorun giderme

### 4. Yocto Entegrasyonu
- **nokia5110_1.0.bb** - BitBake recipe
  - Tüm dosyaları sisteme kurar
  - Gerekli bağımlılıkları yükler (python3-spidev, python3-rpi-gpio)
  - /usr/bin ve /usr/share/doc dizinlerine yerleştirir

## 🔌 Bağlantı Şeması

```
Raspberry Pi          Nokia 5110
────────────          ──────────
3.3V (Pin 1)   ────►  VCC
GND (Pin 6)    ────►  GND
GPIO 11        ────►  CLK (SCLK)
GPIO 10        ────►  DIN (MOSI)
GPIO 8         ────►  CE  (CS)
GPIO 23        ────►  DC  (D/C)
GPIO 24        ────►  RST (Reset)
GPIO 25        ────►  LIGHT (LED)
```

## 📋 Özellikler

### Display Özellikleri
- Çözünürlük: 84x48 piksel
- Tip: Monokrom (Siyah/Beyaz)
- Sürücü: PCD8544
- Arayüz: SPI (4 MHz)
- Voltaj: 3.3V (⚠️ 5V KULLANMAYIN!)

### Sürücü Özellikleri
- ✅ Tam grafik desteği
- ✅ Metin gösterimi (5x7 font, ASCII 32-127)
- ✅ Piksel, çizgi, dikdörtgen çizimi
- ✅ Kontrast ayarı
- ✅ Arka ışık kontrolü
- ✅ Display ters çevirme
- ✅ Hardware reset
- ✅ Temiz API

## 🚀 Hızlı Kullanım

### Yocto Image'e Ekleme

```bash
# conf/local.conf veya image recipe'e ekleyin:
IMAGE_INSTALL:append = " nokia5110"
```

### İlk Test

```bash
# Basit metin
nokia5110-text.py "Hello World"

# Demo
nokia5110-demo.py

# Sistem monitörü
nokia5110-monitor.py
```

### Python Kodundan

```python
from nokia5110_driver import Nokia5110

lcd = Nokia5110()
lcd.clear()
lcd.draw_text_centered(20, "Hello!", 1)
lcd.display()
lcd.cleanup()
```

## 📚 API Özeti

### Temel Fonksiyonlar
```python
lcd = Nokia5110()                    # Başlat
lcd.clear()                          # Temizle
lcd.display()                        # Güncelle
lcd.set_contrast(0x3F)               # Kontrast (0-127)
lcd.set_backlight(True)              # Arka ışık
lcd.cleanup()                        # Kapat
```

### Çizim Fonksiyonları
```python
lcd.set_pixel(x, y, 1)               # Piksel
lcd.draw_line(x0, y0, x1, y1, 1)     # Çizgi
lcd.draw_rect(x, y, w, h, 1)         # Dikdörtgen
lcd.fill_rect(x, y, w, h, 1)         # Dolu dikdörtgen
lcd.draw_text(x, y, "text", 1)       # Metin
lcd.draw_text_centered(y, "text", 1) # Ortalı metin
```

## 🎯 Kullanım Senaryoları

### 1. Sistem Bilgisi Gösterimi
- CPU kullanımı ve sıcaklık
- RAM ve disk kullanımı
- Network bilgisi
- Uptime

### 2. IoT Sensör Verileri
- Sıcaklık/nem gösterimi
- Sensör değerleri
- Durum bilgisi

### 3. Robotik Projeler
- Robot durumu
- Sensör okumaları
- Mesajlar

### 4. Gömülü Sistemler
- Kompakt bilgi gösterimi
- Düşük güç tüketimi
- Küçük form faktörü

## ⚙️ Yapılandırma

### Pin Değiştirme
```python
lcd = Nokia5110(
    rst=24,   # Reset pin
    dc=23,    # Data/Command pin
    led=25    # LED pin (None = yok)
)
```

### Kontrast Ayarlama
```python
# Başlangıçta
lcd = Nokia5110(contrast=0x40)

# Sonradan
lcd.set_contrast(0x40)  # 0x00-0x7F
```

## 🔧 Sorun Giderme

### Ekran boş
1. Bağlantıları kontrol edin
2. SPI etkin mi? `ls /dev/spi*`
3. 3.3V kullanıyor musunuz?
4. Kontrast: `lcd.set_contrast(0x50)`

### Permission denied
```bash
sudo usermod -a -G spi,gpio $USER
# Çıkış yapıp tekrar giriş yapın
```

### Ekran titriyor
1. Kabloları kısaltın (<15cm)
2. GND bağlantısını kontrol edin
3. SPI hızını düşürün

## 📦 Bağımlılıklar

Recipe otomatik olarak yükler:
- python3-core
- python3-spidev
- python3-rpi-gpio

## 🎓 Örnek Projeler

### Saat
```python
while True:
    lcd.clear()
    lcd.draw_text_centered(20, time.strftime("%H:%M:%S"), 1)
    lcd.display()
    time.sleep(1)
```

### Sıcaklık
```python
temp = get_cpu_temp()
lcd.draw_text_centered(20, f"{temp:.1f}C", 1)
lcd.display()
```

### Logo
```python
logo = [0b01101100, 0b11111110, ...]
for y, byte in enumerate(logo):
    for x in range(8):
        if byte & (1 << x):
            lcd.set_pixel(x, y, 1)
```

## 📂 Dosya Konumları

### Kaynak Dosyalar (Yocto layer)
```
meta-spiny/recipes-drivers/nokia5110/
├── nokia5110_1.0.bb              (BitBake recipe)
├── ENTEGRASYON-OZETI.md          (Bu dosya)
└── files/
    ├── nokia5110_driver.py       (Sürücü)
    ├── nokia5110-demo.py         (Demo)
    ├── nokia5110-monitor.py      (Monitör)
    ├── nokia5110-text.py         (Metin)
    ├── README-NOKIA5110.md       (İng. kılavuz)
    └── HIZLI-BASLANGIC.md        (Tr. kılavuz)
```

### Sisteme Kurulduğunda
```
/usr/bin/
├── nokia5110_driver.py
├── nokia5110-demo.py
├── nokia5110-monitor.py
└── nokia5110-text.py

/usr/share/doc/nokia5110/
├── README-NOKIA5110.md
└── HIZLI-BASLANGIC.md
```

## ✨ Sonuç

Nokia 5110 ekranı başarıyla entegre edildi! Artık 84x48 piksellik monokrom ekranınızda:
- Sistem bilgilerini gösterebilir
- Sensör verilerini takip edebilir
- Grafik çizimler yapabilir
- Özel uygulamalar geliştirebilirsiniz

**3.5" touchscreen'den Nokia 5110'a başarıyla geçiş yaptınız! 🎉**

---

**Not**: Tüm dosyalar `/home/s2344/yocto/poky/meta-spiny/recipes-drivers/nokia5110/` dizininde hazır.

