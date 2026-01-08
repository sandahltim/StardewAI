#!/usr/bin/env python3
"""
Persistent virtual Xbox 360 controller for StardewAI.

Run this BEFORE starting Stardew Valley so the game detects the controller.
Then the Python agent can import and use the shared controller instance.
"""

import vgamepad as vg
import time
import sys
import signal
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Global controller instance
controller = None

class ControllerHandler(BaseHTTPRequestHandler):
    """HTTP interface for controller commands."""

    def log_message(self, format, *args):
        # Quieter logging
        pass

    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "controller": "active"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global controller

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        response = {"success": True}

        try:
            if self.path == '/move':
                # Move left stick: x,y from -1.0 to 1.0
                x = float(data.get('x', 0))
                y = float(data.get('y', 0))
                controller.left_joystick_float(x_value_float=x, y_value_float=y)
                controller.update()
                response["action"] = f"move({x}, {y})"

            elif self.path == '/button':
                # Press/release a button
                button = data.get('button', 'A').upper()
                action = data.get('action', 'press')  # press, release, tap
                duration = float(data.get('duration', 0.1))

                button_map = {
                    'A': vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
                    'B': vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
                    'X': vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
                    'Y': vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
                    'START': vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
                    'BACK': vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
                    'LB': vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
                    'RB': vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
                    'DPAD_UP': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
                    'DPAD_DOWN': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
                    'DPAD_LEFT': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
                    'DPAD_RIGHT': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
                }

                btn = button_map.get(button)
                if btn is None:
                    response = {"success": False, "error": f"Unknown button: {button}"}
                else:
                    if action == 'press':
                        controller.press_button(btn)
                        controller.update()
                    elif action == 'release':
                        controller.release_button(btn)
                        controller.update()
                    elif action == 'tap':
                        controller.press_button(btn)
                        controller.update()
                        time.sleep(duration)
                        controller.release_button(btn)
                        controller.update()
                    response["action"] = f"button {button} {action}"

            elif self.path == '/release_all':
                # Release all buttons and center sticks
                controller.reset()
                controller.update()
                response["action"] = "release_all"

            else:
                response = {"success": False, "error": f"Unknown endpoint: {self.path}"}

        except Exception as e:
            response = {"success": False, "error": str(e)}

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())


def shutdown(sig, frame):
    print("\nShutting down controller...")
    if controller:
        controller.reset()
        controller.update()
    sys.exit(0)


def main():
    global controller

    port = 8791  # Controller daemon port

    print("Creating virtual Xbox 360 controller...")
    controller = vg.VX360Gamepad()
    controller.update()
    print("✓ Controller created")

    # Register cleanup
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"\nController daemon listening on http://localhost:{port}")
    print("\nEndpoints:")
    print("  GET  /health          - Check status")
    print("  POST /move            - {x: -1..1, y: -1..1}")
    print("  POST /button          - {button: A/B/X/Y/..., action: press/release/tap}")
    print("  POST /release_all     - Reset all inputs")
    print("\nStart Stardew Valley now - it will detect this controller.")
    print("Press Ctrl+C to stop.\n")

    server = HTTPServer(('localhost', port), ControllerHandler)
    server.serve_forever()


if __name__ == '__main__':
    main()
