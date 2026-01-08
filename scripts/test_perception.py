#!/usr/bin/env python3
"""Test perception accuracy across different models."""

import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import mss
import requests
from PIL import Image

SERVER_URL = "http://localhost:8780"
MODELS = [
    "Qwen3VL-30B-A3B-Instruct-Q4_K_M",
    "Qwen3VL-8B-Thinking-F16",
    "Qwen3VL-32B-Instruct-Q4_K_M",
    "Mistral-Small-3.2-24B-Instruct-2503-Q5_K_M",
]

PERCEPTION_PROMPT = """Look at this Stardew Valley screenshot and identify:

1. Location (Farm, House, Town, Beach, Mine, Forest, Shop, etc.)
2. Exact time shown in top-right (format: H:MM AM/PM)
3. Day/date shown (e.g., "Mon. 1")
4. Energy level (look at green bar bottom-right: full/good/half/low/exhausted)
5. Currently held item (look at toolbar - which slot is selected with red border?)
6. Is any menu/dialog open? (inventory, shop, dialogue box, etc.)
7. Weather (sunny, rainy, etc. - look at icon in top-right)
8. What objects/NPCs are visible nearby?

RESPOND ONLY WITH JSON:
{
  "location": "...",
  "time": "...",
  "day": "...",
  "energy": "...",
  "holding": "...",
  "menu_open": true/false,
  "weather": "...",
  "nearby": ["..."]
}
"""


def capture_screen(monitor=1):
    """Capture screen and return base64."""
    with mss.mss() as sct:
        img = sct.grab(sct.monitors[monitor])
        pil_img = Image.frombytes('RGB', img.size, img.bgra, 'raw', 'BGRX')
        # Resize for faster processing
        pil_img.thumbnail((1280, 1280))
        # Save for reference
        pil_img.save("logs/screenshots/perception_test.png")
        # Convert to base64
        import io
        buffer = io.BytesIO()
        pil_img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()


def test_perception(image_b64):
    """Send image to current model and get perception."""
    start = time.time()

    response = requests.post(
        f"{SERVER_URL}/v1/chat/completions",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        {"type": "text", "text": PERCEPTION_PROMPT}
                    ]
                }
            ],
            "max_tokens": 400,
            "temperature": 0.3,
        },
        timeout=60
    )

    latency = (time.time() - start) * 1000
    data = response.json()

    content = data["choices"][0]["message"]["content"]
    tokens = data.get("usage", {}).get("completion_tokens", 0)
    tok_per_sec = tokens / (latency / 1000) if latency > 0 else 0

    # Parse JSON from response
    try:
        # Try to extract JSON
        import re
        json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if json_match:
            perception = json.loads(json_match.group())
        else:
            perception = {"raw": content}
    except:
        perception = {"raw": content}

    return {
        "latency_ms": round(latency),
        "tokens": tokens,
        "tok_per_sec": round(tok_per_sec, 1),
        "perception": perception,
        "raw": content
    }


def switch_model(model_name):
    """Restart server with different model."""
    print(f"\n{'='*60}")
    print(f"Switching to: {model_name}")
    print(f"{'='*60}")

    # Kill existing server
    subprocess.run(["pkill", "-f", "llama-server"], capture_output=True)
    time.sleep(2)

    # Start with new model
    subprocess.Popen(
        ["bash", "scripts/start-llama-server.sh", model_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Wait for server to be ready
    for i in range(60):
        try:
            r = requests.get(f"{SERVER_URL}/health", timeout=2)
            if r.json().get("status") == "ok":
                print("Server ready!")
                return True
        except:
            pass
        time.sleep(2)
        print(f"Waiting... ({i+1})")

    print("Server failed to start!")
    return False


def main():
    # Capture current screen
    print("Capturing screen...")
    image_b64 = capture_screen()
    print(f"Saved to logs/screenshots/perception_test.png")

    results = {}

    # Test each model
    for model in MODELS:
        if not switch_model(model):
            results[model] = {"error": "Failed to start"}
            continue

        print(f"\nTesting perception...")
        result = test_perception(image_b64)
        results[model] = result

        print(f"  Latency: {result['latency_ms']}ms")
        print(f"  Tokens: {result['tokens']} ({result['tok_per_sec']} tok/s)")
        print(f"  Perception: {json.dumps(result['perception'], indent=2)}")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"{'Model':<45} {'Latency':<10} {'tok/s':<8}")
    print("-"*60)
    for model, result in results.items():
        if "error" in result:
            print(f"{model:<45} ERROR")
        else:
            print(f"{model:<45} {result['latency_ms']:<10} {result['tok_per_sec']:<8}")

    # Save results
    Path("logs").mkdir(exist_ok=True)
    with open("logs/perception_comparison.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to logs/perception_comparison.json")


if __name__ == "__main__":
    main()
