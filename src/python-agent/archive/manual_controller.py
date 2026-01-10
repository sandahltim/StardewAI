#!/usr/bin/env python3
"""
Manual Controller - Interactive gamepad for P2 character creation and testing.

Keyboard controls:
  WASD     - D-pad / Left stick movement
  SPACE    - A button (confirm/interact)
  E        - B button (cancel/back)
  Q        - X button (use tool)
  R        - Y button (crafting)
  TAB      - Start button
  1/2      - LB/RB (toolbar cycle)
  ESC      - Quit

Run: python manual_controller.py
"""

import sys
import time

try:
    import vgamepad as vg
except ImportError:
    print("ERROR: vgamepad not installed. Run: pip install vgamepad")
    sys.exit(1)

try:
    import readchar
except ImportError:
    print("ERROR: readchar not installed. Run: pip install readchar")
    sys.exit(1)


def main():
    print("=" * 50)
    print("  Manual Controller - Player 2 Gamepad")
    print("=" * 50)
    print()
    print("Creating virtual Xbox 360 controller...")

    gamepad = vg.VX360Gamepad()
    gamepad.reset()
    gamepad.update()

    print("Controller ready!")
    print()
    print("Controls:")
    print("  WASD   - Move (left stick)")
    print("  SPACE  - A (confirm/interact)")
    print("  E      - B (cancel/back/menu)")
    print("  Q      - X (use tool)")
    print("  R      - Y (crafting)")
    print("  TAB    - Start")
    print("  `      - Back/Select")
    print("  1/2    - LB/RB (toolbar)")
    print("  Arrow keys - D-pad")
    print("  ESC    - Quit")
    print()
    print("Waiting for input... (press ESC to quit)")
    print()

    # Button mapping
    buttons = {
        ' ': vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
        'e': vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
        'q': vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
        'r': vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
        '\t': vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
        '`': vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
        '1': vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
        '2': vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
    }

    # D-pad mapping (arrow keys come as escape sequences)
    dpad = {
        'A': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,      # Up arrow
        'B': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,    # Down arrow
        'C': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,   # Right arrow
        'D': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,    # Left arrow
    }

    # Movement directions (left stick)
    move_dirs = {
        'w': (0.0, 1.0),    # Up
        's': (0.0, -1.0),   # Down
        'a': (-1.0, 0.0),   # Left
        'd': (1.0, 0.0),    # Right
    }

    try:
        while True:
            char = readchar.readchar()

            # ESC to quit
            if char == '\x1b':
                # Check if it's an arrow key sequence
                next1 = readchar.readchar()
                if next1 == '[':
                    arrow = readchar.readchar()
                    if arrow in dpad:
                        btn = dpad[arrow]
                        gamepad.press_button(button=btn)
                        gamepad.update()
                        print(f"D-PAD: {arrow}")
                        time.sleep(0.1)
                        gamepad.release_button(button=btn)
                        gamepad.update()
                        continue
                # Just ESC - quit
                print("\nQuitting...")
                break

            # Button press
            if char.lower() in buttons:
                btn = buttons[char.lower()]
                gamepad.press_button(button=btn)
                gamepad.update()
                print(f"BUTTON: {char!r}")
                time.sleep(0.15)
                gamepad.release_button(button=btn)
                gamepad.update()

            # Movement (left stick)
            elif char.lower() in move_dirs:
                x, y = move_dirs[char.lower()]
                gamepad.left_joystick_float(x_value_float=x, y_value_float=y)
                gamepad.update()
                print(f"MOVE: {char.upper()}")
                time.sleep(0.2)
                gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
                gamepad.update()

            else:
                print(f"Unknown key: {char!r}")

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        gamepad.reset()
        gamepad.update()
        print("Controller released.")


if __name__ == "__main__":
    main()
