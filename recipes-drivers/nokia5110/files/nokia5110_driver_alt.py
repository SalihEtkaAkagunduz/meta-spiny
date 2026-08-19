#!/usr/bin/env python3
"""
Nokia 5110 LCD Driver Module - Alternative Version
PCD8544 controller driver for Raspberry Pi
84x48 monochrome display
Uses SPI1 to avoid conflicts with LCD touchscreen
"""

import time
try:
    import spidev
    HAS_SPIDEV = True
except ImportError:
    HAS_SPIDEV = False

from periphery import GPIO

# Alternative pin configuration (SPI1 compatible)
DEFAULT_PIN_RST = 12   # Reset
DEFAULT_PIN_DC = 16    # Data/Command
DEFAULT_PIN_LED = 21   # Backlight (alternative)

# SPI Configuration - Using SPI1
DEFAULT_SPI_BUS = 1
DEFAULT_SPI_DEVICE = 0
DEFAULT_SPI_MAX_SPEED = 4000000  # 4 MHz

# Display dimensions
LCD_WIDTH = 84
LCD_HEIGHT = 48
LCD_ROWS = 6  # 48 pixels / 8 bits per row

# Commands
PCD8544_FUNCTIONSET = 0x20
PCD8544_DISPLAYCONTROL = 0x08
PCD8544_SETYADDR = 0x40
PCD8544_SETXADDR = 0x80
PCD8544_SETTEMP = 0x04
PCD8544_SETBIAS = 0x10
PCD8544_SETVOP = 0x80

# Display modes
DISPLAY_BLANK = 0
DISPLAY_NORMAL = 4
DISPLAY_ALLON = 1
DISPLAY_INVERTED = 5

