# import pygame
# import math
# import time
# import os
# import ctypes
# from ctypes import windll, wintypes, byref, c_ubyte
# import traceback

# # --- CONFIGURATION ---
# FPS = 60
# COLOR_CORE = (255, 255, 255)  # White
# COLOR_GLOW = (40, 200, 255)   # Cyan
# COLOR_BACKGROUND = (0, 0, 0, 0) # Fully transparent

# # --- WINDOWS API ---
# GWL_EXSTYLE = -20
# WS_EX_LAYERED = 0x00080000
# WS_EX_TOPMOST = 0x00000008
# WS_POPUP = 0x80000000
# ULW_ALPHA = 0x00000002
# AC_SRC_ALPHA = 0x01

# class POINT(ctypes.Structure):
#     _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

# class SIZE(ctypes.Structure):
#     _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

# class BLENDFUNCTION(ctypes.Structure):
#     _fields_ = [
#         ("BlendOp", c_ubyte),
#         ("BlendFlags", c_ubyte),
#         ("SourceConstantAlpha", c_ubyte),
#         ("AlphaFormat", c_ubyte)
#     ]

# def set_layered_style(hwnd):
#     """Sets the WS_EX_LAYERED style without setting a color key."""
#     user32 = ctypes.windll.user32
#     style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
#     # We Add LAYERED, TOPMOST and TRANSPARENT (for click-through)
#     user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TOPMOST)

# def update_window_per_pixel(hwnd, surface):
#     """
#     Uploads the Pygame surface to the Windows window using per-pixel alpha.
#     """
#     user32 = ctypes.windll.user32
#     gdi32 = ctypes.windll.gdi32

#     w, h = surface.get_size()

#     # 1. Get Pygame Pixel Data (BGRA)
#     # Windows expects BGRA (Blue-Green-Red-Alpha)
#     pixel_data = pygame.image.tostring(surface, 'BGRA', False)

#     # 2. Get DC
#     hdc_screen = user32.GetDC(0)
#     hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)

#     # 3. Create Bitmap Header
#     class BITMAPINFOHEADER(ctypes.Structure):
#         _fields_ = [
#             ("biSize", wintypes.DWORD),
#             ("biWidth", wintypes.LONG),
#             ("biHeight", wintypes.LONG),
#             ("biPlanes", wintypes.WORD),
#             ("biBitCount", wintypes.WORD),
#             ("biCompression", wintypes.DWORD),
#             ("biSizeImage", wintypes.DWORD),
#             ("biXPelsPerMeter", wintypes.LONG),
#             ("biYPelsPerMeter", wintypes.LONG),
#             ("biClrUsed", wintypes.DWORD),
#             ("biClrImportant", wintypes.DWORD)
#         ]

#     bmi = BITMAPINFOHEADER()
#     bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
#     bmi.biWidth = w
#     bmi.biHeight = -h  # Top-down
#     bmi.biPlanes = 1
#     bmi.biBitCount = 32
#     bmi.biCompression = 0 # BI_RGB

#     # 4. Create DIB Section and copy pixels
#     bits = ctypes.c_void_p()
#     hbitmap = gdi32.CreateDIBSection(hdc_mem, byref(bmi), 0, byref(bits), 0, 0)
    
#     if hbitmap:
#         gdi32.SelectObject(hdc_mem, hbitmap)
#         ctypes.memmove(bits, pixel_data, len(pixel_data))

#         # 5. Update Layered Window
#         pt_src = POINT(0, 0)
#         pt_win_pos = POINT(0, 0)
#         sz_win = SIZE(w, h)
#         blend = BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)

#         user32.UpdateLayeredWindow(
#             hwnd, hdc_screen, byref(pt_win_pos), byref(sz_win),
#             hdc_mem, byref(pt_src), 0, byref(blend), ULW_ALPHA
#         )
    
