#!/usr/bin/env python3
import struct
import select
import mmap
import os

WIDTH = 480
HEIGHT = 320
BPP = 2  # bytes per pixel (RGB565)

class TouchScreen:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.pressure = 0
        self.touching = False
        
    def read_events(self, event_file):
        ready, _, _ = select.select([event_file], [], [], 0.001)
        if ready:
            try:
                data = event_file.read(24)
                if len(data) == 24:
                    _, _, ev_type, code, value = struct.unpack('QQHHi', data)
                    
                    if ev_type == 3:  # EV_ABS
                        if code == 0:  # ABS_X
                            self.x = value
                        elif code == 1:  # ABS_Y
                            self.y = value
                        elif code == 24:  # ABS_PRESSURE
                            self.pressure = value
                    elif ev_type == 1:  # EV_KEY
                        if code == 330:  # BTN_TOUCH
                            self.touching = (value == 1)
                    
                    return True
            except:
                pass
        return False

def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

def draw_circle(fb_map, cx, cy, radius, color):
    for y in range(max(0, cy - radius), min(HEIGHT, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(WIDTH, cx + radius + 1)):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                pos = (y * WIDTH + x) * BPP
                fb_map[pos:pos+2] = color.to_bytes(2, 'little')

print('=== TOUCHSCREEN ÇIZIM UYGULAMASI ===')
print('Ekrana dokunarak çizim yapabilirsiniz')
print('Çıkmak için Ctrl+C')

# Framebuffer aç
fb = os.open('/dev/fb2', os.O_RDWR)
fb_map = mmap.mmap(fb, WIDTH * HEIGHT * BPP, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ)

# Ekranı beyaz yap
white = rgb565(255, 255, 255)
for i in range(0, len(fb_map), 2):
    fb_map[i:i+2] = white.to_bytes(2, 'little')

# Touchscreen aç
touch_file = open('/dev/input/event0', 'rb')
touch = TouchScreen()

red = rgb565(255, 0, 0)
last_x, last_y = -1, -1

try:
    while True:
        if touch.read_events(touch_file):
            if touch.touching and touch.pressure > 0:
                # Ham değerleri ekran koordinatlarına dönüştür
                # ADS7846: X: 0-4095, Y: 0-4095
                screen_x = int((touch.x / 4095.0) * WIDTH)
                screen_y = int((touch.y / 4095.0) * HEIGHT)
                
                # Sınırları kontrol et
                screen_x = max(0, min(WIDTH - 1, screen_x))
                screen_y = max(0, min(HEIGHT - 1, screen_y))
                
                # Çizim yap
                draw_circle(fb_map, screen_x, screen_y, 3, red)
                
                if last_x != screen_x or last_y != screen_y:
                    print(f'Çizim: X={screen_x}, Y={screen_y}, P={touch.pressure}')
                    last_x, last_y = screen_x, screen_y
except KeyboardInterrupt:
    print('\n\nUygulama kapatılıyor...')
finally:
    touch_file.close()
    fb_map.close()
    os.close(fb)
    print('✓ Temizlik tamamlandı')
