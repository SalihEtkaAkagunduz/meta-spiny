#!/usr/bin/env python3
"""
Touch Drawing Application
Simple drawing app for touchscreen LCD
"""

import sys

try:
    import tkinter as tk
except ImportError:
    print("Error: tkinter not available")
    sys.exit(1)

class TouchDraw:
    def __init__(self):
        self.width = 480
        self.height = 320
        
        self.root = tk.Tk()
        self.root.title("Touch Draw")
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.configure(bg='white')
        
        try:
            self.root.attributes('-fullscreen', True)
        except:
            pass
        
        self.current_color = 'black'
        self.brush_size = 3
        self.old_x = None
        self.old_y = None
        
        self.setup_gui()
    
    def setup_gui(self):
        """Setup drawing interface"""
        # Top bar with controls
        control_frame = tk.Frame(self.root, bg='#2c3e50', height=50)
        control_frame.pack(side='top', fill='x')
        control_frame.pack_propagate(False)
        
        # Color buttons
        colors = [
            ('Black', 'black'),
            ('Red', 'red'),
            ('Blue', 'blue'),
            ('Green', 'green'),
            ('Yellow', 'yellow')
        ]
        
        for name, color in colors:
            btn = tk.Button(control_frame, text=name, 
                          command=lambda c=color: self.set_color(c),
                          bg=color, fg='white' if color != 'yellow' else 'black',
                          width=6, height=1)
            btn.pack(side='left', padx=2, pady=5)
        
        # Clear button
        clear_btn = tk.Button(control_frame, text='Clear', 
                            command=self.clear_canvas,
                            bg='#e74c3c', fg='white', width=6, height=1)
        clear_btn.pack(side='left', padx=2, pady=5)
        
        # Close button
        close_btn = tk.Button(control_frame, text='Close', 
                            command=self.root.destroy,
                            bg='#95a5a6', fg='white', width=6, height=1)
        close_btn.pack(side='right', padx=2, pady=5)
        
        # Canvas for drawing
        self.canvas = tk.Canvas(self.root, bg='white', cursor='crosshair')
        self.canvas.pack(expand=True, fill='both')
        
        # Bind mouse/touch events
        self.canvas.bind('<Button-1>', self.start_draw)
        self.canvas.bind('<B1-Motion>', self.draw)
        self.canvas.bind('<ButtonRelease-1>', self.reset)
        
        # Welcome message
        self.canvas.create_text(
            self.width // 2, self.height // 2,
            text="Touch or click to draw!",
            font=('Helvetica', 20),
            fill='lightgray',
            tags='welcome'
        )
        
        self.root.mainloop()
    
    def set_color(self, color):
        """Change drawing color"""
        self.current_color = color
    
    def clear_canvas(self):
        """Clear the canvas"""
        self.canvas.delete('all')
    
    def start_draw(self, event):
        """Start drawing"""
        self.canvas.delete('welcome')
        self.old_x = event.x
        self.old_y = event.y
    
    def draw(self, event):
        """Draw on canvas"""
        if self.old_x and self.old_y:
            self.canvas.create_line(
                self.old_x, self.old_y, event.x, event.y,
                width=self.brush_size, fill=self.current_color,
                capstyle=tk.ROUND, smooth=True
            )
        self.old_x = event.x
        self.old_y = event.y
    
    def reset(self, event):
        """Reset drawing position"""
        self.old_x = None
        self.old_y = None

if __name__ == "__main__":
    try:
        TouchDraw()
    except KeyboardInterrupt:
        print("\nDrawing app closed")
        sys.exit(0)
