#!/usr/bin/env python3
"""
On-Screen Virtual Controller GUI
Click buttons to send input to the virtual Xbox controller.
"""

import tkinter as tk
from tkinter import ttk
import vgamepad as vg
import threading
import time

class ControllerGUI:
    def __init__(self):
        self.gamepad = vg.VX360Gamepad()
        self.root = tk.Tk()
        self.root.title("Rusty Controller")
        self.root.attributes('-topmost', True)  # Always on top
        self.root.geometry("400x350")

        self.setup_ui()

    def setup_ui(self):
        # Main frame
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main, text="Virtual Xbox Controller", font=('Arial', 12, 'bold')).pack()
        ttk.Label(main, text="Click buttons to control Player 2", font=('Arial', 9)).pack()

        # D-Pad frame
        dpad_frame = ttk.LabelFrame(main, text="D-Pad", padding=5)
        dpad_frame.pack(pady=10)

        dpad_grid = ttk.Frame(dpad_frame)
        dpad_grid.pack()

        ttk.Button(dpad_grid, text="↑", width=4, command=lambda: self.dpad("up")).grid(row=0, column=1)
        ttk.Button(dpad_grid, text="←", width=4, command=lambda: self.dpad("left")).grid(row=1, column=0)
        ttk.Button(dpad_grid, text="→", width=4, command=lambda: self.dpad("right")).grid(row=1, column=2)
        ttk.Button(dpad_grid, text="↓", width=4, command=lambda: self.dpad("down")).grid(row=2, column=1)

        # Face buttons frame
        btn_frame = ttk.LabelFrame(main, text="Buttons", padding=5)
        btn_frame.pack(pady=10)

        btn_grid = ttk.Frame(btn_frame)
        btn_grid.pack()

        # Xbox layout: Y top, B right, A bottom, X left
        ttk.Button(btn_grid, text="Y", width=4, command=lambda: self.button("y")).grid(row=0, column=1)
        ttk.Button(btn_grid, text="X", width=4, command=lambda: self.button("x")).grid(row=1, column=0)
        ttk.Button(btn_grid, text="B", width=4, command=lambda: self.button("b")).grid(row=1, column=2)
        ttk.Button(btn_grid, text="A", width=4, command=lambda: self.button("a")).grid(row=2, column=1)

        # Special buttons
        special_frame = ttk.Frame(main)
        special_frame.pack(pady=10)

        ttk.Button(special_frame, text="START", width=8, command=lambda: self.button("start")).pack(side=tk.LEFT, padx=5)
        ttk.Button(special_frame, text="BACK", width=8, command=lambda: self.button("back")).pack(side=tk.LEFT, padx=5)

        # Shoulder buttons
        shoulder_frame = ttk.Frame(main)
        shoulder_frame.pack(pady=5)

        ttk.Button(shoulder_frame, text="LB", width=6, command=lambda: self.button("lb")).pack(side=tk.LEFT, padx=5)
        ttk.Button(shoulder_frame, text="RB", width=6, command=lambda: self.button("rb")).pack(side=tk.LEFT, padx=5)

        # Text entry for typing (uses keyboard simulation)
        text_frame = ttk.LabelFrame(main, text="Type Text (then press Send)", padding=5)
        text_frame.pack(pady=10, fill=tk.X)

        self.text_entry = ttk.Entry(text_frame)
        self.text_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
        ttk.Button(text_frame, text="Send", command=self.send_text).pack(side=tk.RIGHT)

        # Status
        self.status = ttk.Label(main, text="Ready", foreground="green")
        self.status.pack()

    def dpad(self, direction):
        """Press D-pad direction."""
        buttons = {
            "up": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
            "down": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
            "left": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
            "right": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
        }
        self._press(buttons[direction], f"D-Pad {direction}")

    def button(self, btn):
        """Press a button."""
        buttons = {
            "a": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
            "b": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
            "x": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
            "y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            "start": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
            "back": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
            "lb": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            "rb": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
        }
        self._press(buttons[btn], btn.upper())

    def _press(self, button, name):
        """Press and release a button."""
        def do_press():
            self.status.config(text=f"Pressing {name}...", foreground="blue")
            self.gamepad.press_button(button=button)
            self.gamepad.update()
            time.sleep(0.15)
            self.gamepad.release_button(button=button)
            self.gamepad.update()
            self.status.config(text=f"Pressed {name}", foreground="green")

        threading.Thread(target=do_press, daemon=True).start()

    def send_text(self):
        """Send text by typing on keyboard (for text fields)."""
        text = self.text_entry.get()
        if not text:
            return

        self.status.config(text=f"Use keyboard to type in game", foreground="orange")
        # Can't easily type with gamepad - show message
        print(f"Text to type: {text}")
        print("Note: For text entry, you may need to use Steam's on-screen keyboard")
        print("Try pressing A on the text field, then use Steam overlay (Shift+Tab) keyboard")

    def run(self):
        """Run the GUI."""
        print("Controller GUI running - click buttons to control Player 2")
        print("Window is always-on-top")
        self.root.mainloop()

if __name__ == "__main__":
    gui = ControllerGUI()
    gui.run()
