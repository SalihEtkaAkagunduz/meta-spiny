#!/usr/bin/env python3
"""
Nokia 5110 Simple Text Display
Quick test program for Nokia 5110 LCD
"""

import sys
import time

try:
    from nokia5110_driver import Nokia5110
except ImportError:
    print("Error: nokia5110_driver.py not found!")
    sys.exit(1)


def main():
    """Main function"""
    
    # Get text from command line arguments
    if len(sys.argv) > 1:
        text = ' '.join(sys.argv[1:])
    else:
        text = "Hello\nWorld!\nNokia\n5110"
    
    try:
        # Initialize display
        print("Initializing Nokia 5110 display...")
        lcd = Nokia5110()
        
        # Clear and display text
        lcd.clear()
        lcd.draw_text(0, 0, text, 1)
        lcd.display()
        
        print(f"Displayed: {text}")
        print("Text will remain on screen until next update")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
