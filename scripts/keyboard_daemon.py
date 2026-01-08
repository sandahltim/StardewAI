#!/usr/bin/env python3
"""
Keyboard input daemon for StardewAI.

Sends keyboard input to Stardew Valley using xdotool.
Runs as HTTP server so Python agent can send commands.
"""

import subprocess
import time
import json
import signal
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

# Stardew Valley window ID (found at startup)
stardew_window = None

def find_stardew_window():
    """Find Stardew Valley window ID."""
    try:
        result = subprocess.run(
            ['xdotool', 'search', '--name', 'Stardew Valley'],
            capture_output=True, text=True, timeout=5
        )
        windows = result.stdout.strip().split('\n')
        if windows and windows[0]:
            return windows[0]  # Return first match
    except Exception as e:
        print(f"Warning: Could not find Stardew window: {e}")
    return None

def send_key(key, hold_time=0.1):
    """Send a key press to Stardew window."""
    global stardew_window

    if not stardew_window:
        stardew_window = find_stardew_window()
        if not stardew_window:
            return False, "Stardew window not found"

    try:
        # Send key down
        subprocess.run(
            ['xdotool', 'keydown', '--window', stardew_window, key],
            timeout=1
        )
        time.sleep(hold_time)
        # Send key up
        subprocess.run(
            ['xdotool', 'keyup', '--window', stardew_window, key],
            timeout=1
        )
        return True, f"Sent {key}"
    except Exception as e:
        return False, str(e)

def hold_key(key, duration):
    """Hold a key for specified duration."""
    global stardew_window

    if not stardew_window:
        stardew_window = find_stardew_window()
        if not stardew_window:
            return False, "Stardew window not found"

    try:
        subprocess.run(['xdotool', 'keydown', '--window', stardew_window, key], timeout=1)
        time.sleep(duration)
        subprocess.run(['xdotool', 'keyup', '--window', stardew_window, key], timeout=1)
        return True, f"Held {key} for {duration}s"
    except Exception as e:
        return False, str(e)

# Key mappings for Stardew (from default_options)
KEY_MAP = {
    'up': 'w',
    'down': 's',
    'left': 'a',
    'right': 'd',
    'action': 'x',      # Use tool / Confirm
    'cancel': 'v',      # Cancel
    'tool': 'c',        # Use tool
    'menu': 'e',        # Inventory/Menu
    'run': 'shift',     # Run modifier
    'chat': 't',
    'map': 'm',
    'journal': 'f',
}


class KeyboardHandler(BaseHTTPRequestHandler):
    """HTTP interface for keyboard commands."""

    def log_message(self, format, *args):
        pass  # Quiet logging

    def do_GET(self):
        if self.path == '/health':
            global stardew_window
            stardew_window = find_stardew_window()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "window": stardew_window,
                "window_found": stardew_window is not None
            }).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        response = {"success": True}

        try:
            if self.path == '/key':
                # Send a single key tap
                key = data.get('key', '').lower()
                mapped_key = KEY_MAP.get(key, key)
                hold_time = float(data.get('hold', 0.1))

                success, msg = send_key(mapped_key, hold_time)
                response = {"success": success, "message": msg}

            elif self.path == '/move':
                # Move in a direction for duration
                direction = data.get('direction', '').lower()
                duration = float(data.get('duration', 0.3))

                key = KEY_MAP.get(direction)
                if not key:
                    response = {"success": False, "error": f"Unknown direction: {direction}"}
                else:
                    success, msg = hold_key(key, duration)
                    response = {"success": success, "message": msg}

            elif self.path == '/walk':
                # Walk multiple tiles in a direction
                direction = data.get('direction', '').lower()
                tiles = int(data.get('tiles', 1))

                key = KEY_MAP.get(direction)
                if not key:
                    response = {"success": False, "error": f"Unknown direction: {direction}"}
                else:
                    # ~0.25s per tile at normal speed
                    duration = tiles * 0.25
                    success, msg = hold_key(key, duration)
                    response = {"success": success, "message": msg, "tiles": tiles}

            elif self.path == '/refresh_window':
                # Re-find Stardew window
                global stardew_window
                stardew_window = find_stardew_window()
                response = {"success": stardew_window is not None, "window": stardew_window}

            else:
                response = {"success": False, "error": f"Unknown endpoint: {self.path}"}

        except Exception as e:
            response = {"success": False, "error": str(e)}

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())


def shutdown(sig, frame):
    print("\nShutting down keyboard daemon...")
    sys.exit(0)


def main():
    global stardew_window
    port = 8792  # Keyboard daemon port

    print("Keyboard input daemon for StardewAI")
    print("Finding Stardew Valley window...")

    stardew_window = find_stardew_window()
    if stardew_window:
        print(f"✓ Found Stardew window: {stardew_window}")
    else:
        print("⚠ Stardew window not found (will retry on requests)")

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"\nKeyboard daemon listening on http://localhost:{port}")
    print("\nEndpoints:")
    print("  GET  /health              - Check status")
    print("  POST /key                 - {key: w/a/s/d/action/etc, hold: 0.1}")
    print("  POST /move                - {direction: up/down/left/right, duration: 0.3}")
    print("  POST /walk                - {direction: up/down/left/right, tiles: 3}")
    print("  POST /refresh_window      - Re-find Stardew window")
    print("\nPress Ctrl+C to stop.\n")

    server = HTTPServer(('localhost', port), KeyboardHandler)
    server.serve_forever()


if __name__ == '__main__':
    main()
