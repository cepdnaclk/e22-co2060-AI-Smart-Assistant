import tkinter as tk
import multiprocessing
import queue
import datetime

def _launch_chat_window(msg_queue):
    # --- Theme Configuration ---
    BG_COLOR = "#1E1E2E"      
    ACCENT_COLOR = "#89B4FA"  
    INPUT_BG = "#313244"      
    USER_BUBBLE_BG = "#45475A"
    SYSTEM_BUBBLE_BG = "#313244"
    TEXT_COLOR = "#CDD6F4"
    TIME_COLOR = "#585B70" # Subtle color for the clock
    
    WINDOW_RADIUS = 20  
    BUBBLE_RADIUS = 15 

    root = tk.Tk()
    root.overrideredirect(True) 
    root.attributes("-topmost", True)
    root.config(bg="#000001")
    root.attributes("-transparentcolor", "#000001")

    # Geometry logic
    sh = root.winfo_screenheight()
    h = sh - 100
    w = 400
    sw = root.winfo_screenwidth()
    root.geometry(f"{w}x{h}+{sw - w - 20}+{sh - h - 60}")
    root.withdraw()

    def draw_rounded_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
        points = [x1+radius, y1, x1+radius, y1, x2-radius, y1, x2-radius, y1, x2, y1, x2, y1+radius, x2, y1+radius, x2, y2-radius, x2, y2-radius, x2, y2, x2-radius, y2, x2-radius, y2, x1+radius, y2, x1+radius, y2, x1, y2, x1, y2-radius, x1, y2-radius, x1, y1+radius, x1, y1+radius, x1, y1]
        return canvas.create_polygon(points, **kwargs, smooth=True)

    # Main Window Canvas
    main_canvas = tk.Canvas(root, width=w, height=h, bg="#000001", highlightthickness=0)
    main_canvas.pack()
    draw_rounded_rect(main_canvas, 2, 2, w-2, h-2, WINDOW_RADIUS, fill=BG_COLOR, outline=ACCENT_COLOR, width=2)

    content_frame = tk.Frame(root, bg=BG_COLOR, bd=0)
    content_frame.place(x=15, y=15, width=w-30, height=h-30)

    # --- Header ---
    header = tk.Frame(content_frame, bg=BG_COLOR)
    header.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))
    tk.Label(header, text="AI ASSISTANT", bg=BG_COLOR, fg=ACCENT_COLOR, font=("Segoe UI Semibold", 10)).pack(side=tk.LEFT)
    tk.Button(header, text="✕", command=root.withdraw, bg=BG_COLOR, fg="#F38BA8", bd=0, font=("Arial", 11)).pack(side=tk.RIGHT, padx=2)

    # --- Scrollable Chat Area ---
    chat_canvas = tk.Canvas(content_frame, bg=BG_COLOR, highlightthickness=0)
    chat_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    
    bubble_frame = tk.Frame(chat_canvas, bg=BG_COLOR)
    chat_canvas.create_window((0, 0), window=bubble_frame, anchor="nw", width=w-40)

    def on_configure(event):
        chat_canvas.configure(scrollregion=chat_canvas.bbox("all"))
    bubble_frame.bind("<Configure>", on_configure)

    # --- Bubble Logic with Timestamps ---
    def add_message(text, sender="system"):
        # Container for the row
        row_frame = tk.Frame(bubble_frame, bg=BG_COLOR, pady=10)
        row_frame.pack(fill=tk.X, expand=True)

        # Time string
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        
        # Dynamic sizing logic
        lines = (len(text) // 32) + 1
        bubble_h = (lines * 22) + 20
        bubble_w = 260
        bg_color = USER_BUBBLE_BG if sender == "user" else SYSTEM_BUBBLE_BG
        align = tk.RIGHT if sender == "user" else tk.LEFT
        
        # 1. Create Time Label
        time_lbl = tk.Label(row_frame, text=current_time, font=("Segoe UI", 7), fg=TIME_COLOR, bg=BG_COLOR)
        
        # 2. Create Bubble Canvas
        b_canvas = tk.Canvas(row_frame, width=bubble_w, height=bubble_h, bg=BG_COLOR, highlightthickness=0)
        
        if sender == "user":
            b_canvas.pack(side=tk.RIGHT, padx=(5, 10))
            time_lbl.pack(side=tk.RIGHT, anchor="s", padx=2) # Time on left of user bubble
        else:
            b_canvas.pack(side=tk.LEFT, padx=(10, 5))
            time_lbl.pack(side=tk.LEFT, anchor="s", padx=2) # Time on right of system bubble

        # Draw bubble shape
        draw_rounded_rect(b_canvas, 2, 2, bubble_w-2, bubble_h-2, BUBBLE_RADIUS, fill=bg_color)
        
        # Add Text
        lbl = tk.Label(b_canvas, text=text, bg=bg_color, fg="white", wraplength=bubble_w-30, justify=tk.LEFT, font=("Segoe UI", 10))
        b_canvas.create_window(bubble_w//2, bubble_h//2, window=lbl)

        # Auto-scroll
        root.update_idletasks()
        chat_canvas.yview_moveto(1.0)

    # --- Input Section (Maintains existing radius) ---
    input_canvas_height = 60
    input_container = tk.Canvas(content_frame, height=input_canvas_height, bg=BG_COLOR, highlightthickness=0)
    input_container.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
    draw_rounded_rect(input_container, 2, 2, w-32, input_canvas_height-2, 15, fill=INPUT_BG)

    input_box = tk.Text(input_container, bg=INPUT_BG, fg="white", bd=0, font=("Segoe UI", 10), insertbackground="white")
    
    def send_action(event=None):
        content = input_box.get("1.0", tk.END).strip()
        if content:
            add_message(content, sender="user")
            input_box.delete("1.0", tk.END)
        return "break"

    send_btn = tk.Button(input_container, text="➤", command=send_action, bg=INPUT_BG, fg=ACCENT_COLOR, bd=0, font=("Segoe UI", 14), cursor="hand2")
    input_container.create_window((w-85)//2, input_canvas_height//2, window=input_box, width=w-110, height=input_canvas_height-20)
    input_container.create_window(w-60, input_canvas_height//2, window=send_btn)
    input_box.bind("<Return>", send_action)

    def check_queue():
        try:
            while True:
                msg_data = msg_queue.get_nowait()
                if msg_data:
                    # Check if data is a dict (sender + text) or just a string
                    if isinstance(msg_data, dict):
                        sender = msg_data.get("sender", "system")
                        message = msg_data.get("text", "")
                    else:
                        sender = "system"
                        message = msg_data

                    root.deiconify() # Bring window to front
                    root.attributes("-topmost", True)
                    add_message(message, sender=sender) # Use your new bubble logic
                    input_box.focus_set()
        except queue.Empty:
            pass
        root.after(100, check_queue)

    root.after(100, check_queue)
    root.mainloop()

def start_chat_process():
    msg_queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=_launch_chat_window, args=(msg_queue,), daemon=True)
    p.start()
    return msg_queue, p