# Font 5x7 (ASCII 32-127)
FONT_5X7 = [
    [0x00, 0x00, 0x00, 0x00, 0x00],  # 20 space
    [0x00, 0x00, 0x5f, 0x00, 0x00],  # 21 !
    [0x00, 0x07, 0x00, 0x07, 0x00],  # 22 "
    [0x14, 0x7f, 0x14, 0x7f, 0x14],  # 23 #
    [0x24, 0x2a, 0x7f, 0x2a, 0x12],  # 24 $
    [0x23, 0x13, 0x08, 0x64, 0x62],  # 25 %
    [0x36, 0x49, 0x55, 0x22, 0x50],  # 26 &
    [0x00, 0x05, 0x03, 0x00, 0x00],  # 27 '
    [0x00, 0x1c, 0x22, 0x41, 0x00],  # 28 (
    [0x00, 0x41, 0x22, 0x1c, 0x00],  # 29 )
    [0x14, 0x08, 0x3e, 0x08, 0x14],  # 2a *
    [0x08, 0x08, 0x3e, 0x08, 0x08],  # 2b +
    [0x00, 0x50, 0x30, 0x00, 0x00],  # 2c ,
    [0x08, 0x08, 0x08, 0x08, 0x08],  # 2d -
    [0x00, 0x60, 0x60, 0x00, 0x00],  # 2e .
    [0x20, 0x10, 0x08, 0x04, 0x02],  # 2f /
    [0x3e, 0x51, 0x49, 0x45, 0x3e],  # 30 0
    [0x00, 0x42, 0x7f, 0x40, 0x00],  # 31 1
    [0x42, 0x61, 0x51, 0x49, 0x46],  # 32 2
    [0x21, 0x41, 0x45, 0x4b, 0x31],  # 33 3
    [0x18, 0x14, 0x12, 0x7f, 0x10],  # 34 4
    [0x27, 0x45, 0x45, 0x45, 0x39],  # 35 5
    [0x3c, 0x4a, 0x49, 0x49, 0x30],  # 36 6
    [0x01, 0x71, 0x09, 0x05, 0x03],  # 37 7
    [0x36, 0x49, 0x49, 0x49, 0x36],  # 38 8
    [0x06, 0x49, 0x49, 0x29, 0x1e],  # 39 9
    [0x00, 0x36, 0x36, 0x00, 0x00],  # 3a :
    [0x00, 0x56, 0x36, 0x00, 0x00],  # 3b ;
    [0x08, 0x14, 0x22, 0x41, 0x00],  # 3c <
    [0x14, 0x14, 0x14, 0x14, 0x14],  # 3d =
    [0x00, 0x41, 0x22, 0x14, 0x08],  # 3e >
    [0x02, 0x01, 0x51, 0x09, 0x06],  # 3f ?
    [0x32, 0x49, 0x79, 0x41, 0x3e],  # 40 @
    [0x7e, 0x11, 0x11, 0x11, 0x7e],  # 41 A
    [0x7f, 0x49, 0x49, 0x49, 0x36],  # 42 B
    [0x3e, 0x41, 0x41, 0x41, 0x22],  # 43 C
    [0x7f, 0x41, 0x41, 0x22, 0x1c],  # 44 D
    [0x7f, 0x49, 0x49, 0x49, 0x41],  # 45 E
    [0x7f, 0x09, 0x09, 0x09, 0x01],  # 46 F
    [0x3e, 0x41, 0x49, 0x49, 0x7a],  # 47 G
    [0x7f, 0x08, 0x08, 0x08, 0x7f],  # 48 H
    [0x00, 0x41, 0x7f, 0x41, 0x00],  # 49 I
    [0x20, 0x40, 0x41, 0x3f, 0x01],  # 4a J
    [0x7f, 0x08, 0x14, 0x22, 0x41],  # 4b K
    [0x7f, 0x40, 0x40, 0x40, 0x40],  # 4c L
    [0x7f, 0x02, 0x0c, 0x02, 0x7f],  # 4d M
    [0x7f, 0x04, 0x08, 0x10, 0x7f],  # 4e N
    [0x3e, 0x41, 0x41, 0x41, 0x3e],  # 4f O
    [0x7f, 0x09, 0x09, 0x09, 0x06],  # 50 P
    [0x3e, 0x41, 0x51, 0x21, 0x5e],  # 51 Q
    [0x7f, 0x09, 0x19, 0x29, 0x46],  # 52 R
    [0x46, 0x49, 0x49, 0x49, 0x31],  # 53 S
    [0x01, 0x01, 0x7f, 0x01, 0x01],  # 54 T
    [0x3f, 0x40, 0x40, 0x40, 0x3f],  # 55 U
    [0x1f, 0x20, 0x40, 0x20, 0x1f],  # 56 V
    [0x3f, 0x40, 0x38, 0x40, 0x3f],  # 57 W
    [0x63, 0x14, 0x08, 0x14, 0x63],  # 58 X
    [0x07, 0x08, 0x70, 0x08, 0x07],  # 59 Y
    [0x61, 0x51, 0x49, 0x45, 0x43],  # 5a Z
    [0x00, 0x7f, 0x41, 0x41, 0x00],  # 5b [
    [0x02, 0x04, 0x08, 0x10, 0x20],  # 5c backslash
    [0x00, 0x41, 0x41, 0x7f, 0x00],  # 5d ]
    [0x04, 0x02, 0x01, 0x02, 0x04],  # 5e ^
    [0x40, 0x40, 0x40, 0x40, 0x40],  # 5f _
    [0x00, 0x01, 0x02, 0x04, 0x00],  # 60 `
    [0x20, 0x54, 0x54, 0x54, 0x78],  # 61 a
    [0x7f, 0x48, 0x44, 0x44, 0x38],  # 62 b
    [0x38, 0x44, 0x44, 0x44, 0x20],  # 63 c
    [0x38, 0x44, 0x44, 0x48, 0x7f],  # 64 d
    [0x38, 0x54, 0x54, 0x54, 0x18],  # 65 e
    [0x08, 0x7e, 0x09, 0x01, 0x02],  # 66 f
    [0x0c, 0x52, 0x52, 0x52, 0x3e],  # 67 g
    [0x7f, 0x08, 0x04, 0x04, 0x78],  # 68 h
    [0x00, 0x44, 0x7d, 0x40, 0x00],  # 69 i
    [0x20, 0x40, 0x44, 0x3d, 0x00],  # 6a j
    [0x7f, 0x10, 0x28, 0x44, 0x00],  # 6b k
    [0x00, 0x41, 0x7f, 0x40, 0x00],  # 6c l
    [0x7c, 0x04, 0x18, 0x04, 0x78],  # 6d m
    [0x7c, 0x08, 0x04, 0x04, 0x78],  # 6e n
    [0x38, 0x44, 0x44, 0x44, 0x38],  # 6f o
    [0x7c, 0x14, 0x14, 0x14, 0x08],  # 70 p
    [0x08, 0x14, 0x14, 0x18, 0x7c],  # 71 q
    [0x7c, 0x08, 0x04, 0x04, 0x08],  # 72 r
    [0x48, 0x54, 0x54, 0x54, 0x20],  # 73 s
    [0x04, 0x3f, 0x44, 0x40, 0x20],  # 74 t
    [0x3c, 0x40, 0x40, 0x20, 0x7c],  # 75 u
    [0x1c, 0x20, 0x40, 0x20, 0x1c],  # 76 v
    [0x3c, 0x40, 0x30, 0x40, 0x3c],  # 77 w
    [0x44, 0x28, 0x10, 0x28, 0x44],  # 78 x
    [0x0c, 0x50, 0x50, 0x50, 0x3c],  # 79 y
    [0x44, 0x64, 0x54, 0x4c, 0x44],  # 7a z
    [0x00, 0x08, 0x36, 0x41, 0x00],  # 7b {
    [0x00, 0x00, 0x7f, 0x00, 0x00],  # 7c |
    [0x00, 0x41, 0x36, 0x08, 0x00],  # 7d }
    [0x10, 0x08, 0x08, 0x10, 0x08],  # 7e ~
    [0x00, 0x00, 0x00, 0x00, 0x00],  # 7f
]


