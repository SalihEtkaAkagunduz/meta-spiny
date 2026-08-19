#!/usr/bin/env python3
"""
LCD System Information Display
Shows system information on the LCD screen
"""

import os
import sys
import platform
import subprocess
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import font, scrolledtext
except ImportError:
    tk = None

class SystemInfo:
    def __init__(self):
        self.width = 480
        self.height = 320
        
        if tk:
            self.root = tk.Tk()
            self.root.title("System Information")
            self.root.geometry(f"{self.width}x{self.height}")
            self.root.configure(bg='#1e1e1e')
            
            try:
                self.root.attributes('-fullscreen', True)
            except:
                pass
            
            self.setup_gui()
            self.update_info()
        else:
            self.console_display()
    
    def get_system_info(self):
        """Gather system information"""
        info = []
        
        # System
        info.append(f"System: {platform.system()} {platform.release()}")
        info.append(f"Machine: {platform.machine()}")
        info.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Uptime
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                info.append(f"Uptime: {hours}h {minutes}m")
        except:
            pass
        
        # Memory
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
                mem_total = int(lines[0].split()[1]) // 1024
                mem_free = int(lines[1].split()[1]) // 1024
                mem_used = mem_total - mem_free
                info.append(f"Memory: {mem_used}MB / {mem_total}MB")
        except:
            pass
        
        # CPU Temperature
        try:
            temp_file = '/sys/class/thermal/thermal_zone0/temp'
            if os.path.exists(temp_file):
                with open(temp_file, 'r') as f:
                    temp = int(f.read().strip()) / 1000
                    info.append(f"CPU Temp: {temp:.1f}°C")
        except:
            pass
        
        # Disk usage
        try:
            result = subprocess.run(['df', '-h', '/'], 
                                  capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                info.append(f"Disk: {parts[2]} / {parts[1]} ({parts[4]})")
        except:
            pass
        
        # IP Address
        try:
            result = subprocess.run(['hostname', '-I'], 
                                  capture_output=True, text=True)
            ip = result.stdout.strip().split()[0]
            info.append(f"IP Address: {ip}")
        except:
            pass
        
        # Hostname
        try:
            hostname = platform.node()
            info.append(f"Hostname: {hostname}")
        except:
            pass
        
        return info
    
    def setup_gui(self):
        """Setup GUI display"""
        title_font = font.Font(family='Helvetica', size=18, weight='bold')
        info_font = font.Font(family='Courier', size=11)
        
        # Title
        title = tk.Label(self.root, text="SYSTEM INFORMATION", 
                        font=title_font, fg='#00ff00', bg='#1e1e1e')
        title.pack(pady=10)
        
        # Info display
        self.info_text = scrolledtext.ScrolledText(
            self.root, 
            font=info_font,
            bg='#1e1e1e',
            fg='#00ff00',
            height=12,
            width=50,
            relief='flat'
        )
        self.info_text.pack(padx=10, pady=10, expand=True, fill='both')
        
        # Close button
        btn = tk.Button(self.root, text="Close", command=self.root.destroy,
                       font=('Helvetica', 12), width=15, height=1,
                       bg='#c0392b', fg='white', activebackground='#e74c3c')
        btn.pack(pady=10)
        
        self.root.mainloop()
    
    def update_info(self):
        """Update information display"""
        if tk and hasattr(self, 'info_text'):
            self.info_text.delete(1.0, tk.END)
            info_lines = self.get_system_info()
            for line in info_lines:
                self.info_text.insert(tk.END, line + '\n')
            
            # Schedule next update
            self.root.after(2000, self.update_info)
    
    def console_display(self):
        """Console fallback mode"""
        print("=" * 50)
        print("       SYSTEM INFORMATION")
        print("=" * 50)
        for line in self.get_system_info():
            print(line)
        print("=" * 50)

if __name__ == "__main__":
    try:
        SystemInfo()
    except KeyboardInterrupt:
        print("\nInfo display closed")
        sys.exit(0)
