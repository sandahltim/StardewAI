#!/usr/bin/env python3
"""
Phase 0 Test: Vision-based Stardew Valley perception.

Run this with Stardew Valley open in windowed mode.
Captures screen and sends to Qwen3 VL for description.

Server setup:
- Nemotron: Ollama on localhost:11434
- Qwen3 VL: llama.cpp server on 100.104.77.44:8061
"""

import base64
import io
import sys
import json
from pathlib import Path

try:
    import httpx
    from mss import mss
    from PIL import Image
except ImportError:
    print("Missing dependencies. Run:")
    print("  pip install httpx mss pillow")
    sys.exit(1)


# Configuration
NEMOTRON_URL = "http://localhost:11434"
NEMOTRON_MODEL = "nemotron-3-nano:latest"

QWEN_URL = "http://100.104.77.44:8061"
QWEN_MODEL = "Qwen3VL-8B-Instruct-Q4_K_M.gguf"


def capture_screen(monitor: int = 1) -> Image.Image:
    """Capture the screen and return as PIL Image."""
    with mss() as sct:
        screenshot = sct.grab(sct.monitors[monitor])
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
    return img


def image_to_base64(img: Image.Image, max_size: int = 1920) -> str:
    """Convert PIL Image to base64 string, resizing if needed."""
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def query_nemotron(prompt: str) -> str:
    """Send text prompt to Nemotron via Ollama API."""
    payload = {
        "model": NEMOTRON_MODEL,
        "prompt": prompt,
        "stream": False,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{NEMOTRON_URL}/api/generate", json=payload)
            response.raise_for_status()
            return response.json().get("response", "No response")
    except httpx.ConnectError:
        return f"ERROR: Cannot connect to Nemotron at {NEMOTRON_URL}"
    except Exception as e:
        return f"ERROR: {e}"


def query_qwen_vision(image_b64: str, prompt: str) -> str:
    """Send image to Qwen3 VL via llama.cpp OpenAI-compatible API."""
    # llama.cpp uses OpenAI-compatible chat completions API
    payload = {
        "model": QWEN_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        "max_tokens": 1024,
        "temperature": 0.3,
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{QWEN_URL}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except httpx.ConnectError:
        return f"ERROR: Cannot connect to Qwen3 VL at {QWEN_URL}"
    except httpx.HTTPStatusError as e:
        return f"ERROR: HTTP {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"ERROR: {e}"


def test_nemotron_connection():
    """Test if Nemotron (Ollama) is reachable."""
    print(f"Testing Nemotron connection at {NEMOTRON_URL}...")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{NEMOTRON_URL}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = [m['name'] for m in models]
            print(f"  Connected! Models: {model_names[:5]}...")  # Show first 5
            if NEMOTRON_MODEL in model_names:
                print(f"  ✓ {NEMOTRON_MODEL} available")
            else:
                print(f"  ✗ {NEMOTRON_MODEL} not found!")
            return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def test_qwen_connection():
    """Test if Qwen3 VL (llama.cpp) is reachable."""
    print(f"Testing Qwen3 VL connection at {QWEN_URL}...")
    try:
        with httpx.Client(timeout=10.0) as client:
            # Check health
            response = client.get(f"{QWEN_URL}/health")
            response.raise_for_status()
            health = response.json()
            print(f"  Health: {health}")

            # Check models
            response = client.get(f"{QWEN_URL}/v1/models")
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            if models:
                caps = models[0].get("capabilities", [])
                print(f"  Model: {models[0]['name']}")
                print(f"  Capabilities: {caps}")
                if "multimodal" in caps:
                    print("  ✓ Vision supported!")
            return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def test_screen_capture():
    """Test screen capture."""
    print("Testing screen capture...")
    try:
        img = capture_screen()
        print(f"  Captured: {img.size[0]}x{img.size[1]}")

        test_path = Path(__file__).parent / "test_screenshot.png"
        img.save(test_path)
        print(f"  Saved to: {test_path}")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def test_perception():
    """Full perception test: capture screen and describe with Qwen3 VL."""
    print("\n" + "=" * 60)
    print("PERCEPTION TEST")
    print("Make sure Stardew Valley is visible on screen!")
    print("=" * 60)

    input("Press Enter when ready...")

    print("\nCapturing screen...")
    img = capture_screen()

    # Save for debugging
    test_path = Path(__file__).parent / "perception_test.png"
    img.save(test_path)
    print(f"  Saved screenshot to: {test_path}")

    img_b64 = image_to_base64(img, max_size=1280)  # Smaller for faster inference
    print(f"  Image size: {len(img_b64) // 1024}KB (base64)")

    perception_prompt = """You are the eyes of a Stardew Valley AI player.
Look at this screenshot and describe what you see:

1. What location is the player in?
2. What time is shown (top-right)?
3. What is the player character doing/holding?
4. What objects are nearby?
5. Is any menu or dialog open?
6. What items are in the toolbar (bottom)?

Be concise and accurate."""

    print("\nSending to Qwen3 VL for analysis (this may take 30-60s)...")
    result = query_qwen_vision(img_b64, perception_prompt)

    print("\n" + "-" * 40)
    print("QWEN3 VL PERCEPTION:")
    print("-" * 40)
    print(result)

    return result


def test_planning(perception: str):
    """Test planning with Nemotron based on perception."""
    print("\n" + "=" * 60)
    print("PLANNING TEST")
    print("=" * 60)

    planning_prompt = f"""You are the brain of a Stardew Valley AI co-op partner.

Your eyes (another AI) reported this about the current game state:
---
{perception}
---

Based on this, suggest 3 useful things the AI farmer could do right now.
For each suggestion, provide:
1. The action
2. Why it's useful
3. First step to execute it

Be practical and specific to Stardew Valley gameplay."""

    print("Sending to Nemotron for planning...")
    result = query_nemotron(planning_prompt)

    print("\n" + "-" * 40)
    print("NEMOTRON PLAN:")
    print("-" * 40)
    print(result)

    return result


def main():
    print("=" * 60)
    print("StardewAI - Phase 0 Vision Test")
    print("=" * 60)
    print(f"Nemotron: {NEMOTRON_URL} (Ollama)")
    print(f"Qwen3 VL: {QWEN_URL} (llama.cpp)")
    print("=" * 60 + "\n")

    # Test connections
    nemotron_ok = test_nemotron_connection()
    print()
    qwen_ok = test_qwen_connection()
    print()

    # Test screen capture
    capture_ok = test_screen_capture()

    if not capture_ok:
        print("\nScreen capture failed. Check permissions.")
        return

    # Run full test if Qwen is available
    if qwen_ok:
        perception = test_perception()

        if nemotron_ok and not perception.startswith("ERROR"):
            test_planning(perception)
    else:
        print("\nQwen3 VL not available - skipping perception test")
        print("Check that llama-server is running on vision server")

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
