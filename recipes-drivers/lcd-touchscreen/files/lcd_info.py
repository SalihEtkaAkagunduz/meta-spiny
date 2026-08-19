#!/usr/bin/env python3
import os
import mmap
import time

WIDTH = 480
HEIGHT = 320
BPP = 2

def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

def fill_screen(fb_map, color):
    color_bytes = color.to_bytes(2, 'little')
    for i in range(0, len(fb_map), 2):
        fb_map[i:i+2] = color_bytes

def fill_rect(fb_map, x, y, w, h, color):
    color_bytes = color.to_bytes(2, 'little')
    for row in range(y, min(HEIGHT, y + h)):
        for col in range(x, min(WIDTH, x + w)):
            pos = (row * WIDTH + col) * BPP
            if pos + 2 <= len(fb_map):
                fb_map[pos:pos+2] = color_bytes

print('LCD Info Display - Starting...')

# Framebuffer aç
fb = os.open('/dev/fb2', os.O_RDWR)
fb_map = mmap.mmap(fb, WIDTH * HEIGHT * BPP, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ)

# Renkler
WHITE = rgb565(255, 255, 255)
BLACK = rgb565(0, 0, 0)
BLUE = rgb565(0, 100, 255)
GREEN = rgb565(0, 200, 0)
RED = rgb565(255, 0, 0)
YELLOW = rgb565(255, 255, 0)

try:
    # Ekranı beyaz yap
    fill_screen(fb_map, WHITE)
    time.sleep(0.5)
    
    # Başlık (mavi)
    fill_rect(fb_map, 0, 0, WIDTH, 50, BLUE)
    
    # İçerik alanı (açık yeşil)
    fill_rect(fb_map, 10, 60, WIDTH-20, 180, GREEN)
    
    # Alt bilgi (sarı)
    fill_rect(fb_map, 0, HEIGHT-40, WIDTH, 40, YELLOW)
    
    # Köşelere işaretler (kırmızı)
    for x, y in [(10, 60), (WIDTH-20, 60), (10, HEIGHT-50), (WIDTH-20, HEIGHT-50)]:
        fill_rect(fb_map, x, y, 10, 10, RED)
    
    print('✓ Display initialized successfully!')
    print('LCD showing: Blue header, Green content area, Yellow footer')
    print('Red markers at corners')
    
    # 10 saniye bekle
    time.sleep(10)
    
    # Ekranı siyah yap
    fill_screen(fb_map, BLACK)
    print('Screen cleared to black')
    
except Exception as e:
    print(f'Error: {e}')
finally:
    fb_map.close()
    os.close(fb)
    print('Cleanup done')
