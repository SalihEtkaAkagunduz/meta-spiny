#!/usr/bin/env python3
import struct
import mmap
import os
import time

WIDTH = 480
HEIGHT = 320
BPP = 2

class TouchScreen:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.pressure = 0
        self.touching = False
        self.fd = os.open('/dev/input/event0', os.O_RDONLY | os.O_NONBLOCK)
        
    def read_events(self):
        try:
            data = os.read(self.fd, 24)
            if len(data) == 24:
                _, _, ev_type, code, value = struct.unpack('QQHHi', data)
                if ev_type == 3:
                    if code == 0: self.x = value
                    elif code == 1: self.y = value
                    elif code == 24: self.pressure = value
                elif ev_type == 1 and code == 330:
                    self.touching = (value == 1)
                return True
        except BlockingIOError:
            pass
        except Exception as e:
            print(f'Error: {e}')
        return False
    
    def close(self):
        os.close(self.fd)

def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

def fill_rect(fb_map, x, y, w, h, color):
    color_bytes = color.to_bytes(2, 'little')
    for row in range(y, min(HEIGHT, y + h)):
        start = (row * WIDTH + x) * BPP
        for col in range(w):
            pos = start + col * BPP
            if pos + 2 <= len(fb_map):
                fb_map[pos:pos+2] = color_bytes

def draw_text_simple(fb_map, x, y, text, fg_color, bg_color):
    # Basit 8x8 bitmap font ile yazı yazdırma
    # Her harf için küçük bir dikdörtgen çiziyoruz
    char_width = 10
    char_height = 16
    for i, char in enumerate(text):
        char_x = x + i * char_width
        fill_rect(fb_map, char_x, y, char_width-2, char_height, fg_color)

print('LCD MENU v2 - Starting...')

# Framebuffer
fb = os.open('/dev/fb2', os.O_RDWR)
fb_map = mmap.mmap(fb, WIDTH * HEIGHT * BPP, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ)

# Renkler
WHITE = rgb565(255, 255, 255)
BLACK = rgb565(0, 0, 0)
BLUE = rgb565(0, 100, 255)
GREEN = rgb565(0, 255, 0)
RED = rgb565(255, 0, 0)

# Ekranı temizle
for i in range(0, len(fb_map), 2):
    fb_map[i:i+2] = WHITE.to_bytes(2, 'little')

# Başlık
fill_rect(fb_map, 0, 0, WIDTH, 40, BLUE)
draw_text_simple(fb_map, 20, 12, 'RASPBERRY PI 4 - LCD MENU', WHITE, BLUE)

# Koordinat gösterge alanı
coord_y = 45
fill_rect(fb_map, 0, coord_y, WIDTH, 20, BLACK)
draw_text_simple(fb_map, 20, coord_y+2, 'Last Touch: ---', GREEN, BLACK)

# Butonlar
button_y = 70
button_height = 50
button_margin = 10

ORANGE = rgb565(255, 165, 0)

buttons = [
    {'label': 'BTN 1: Test', 'y': button_y, 'color': GREEN},
    {'label': 'BTN 2: Info', 'y': button_y + button_height + button_margin, 'color': ORANGE},
    {'label': 'BTN 3: Exit', 'y': button_y + 2*(button_height + button_margin), 'color': RED},
]

for btn in buttons:
    fill_rect(fb_map, 20, btn['y'], WIDTH-40, button_height, btn['color'])
    draw_text_simple(fb_map, 40, btn['y']+17, btn['label'], WHITE, btn['color'])

# Durum satırı
status_y = HEIGHT - 30
fill_rect(fb_map, 0, status_y, WIDTH, 30, BLACK)
draw_text_simple(fb_map, 20, status_y+7, 'Touchscreen: READY', GREEN, BLACK)

print('Menu drawn. Waiting for touch...')

# Touchscreen
touch = TouchScreen()

try:
    last_button = -1
    button_press_count = [0, 0, 0]
    
    while True:
        if touch.read_events():
            if touch.pressure > 0:
                screen_x = int((touch.x / 4095.0) * WIDTH)
                screen_y = int((touch.y / 4095.0) * HEIGHT)
                
                # Koordinat göstergesini güncelle
                fill_rect(fb_map, 0, coord_y, WIDTH, 20, BLACK)
                coord_text = f'Last Touch: X={screen_x:3d} Y={screen_y:3d}'
                draw_text_simple(fb_map, 20, coord_y+2, coord_text, GREEN, BLACK)
                
                # Buton kontrolü
                for i, btn in enumerate(buttons):
                    if (20 <= screen_x <= WIDTH-20 and 
                        btn['y'] <= screen_y <= btn['y']+button_height):
                        if last_button != i:
                            button_press_count[i] += 1
                            print(f'✓ Button {i+1} pressed! Count: {button_press_count[i]} Pos:({screen_x},{screen_y})')
                            
                            # Buton efekti
                            fill_rect(fb_map, 20, btn['y'], WIDTH-40, button_height, WHITE)
                            time.sleep(0.05)
                            fill_rect(fb_map, 20, btn['y'], WIDTH-40, button_height, btn['color'])
                            draw_text_simple(fb_map, 40, btn['y']+17, btn['label'], WHITE, btn['color'])
                            
                            # Durum satırını güncelle
                            fill_rect(fb_map, 0, status_y, WIDTH, 30, BLACK)
                            status_text = f'Button {i+1} - Count: {button_press_count[i]}'
                            draw_text_simple(fb_map, 20, status_y+7, status_text, GREEN, BLACK)
                            
                            last_button = i
                            
                            # Button 3 = Exit
                            if i == 2:
                                print('Exit button pressed. Exiting...')
                                raise KeyboardInterrupt
            else:
                last_button = -1
        else:
            time.sleep(0.001)
                
except KeyboardInterrupt:
    print('Exiting...')
finally:
    touch.close()
    fb_map.close()
    os.close(fb)
    print('✓ Cleanup done')
