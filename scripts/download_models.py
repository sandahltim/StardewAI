#!/usr/bin/env python3
"""
StardewAI Model Downloader
Downloads all VLM models for testing - ISOLATED from Gary
"""

from huggingface_hub import hf_hub_download
import os
import sys
from datetime import datetime

MODEL_DIR = '/home/tim/StardewAI/models'

DOWNLOADS = [
    # (repo_id, filename, description)

    # Qwen3-VL-8B-Thinking F16 (~16GB) - Smooth Gameplay
    ('Qwen/Qwen3-VL-8B-Thinking-GGUF', 'Qwen3VL-8B-Thinking-F16.gguf', 'Qwen3-VL-8B-Thinking F16'),
    ('Qwen/Qwen3-VL-8B-Thinking-GGUF', 'mmproj-Qwen3VL-8B-Thinking-F16.gguf', 'Qwen3-VL-8B-Thinking mmproj'),

    # Qwen3-VL-32B Q4_K_M (~22GB) - Complex Planning
    ('Qwen/Qwen3-VL-32B-Instruct-GGUF', 'Qwen3VL-32B-Instruct-Q4_K_M.gguf', 'Qwen3-VL-32B Q4_K_M'),
    ('Qwen/Qwen3-VL-32B-Instruct-GGUF', 'mmproj-Qwen3VL-32B-Instruct-Q8_0.gguf', 'Qwen3-VL-32B mmproj'),

    # Mistral 3.2 24B Q5_K_M (~18GB) - General Accuracy
    ('bartowski/mistralai_Mistral-Small-3.2-24B-Instruct-2506-GGUF',
     'mistralai_Mistral-Small-3.2-24B-Instruct-2506-Q5_K_M.gguf', 'Mistral-3.2-24B Q5_K_M'),
    ('bartowski/mistralai_Mistral-Small-3.2-24B-Instruct-2506-GGUF',
     'mmproj-mistralai_Mistral-Small-3.2-24B-Instruct-2506-f16.gguf', 'Mistral-3.2-24B mmproj'),
]

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=True)

def main():
    log("=" * 60)
    log("StardewAI Model Downloader")
    log(f"Target directory: {MODEL_DIR}")
    log("=" * 60)

    os.makedirs(MODEL_DIR, exist_ok=True)

    total = len(DOWNLOADS)
    for i, (repo, filename, desc) in enumerate(DOWNLOADS, 1):
        log(f"\n[{i}/{total}] Downloading: {desc}")
        log(f"  Repo: {repo}")
        log(f"  File: {filename}")

        target_path = os.path.join(MODEL_DIR, filename)
        if os.path.exists(target_path):
            size_gb = os.path.getsize(target_path) / (1024**3)
            log(f"  SKIP: Already exists ({size_gb:.2f} GB)")
            continue

        try:
            path = hf_hub_download(
                repo_id=repo,
                filename=filename,
                local_dir=MODEL_DIR
            )
            size_gb = os.path.getsize(path) / (1024**3)
            log(f"  DONE: {size_gb:.2f} GB")
        except Exception as e:
            log(f"  ERROR: {e}")

    log("\n" + "=" * 60)
    log("Download complete! Files in models directory:")
    log("=" * 60)
    for f in sorted(os.listdir(MODEL_DIR)):
        if f.endswith('.gguf'):
            size = os.path.getsize(os.path.join(MODEL_DIR, f)) / (1024**3)
            log(f"  {f}: {size:.2f} GB")

    log("\nAll downloads finished.")

if __name__ == '__main__':
    main()
