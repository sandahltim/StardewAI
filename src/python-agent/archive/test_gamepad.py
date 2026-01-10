#!/usr/bin/env python3
"""
Test script to create and hold a virtual Xbox controller.
Run this, then check if Stardew Valley detects it in Options > Controls.
"""
import vgamepad as vg
import time

print("Creating virtual Xbox 360 controller...")
gamepad = vg.VX360Gamepad()
gamepad.reset()
gamepad.update()
print("✅ Virtual controller active at /dev/input/js0")
print("\nNow check Stardew Valley:")
print("  1. Open Options > Controls")
print("  2. Look for 'Controller Layout' option")
print("  3. The game should show controller prompts if detected")
print("\nPress Ctrl+C to exit and remove the virtual controller")
print("Sending periodic inputs to keep controller alive...\n")

try:
    tick = 0
    while True:
        # Small periodic input to ensure controller stays registered
        gamepad.left_joystick(x_value=0, y_value=0)
        gamepad.update()
        tick += 1
        if tick % 10 == 0:
            print(f"  Controller active... ({tick}s)")
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\nCleaning up...")
    gamepad.reset()
    gamepad.update()
    print("Virtual controller removed.")
