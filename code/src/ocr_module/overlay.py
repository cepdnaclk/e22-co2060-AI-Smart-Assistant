import tkinter as tk
from tkinter import Canvas

class RegionSelection:
    def __init__(self):
        self.selection = None
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.glow_rects = []

    def get_region(self):
        """
        Opens a full-screen overlay to let the user select a region.
        Returns a tuple (x1, y1, x2, y2) or None if cancelled.
        """
        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.3)  # Semi-transparent
        self.root.attributes("-topmost", True)
        self.root.config(cursor="cross")
        
        # Darkening the screen
        self.root.configure(bg="black")

        # Use a slightly darker alpha for more contrast with the glow
        self.root.attributes("-alpha", 0.5)

        self.canvas = Canvas(self.root, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        # Make the canvas slightly transparent to see through
        self.root.attributes("-transparentcolor", "white") 

        # However, standard tkinter doesn't support easy "cut out" selection transparency effectively without complex hacks on some systems.
        # A simpler approach for the overlay:
        # 1. Full screen window, alpha 0.3 (greyed out).
        # 2. Draw a rectangle that represents the selection.
        # Since we just need coordinates, visual feedback of a red rectangle is enough.

        # Draw full screen glow border
        self.root.update_idletasks()
        w = self.root.winfo_screenwidth()
        h = self.root.winfo_screenheight()
        
        # Draw concentric rectangles at the edge
        # Outer -> Inner
        colors = ['#004466', '#0088AA', '#00BBEE', '#00FFFF']
        widths = [8, 6, 4, 2]
        
        for i in range(4):
            offset = i * 2
            self.canvas.create_rectangle(
                offset, offset, w-offset, h-offset,
                outline=colors[i], width=widths[i], state='disabled'
            )

        self.canvas.bind("<Button-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.canvas.bind("<Escape>", self.cancel)

        # Force focus
        self.root.focus_force()
        self.root.mainloop()

        return self.selection

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        
        # We removed the intense selection glow as per user request to focus on edge glow
        # Keeping a simple clean Cyan selection box
        if self.current_rect:
            self.canvas.delete(self.current_rect)

        self.current_rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='#00FFFF', width=2)


    def on_move_press(self, event):
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.current_rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x, end_y = (event.x, event.y)
        # Ensure coordinates are top-left and bottom-right
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        # Only accept if width and height > 0
        if x2 - x1 > 0 and y2 - y1 > 0:
            self.selection = (x1, y1, x2, y2)
        
        self.root.quit()
        self.root.destroy()

    def cancel(self, event):
        self.selection = None
        self.root.quit()
        self.root.destroy()

if __name__ == "__main__":
    # Test
    r = RegionSelection()
    print(r.get_region())