#     # Cleanup
#     if hbitmap: gdi32.DeleteObject(hbitmap)
#     gdi32.DeleteDC(hdc_mem)
#     user32.ReleaseDC(0, hdc_screen)

# def interpolate_color(c1, c2, ratio):
#     r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
#     g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
#     b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
#     return (r, g, b)

# def create_gradient_surface(width, height):
#     surf = pygame.Surface((width, height), pygame.SRCALPHA)
#     # IMPORTANT: Do not fill with black. Leave it fully transparent (0 alpha).
    
#     center_x = width // 2
#     center_y = height 
#     max_radius = width // 2
    
#     steps = 100
#     for i in range(steps):
#         prog = i / steps
#         radius_x = int(max_radius * (1 - prog))
#         radius_y = int(height * (1 - prog))
        
#         if radius_x <= 0 or radius_y <= 0: continue

#         if prog < 0.3:
#             ratio = prog / 0.3
#             c = interpolate_color(COLOR_CORE, COLOR_GLOW, ratio)
#             alpha = 180 
#         else:
#             c = COLOR_GLOW
#             alpha_prog = (prog - 0.3) / 0.7
#             alpha = int(120 * ((1 - alpha_prog)**2))

#         pygame.draw.ellipse(surf, (*c, alpha), 
#                             (center_x - radius_x, center_y - radius_y, radius_x*2, radius_y*2))
#     return surf

# def main():
#     print("Starting animation script...")
#     try:
#         pygame.init()
#         print("Pygame initialized.")
        
#         info = pygame.display.Info()
#         w, h = info.current_w, info.current_h
        
#         os.environ['SDL_VIDEO_WINDOW_POS'] = "0,0"
        
#         # [CRITICAL] Create Surface with SRCALPHA. 
#         # NOFRAME is standard, but we rely on Windows API for the actual transparency layer.
#         screen = pygame.display.set_mode((w, h), pygame.NOFRAME | pygame.SRCALPHA)
#         print(f"Display mode set: {w}x{h}")
        
#         hwnd = pygame.display.get_wm_info()["window"]
#         set_layered_style(hwnd)
#         print(f"Layered style set: {hwnd}")
        
#         # Assets
#         BASE_W = w + 200
#         BASE_H = 400
#         glow_surf = create_gradient_surface(BASE_W, BASE_H)
#         print("Gradient surface created.")
        
#         clock = pygame.time.Clock()
#         start_time = time.time()
        
#         print("Entering main loop...")
#         running = True
#         while running:
#             try:
#                 for event in pygame.event.get():
#                     if event.type == pygame.QUIT:
#                         running = False
                
#                 # 1. Clear Screen with Transparent Color
#                 # We use COLOR_BACKGROUND to create the shaded overlay effect
#                 screen.fill(COLOR_BACKGROUND)
                
#                 # 2. Animation
#                 t = time.time() - start_time
#                 pulse = 1.0 + math.sin(t * 2.0) * 0.05
                
#                 cur_w = int(BASE_W * pulse)
#                 cur_h = int(BASE_H * pulse)
                
#                 scaled_glow = pygame.transform.smoothscale(glow_surf, (cur_w, cur_h))
                
#                 x = (w // 2) - (cur_w // 2)
#                 y = h - cur_h + 120
                
#                 screen.blit(scaled_glow, (x, y))
                
#                 # 3. Send to Windows
#                 update_window_per_pixel(hwnd, screen)
                
#                 clock.tick(FPS)
#             except Exception as e:
#                  print(f"Error in loop: {e}")
#                  traceback.print_exc()
#                  running = False
        
#         print("Loop finished.")
#         pygame.quit()
#     except Exception as e:
#         print(f"CRITICAL ERROR in main: {e}")
#         traceback.print_exc()

# if __name__ == "__main__":
#     try:
#         main()
#     except Exception as e:
#         print(f"CRITICAL ERROR top-level: {e}")
#         traceback.print_exc()
