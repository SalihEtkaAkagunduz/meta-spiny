#!/usr/bin/env python3
"""
LCD Menu Application for 3.5" Touchscreen
Displays an interactive menu on the LCD display
"""

import os
import sys
import time
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import font
except ImportError:
    print("Warning: tkinter not available, using framebuffer mode")
    tk = None

class LCDMenu:
    def __init__(self):
        self.width = 480
        self.height = 320
        
        if tk:
            self.root = tk.Tk()
            self.root.title("Spiny OS LCD Menu")
            self.root.geometry(f"{self.width}x{self.height}")
            self.root.configure(bg='black')
            
            # Try fullscreen for embedded display
            try:
                self.root.attributes('-fullscreen', True)
            except:
                pass
            
            self.setup_gui()
        else:
            self.console_mode()
    
    def setup_gui(self):
        """Setup GUI menu"""
        title_font = font.Font(family='Helvetica', size=20, weight='bold')
        button_font = font.Font(family='Helvetica', size=14)
        
        # Title
        title = tk.Label(self.root, text="SPINY OS", 
                        font=title_font, fg='cyan', bg='black')
        title.pack(pady=20)
        
        # System info
        info_text = f"System Ready\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        info = tk.Label(self.root, text=info_text, 
                       font=button_font, fg='white', bg='black')
        info.pack(pady=10)
        
        # Menu buttons
        button_frame = tk.Frame(self.root, bg='black')
        button_frame.pack(expand=True)
        
        buttons = [
            ("System Info", self.show_info),
            ("Touch Draw", self.show_draw),
            ("Settings", self.show_settings),
            ("Shutdown", self.shutdown)
        ]
        
        for text, command in buttons:
            btn = tk.Button(button_frame, text=text, command=command,
                          font=button_font, width=20, height=2,
                          bg='#2c3e50', fg='white', relief='raised',
                          activebackground='#34495e')
            btn.pack(pady=8)
        
        # Status bar
        self.status = tk.Label(self.root, text="Ready", 
                              font=('Helvetica', 10), fg='green', bg='black')
        self.status.pack(side='bottom', pady=10)
        
        self.root.mainloop()
    
    def show_info(self):
        self.status.config(text="Opening System Info...")
        os.system('/usr/bin/lcd_info.py &')
    
    def show_draw(self):
        self.status.config(text="Opening Touch Draw...")
        os.system('/usr/bin/touch_draw.py &')
    
    def show_settings(self):
        self.status.config(text="Settings - Not yet implemented")
    
    def shutdown(self):
        self.status.config(text="Shutting down...")
        self.root.after(1000, lambda: os.system('systemctl poweroff'))
    
    def console_mode(self):
        """Console fallback mode"""
        print("=" * 40)
        print("    SPINY OS - LCD MENU")
        print("=" * 40)
        print(f"\nSystem Time: {datetime.now()}")
        print("\nMenu Options:")
        print("1. System Info")
        print("2. Touch Draw")
        print("3. Settings")
        print("4. Shutdown")
        print("\nRunning in console mode...")
        
        while True:
            time.sleep(10)
            print(f"Status: Running - {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    try:
        menu = LCDMenu()
    except KeyboardInterrupt:
        print("\nMenu closed")
        sys.exit(0)