class Nokia5110:
    """Nokia 5110 LCD Display Driver - Alternative Version"""
    
    def __init__(self, rst=DEFAULT_PIN_RST, dc=DEFAULT_PIN_DC, led=DEFAULT_PIN_LED, 
                 spi_bus=DEFAULT_SPI_BUS, spi_device=DEFAULT_SPI_DEVICE,
                 contrast=0x3F):
        """
        Initialize Nokia 5110 display
        
        Args:
            rst: Reset pin (BCM numbering)
            dc: Data/Command pin (BCM numbering)
            led: Backlight LED pin (BCM numbering, None to disable)
            spi_bus: SPI bus number
            spi_device: SPI device number
            contrast: Display contrast (0x00-0x7F, default 0x3F)
        """
        self.contrast = contrast
        
        # Initialize GPIO pins using periphery
        self.rst_gpio = GPIO(rst, "out")
        self.dc_gpio = GPIO(dc, "out")
        if led is not None:
            self.led_gpio = GPIO(led, "out")
            self.led_gpio.write(True)  # Turn on backlight
        else:
            self.led_gpio = None
        
        # Initialize SPI
        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_device)
        self.spi.max_speed_hz = DEFAULT_SPI_MAX_SPEED
        self.spi.mode = 0
        
        # Display buffer
        self.buffer = [0] * (LCD_WIDTH * LCD_ROWS)
        
        # Initialize display
        self.reset()
        self.init_display()
        
    def reset(self):
        """Hardware reset"""
        self.rst_gpio.write(False)
        time.sleep(0.1)
        self.rst_gpio.write(True)
        time.sleep(0.1)
        
    def command(self, cmd):
        """Send command to display"""
        self.dc_gpio.write(False)
        self.spi.writebytes([cmd])
        
    def data(self, data_bytes):
        """Send data to display"""
        self.dc_gpio.write(True)
        if isinstance(data_bytes, int):
            self.spi.writebytes([data_bytes])
        else:
            self.spi.writebytes(data_bytes)
            
    def init_display(self):
        """Initialize display with default settings"""
        # Extended instruction set
        self.command(PCD8544_FUNCTIONSET | 0x01)
        
        # Set LCD Vop (Contrast)
        self.command(PCD8544_SETVOP | self.contrast)
        
        # Set Temp coefficient
        self.command(PCD8544_SETTEMP | 0x00)
        
        # LCD bias mode 1:48
        self.command(PCD8544_SETBIAS | 0x04)
        
        # Standard instruction set
        self.command(PCD8544_FUNCTIONSET)
        
        # Normal display mode
        self.command(PCD8544_DISPLAYCONTROL | DISPLAY_NORMAL)
        
        # Clear display
        self.clear()
        
    def set_contrast(self, contrast):
        """
        Set display contrast
        
        Args:
            contrast: Contrast value (0-127, typical range 0x30-0x50)
        """
        if contrast < 0 or contrast > 127:
            return
        self.contrast = contrast
        self.command(PCD8544_FUNCTIONSET | 0x01)  # Extended
        self.command(PCD8544_SETVOP | contrast)
        self.command(PCD8544_FUNCTIONSET)  # Standard
        
    def set_backlight(self, state):
        """
        Turn backlight on/off
        
        Args:
            state: True to turn on, False to turn off
        """
        if self.led_gpio is not None:
            self.led_gpio.write(state)
            
    def invert_display(self, inverted=True):
        """
        Invert display colors
        
        Args:
            inverted: True for inverted, False for normal
        """
        mode = DISPLAY_INVERTED if inverted else DISPLAY_NORMAL
        self.command(PCD8544_DISPLAYCONTROL | mode)
        
    def clear(self):
        """Clear display buffer and screen"""
        self.buffer = [0] * (LCD_WIDTH * LCD_ROWS)
        self.display()
        
    def display(self):
        """Write buffer to display"""
        self.command(PCD8544_SETYADDR)
        self.command(PCD8544_SETXADDR)
        self.data(self.buffer)
        
    def set_pixel(self, x, y, value=1):
        """
        Set a single pixel
        
        Args:
            x: X coordinate (0-83)
            y: Y coordinate (0-47)
            value: 1 for on, 0 for off
        """
        if x < 0 or x >= LCD_WIDTH or y < 0 or y >= LCD_HEIGHT:
            return
        
        row = y // 8
        bit = y % 8
        index = x + row * LCD_WIDTH
        
        if value:
            self.buffer[index] |= (1 << bit)
        else:
            self.buffer[index] &= ~(1 << bit)
            
    def draw_line(self, x0, y0, x1, y1, value=1):
        """
        Draw a line using Bresenham's algorithm
        
        Args:
            x0, y0: Start coordinates
            x1, y1: End coordinates
            value: 1 for on, 0 for off
        """
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        
        while True:
            self.set_pixel(x0, y0, value)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy
                
    def draw_rect(self, x, y, width, height, value=1):
        """
        Draw a rectangle outline
        
        Args:
            x, y: Top-left corner
            width, height: Dimensions
            value: 1 for on, 0 for off
        """
        self.draw_line(x, y, x + width - 1, y, value)
        self.draw_line(x + width - 1, y, x + width - 1, y + height - 1, value)
        self.draw_line(x + width - 1, y + height - 1, x, y + height - 1, value)
        self.draw_line(x, y + height - 1, x, y, value)
        
    def fill_rect(self, x, y, width, height, value=1):
        """
        Fill a rectangle
        
        Args:
            x, y: Top-left corner
            width, height: Dimensions
            value: 1 for on, 0 for off
        """
        for i in range(x, min(x + width, LCD_WIDTH)):
            for j in range(y, min(y + height, LCD_HEIGHT)):
                self.set_pixel(i, j, value)
                
    def draw_char(self, x, y, char, value=1):
        """
        Draw a single character
        
        Args:
            x, y: Top-left corner
            char: Character to draw (ASCII)
            value: 1 for on, 0 for off
        """
        if char < 32 or char > 127:
            char = 32
        
        char_data = FONT_5X7[char - 32]
        
        for col in range(5):
            byte = char_data[col]
            for row in range(8):
                if byte & (1 << row):
                    self.set_pixel(x + col, y + row, value)
                else:
                    self.set_pixel(x + col, y + row, 0 if value else 1)
                    
    def draw_text(self, x, y, text, value=1):
        """
        Draw text string
        
        Args:
            x, y: Starting position
            text: Text to draw
            value: 1 for on, 0 for off
        """
        cursor_x = x
        cursor_y = y
        
        for char in text:
            if char == '\n':
                cursor_y += 8
                cursor_x = x
            else:
                if cursor_x + 6 > LCD_WIDTH:
                    cursor_x = x
                    cursor_y += 8
                if cursor_y + 8 > LCD_HEIGHT:
                    break
                self.draw_char(cursor_x, cursor_y, ord(char), value)
                cursor_x += 6
                
    def draw_text_centered(self, y, text, value=1):
        """
        Draw centered text
        
        Args:
            y: Y position
            text: Text to draw
            value: 1 for on, 0 for off
        """
        text_width = len(text) * 6
        x = (LCD_WIDTH - text_width) // 2
        self.draw_text(x, y, text, value)
        
    def cleanup(self):
        """Clean up resources"""
        self.clear()
        if self.led_gpio is not None:
            self.led_gpio.write(False)
            self.led_gpio.close()
        self.rst_gpio.close()
        self.dc_gpio.close()
        self.spi.close()