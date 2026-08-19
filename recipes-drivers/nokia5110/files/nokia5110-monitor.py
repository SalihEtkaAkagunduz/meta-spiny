#!/usr/bin/env python3
"""
Nokia 5110 System Monitor
Displays system information on Nokia 5110 LCD
"""

import time
import os
import sys

# Import Nokia 5110 driver
try:
    from nokia5110_driver import Nokia5110
except ImportError:
    print("Error: nokia5110_driver.py not found")
    print("Please ensure the driver file is in the same directory")
    sys.exit(1)


def get_cpu_temp():
    """Get CPU temperature"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read().strip()) / 1000.0
            return f"{temp:.1f}C"
    except:
        return "N/A"


def get_cpu_usage():
    """Get CPU usage percentage"""
    try:
        with open('/proc/stat', 'r') as f:
            line = f.readline()
            fields = line.split()
            idle = int(fields[4])
            total = sum(int(x) for x in fields[1:8])
            
            time.sleep(0.1)
            
        with open('/proc/stat', 'r') as f:
            line = f.readline()
            fields = line.split()
            idle2 = int(fields[4])
            total2 = sum(int(x) for x in fields[1:8])
            
        idle_delta = idle2 - idle
        total_delta = total2 - total
        usage = 100.0 * (1.0 - idle_delta / total_delta)
        return f"{usage:.0f}%"
    except:
        return "N/A"


def get_memory_usage():
    """Get memory usage"""
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
            
        mem_total = 0
        mem_free = 0
        mem_available = 0
        
        for line in lines:
            if 'MemTotal:' in line:
                mem_total = int(line.split()[1]) // 1024  # Convert to MB
            elif 'MemFree:' in line:
                mem_free = int(line.split()[1]) // 1024
            elif 'MemAvailable:' in line:
                mem_available = int(line.split()[1]) // 1024
                
        mem_used = mem_total - mem_available
        return f"{mem_used}/{mem_total}MB"
    except:
        return "N/A"


def get_disk_usage():
    """Get disk usage"""
    try:
        stat = os.statvfs('/')
        total = (stat.f_blocks * stat.f_frsize) // (1024**3)  # GB
        free = (stat.f_bavail * stat.f_frsize) // (1024**3)   # GB
        used = total - free
        return f"{used}/{total}GB"
    except:
        return "N/A"


def get_uptime():
    """Get system uptime"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
            
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        
        if hours > 24:
            days = hours // 24
            hours = hours % 24
            return f"{days}d{hours:02d}h"
        else:
            return f"{hours}h{minutes:02d}m"
    except:
        return "N/A"


def get_ip_address():
    """Get IP address"""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "N/A"


def display_system_info(lcd):
    """Display system information"""
    lcd.clear()
    
    # Title
    lcd.draw_text_centered(0, "SYS INFO", 1)
    lcd.draw_line(0, 9, 83, 9, 1)
    
    # System info
    cpu_temp = get_cpu_temp()
    cpu_usage = get_cpu_usage()
    mem_usage = get_memory_usage()
    uptime = get_uptime()
    
    lcd.draw_text(0, 12, f"CPU:{cpu_usage}", 1)
    lcd.draw_text(48, 12, cpu_temp, 1)
    lcd.draw_text(0, 21, f"MEM:{mem_usage}", 1)
    lcd.draw_text(0, 30, f"UP: {uptime}", 1)
    lcd.draw_text(0, 39, get_ip_address(), 1)
    
    lcd.display()


def display_welcome(lcd):
    """Display welcome screen"""
    lcd.clear()
    lcd.draw_rect(0, 0, 84, 48, 1)
    lcd.draw_text_centered(10, "WELCOME", 1)
    lcd.draw_text_centered(22, "TO", 1)
    lcd.draw_text_centered(32, "YOCTO", 1)
    lcd.display()


def display_time(lcd):
    """Display current time"""
    lcd.clear()
    
    # Get current time
    current_time = time.strftime("%H:%M:%S")
    current_date = time.strftime("%d/%m/%y")
    day_name = time.strftime("%A")[:3].upper()
    
    # Display
    lcd.draw_text_centered(5, current_time, 1)
    lcd.draw_line(0, 16, 83, 16, 1)
    lcd.draw_text_centered(22, current_date, 1)
    lcd.draw_text_centered(32, day_name, 1)
    
    lcd.display()


def main():
    """Main program"""
    print("Nokia 5110 System Monitor")
    print("=" * 50)
    print("Press Ctrl+C to exit")
    
    try:
        # Initialize display
        lcd = Nokia5110()
        print("✓ Display initialized")
        
        # Show welcome screen
        display_welcome(lcd)
        time.sleep(2)
        
        # Main loop - cycle through different screens
        screen = 0
        last_update = 0
        update_interval = 2  # seconds
        
        while True:
            current_time = time.time()
            
            if current_time - last_update >= update_interval:
                if screen == 0:
                    display_system_info(lcd)
                elif screen == 1:
                    display_time(lcd)
                
                screen = (screen + 1) % 2
                last_update = current_time
                
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n! Interrupted by user")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        lcd.cleanup()
        print("✓ Cleanup complete")


if __name__ == "__main__":
    main()
