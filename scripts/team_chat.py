#!/usr/bin/env python3
"""
Team Chat CLI - Quick access to team communication channel.

Usage:
    # Post a message
    ./scripts/team_chat.py post claude "Movement test passed"
    ./scripts/team_chat.py post tim "Starting the game now"

    # Read recent messages
    ./scripts/team_chat.py read
    ./scripts/team_chat.py read --limit 20

    # Watch for new messages (polls every 2s)
    ./scripts/team_chat.py watch
"""

import argparse
import json
import sys
import time
from datetime import datetime

import requests

UI_BASE_URL = "http://localhost:9001"


def post_message(sender: str, content: str) -> None:
    """Post a message to team chat."""
    try:
        resp = requests.post(
            f"{UI_BASE_URL}/api/team",
            json={"sender": sender, "content": content},
            timeout=5,
        )
        resp.raise_for_status()
        msg = resp.json()
        print(f"[{msg['sender']}] {msg['content']}")
    except requests.exceptions.ConnectionError:
        print(f"ERROR: UI server not running at {UI_BASE_URL}", file=sys.stderr)
        print("Start with: uvicorn src.ui.app:app --port 9001", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def read_messages(limit: int = 50) -> None:
    """Read recent team messages."""
    try:
        resp = requests.get(
            f"{UI_BASE_URL}/api/team",
            params={"limit": limit},
            timeout=5,
        )
        resp.raise_for_status()
        messages = resp.json()

        if not messages:
            print("No messages yet.")
            return

        for msg in messages:
            ts = msg['created_at'][:16].replace('T', ' ')
            sender = msg['sender'].upper()
            print(f"[{ts}] {sender}: {msg['content']}")

    except requests.exceptions.ConnectionError:
        print(f"ERROR: UI server not running at {UI_BASE_URL}", file=sys.stderr)
        sys.exit(1)


def watch_messages(poll_interval: float = 2.0) -> None:
    """Watch for new messages in real-time."""
    print(f"Watching team chat (Ctrl+C to stop)...")
    print("-" * 50)

    last_id = 0

    # Get existing messages first
    try:
        resp = requests.get(f"{UI_BASE_URL}/api/team", params={"limit": 10}, timeout=5)
        resp.raise_for_status()
        messages = resp.json()
        if messages:
            for msg in messages:
                ts = msg['created_at'][:16].replace('T', ' ')
                sender = msg['sender'].upper()
                print(f"[{ts}] {sender}: {msg['content']}")
            last_id = messages[-1]['id']
        print("-" * 50)
    except Exception as e:
        print(f"ERROR connecting: {e}", file=sys.stderr)
        sys.exit(1)

    # Poll for new messages
    try:
        while True:
            time.sleep(poll_interval)
            try:
                resp = requests.get(
                    f"{UI_BASE_URL}/api/team",
                    params={"since_id": last_id},
                    timeout=5,
                )
                resp.raise_for_status()
                messages = resp.json()

                for msg in messages:
                    ts = msg['created_at'][:16].replace('T', ' ')
                    sender = msg['sender'].upper()
                    print(f"[{ts}] {sender}: {msg['content']}")
                    last_id = msg['id']

            except requests.exceptions.ConnectionError:
                print("(connection lost, retrying...)")

    except KeyboardInterrupt:
        print("\nStopped watching.")


def main():
    parser = argparse.ArgumentParser(description="Team Chat CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # post command
    post_parser = subparsers.add_parser("post", help="Post a message")
    post_parser.add_argument("sender", choices=["claude", "codex", "tim"], help="Who is sending")
    post_parser.add_argument("content", help="Message content")

    # read command
    read_parser = subparsers.add_parser("read", help="Read recent messages")
    read_parser.add_argument("--limit", type=int, default=50, help="Number of messages")

    # watch command
    watch_parser = subparsers.add_parser("watch", help="Watch for new messages")
    watch_parser.add_argument("--interval", type=float, default=2.0, help="Poll interval in seconds")

    args = parser.parse_args()

    if args.command == "post":
        post_message(args.sender, args.content)
    elif args.command == "read":
        read_messages(args.limit)
    elif args.command == "watch":
        watch_messages(args.interval)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
