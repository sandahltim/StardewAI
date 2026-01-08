#!/bin/bash
# =============================================================================
# StardewAI LLaMA Server Startup Script
# COMPLETELY ISOLATED FROM GARY - Uses different port, different models
# =============================================================================

set -e

# Configuration
LLAMA_SERVER="/Gary/llama.cpp/build/bin/llama-server"
LLAMA_LIB_DIR="/Gary/llama.cpp/build/bin"
MODEL_DIR="/home/tim/StardewAI/models"
LOG_DIR="/home/tim/StardewAI/logs"
PORT=8780  # Isolated: Gary llama=8034, Gary API=8765, nginx=8766

# Set library path for CUDA support
export LD_LIBRARY_PATH="${LLAMA_LIB_DIR}:${LD_LIBRARY_PATH:-}"

# GPU ordering - CRITICAL: CUDA device order differs from nvidia-smi!
# Use UUIDs to ensure 3090 Ti is CUDA0, 4070 is CUDA1 (for tensor-split)
export CUDA_VISIBLE_DEVICES="GPU-10495487-d4ed-4e22-9d9a-14f16b8ea0b3,GPU-fb1bf618-f91b-d2a8-f1e0-0161e11ece56"

# Default model (can be overridden with --model)
MODEL_NAME="${1:-Qwen3VL-30B-A3B-Instruct-Q4_K_M}"

# Find model and mmproj files
find_model() {
    local name="$1"
    local model_file=""
    local mmproj_file=""

    # Search for model file
    for f in "$MODEL_DIR"/*.gguf; do
        if [[ "$(basename "$f")" == *"$name"* ]] && [[ "$(basename "$f")" != mmproj* ]]; then
            model_file="$f"
            break
        fi
    done

    # Extract model identifier for mmproj matching
    # For "Qwen3VL-8B-Thinking" we need "Qwen3VL-8B" to match correctly
    # For "Qwen3VL-30B-A3B" we need "Qwen3VL-30B"
    # For "Mistral-Small-3.2" we need "Mistral-Small-3.2"
    local model_base=""
    if [[ "$name" == Qwen3VL-* ]]; then
        # Extract Qwen3VL-{size} (e.g., Qwen3VL-8B, Qwen3VL-30B, Qwen3VL-32B)
        model_base=$(echo "$name" | grep -oE 'Qwen3VL-[0-9]+B')
    elif [[ "$name" == *Mistral* ]]; then
        # For Mistral, use the full identifier
        model_base="mistralai_Mistral-Small-3.2"
    else
        # Fallback: use first 3 parts
        model_base=$(echo "$name" | cut -d'-' -f1-3)
    fi

    # Search for matching mmproj with the extracted base
    for f in "$MODEL_DIR"/mmproj*.gguf; do
        if [[ -n "$model_base" ]] && [[ "$(basename "$f")" == *"$model_base"* ]]; then
            mmproj_file="$f"
            break
        fi
    done

    echo "$model_file|$mmproj_file"
}

# Safety check - make sure Gary isn't running (BOTH use same GPUs with tensor-split)
check_gary() {
    if systemctl is-active --quiet llama-server.service 2>/dev/null || \
       pgrep -f "llama-server.*8034" > /dev/null 2>&1; then
        echo "⚠️  CONFLICT: Gary's llama-server is running!"
        echo ""
        echo "   Both Gary and StardewAI use tensor-split across 3090 Ti + 4070."
        echo "   Running both simultaneously will cause GPU OOM and lockups."
        echo ""
        echo "   To stop Gary:  sudo systemctl stop llama-server gary"
        echo "   To check:      pgrep -fa llama-server"
        echo ""
        exit 1
    fi
}

# Check if port is in use
check_port() {
    if lsof -i :$PORT > /dev/null 2>&1; then
        echo "⚠️  Port $PORT is already in use!"
        echo "   Check with: lsof -i :$PORT"
        exit 1
    fi
}

show_models() {
    echo "Available models in $MODEL_DIR:"
    echo "─────────────────────────────────────────"
    for f in "$MODEL_DIR"/*.gguf; do
        if [[ "$(basename "$f")" != mmproj* ]]; then
            size=$(du -h "$f" 2>/dev/null | cut -f1)
            echo "  $(basename "$f") ($size)"
        fi
    done
    echo ""
}

main() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "  StardewAI LLaMA Server (ISOLATED from Gary)"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    # Safety checks
    check_gary
    check_port

    # Show available models
    show_models

    # Find model files
    result=$(find_model "$MODEL_NAME")
    MODEL_FILE="${result%%|*}"
    MMPROJ_FILE="${result##*|}"

    if [[ -z "$MODEL_FILE" ]] || [[ ! -f "$MODEL_FILE" ]]; then
        echo "❌ Model not found: $MODEL_NAME"
        echo "   Make sure models are downloaded to: $MODEL_DIR"
        exit 1
    fi

    echo "Selected model: $(basename "$MODEL_FILE")"
    echo "Vision encoder: $(basename "$MMPROJ_FILE" 2>/dev/null || echo 'Not found')"
    echo "Port: $PORT"
    echo ""

    # Build command - Use llama-mtmd-cli for multimodal OR llama-server
    # llama-server supports multimodal with --mmproj flag
    CMD="$LLAMA_SERVER"
    CMD="$CMD -m $MODEL_FILE"

    # Add vision encoder if found
    if [[ -n "$MMPROJ_FILE" ]] && [[ -f "$MMPROJ_FILE" ]]; then
        CMD="$CMD --mmproj $MMPROJ_FILE"
    fi

    # Server settings - MEMORY OPTIMIZED to prevent GPU lockups
    # Learned from Gary: <2GB headroom = OOM crashes and XID 158 lockups
    CMD="$CMD --port $PORT"
    CMD="$CMD --host 127.0.0.1"
    CMD="$CMD -c 4096"           # 4K context (plenty for game state, saves ~1GB)
    CMD="$CMD -ngl 99"           # All layers on GPU
    CMD="$CMD --tensor-split 20,4"  # 83% on 3090 Ti, 17% on 4070 (like Gary)
    CMD="$CMD --flash-attn on"   # Enable flash attention
    CMD="$CMD -np 1"             # Single slot (sequential requests)
    CMD="$CMD --fit off"         # Don't auto-adjust, use explicit settings
    CMD="$CMD -sps 0"            # Disable slot prompt similarity (fixes vision+tensor-split crash)

    # MoE optimization - offload experts to CPU if needed for 30B+ models
    # Uncomment if still OOM: CMD="$CMD -ot '.ffn_.*_exps.=CPU'"

    echo "Starting server..."
    echo "Command: $CMD"
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  Server starting on http://127.0.0.1:$PORT"
    echo "  Test with: curl http://127.0.0.1:$PORT/health"
    echo "  Stop with: Ctrl+C"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    # Create log directory
    mkdir -p "$LOG_DIR"

    # Run server
    exec $CMD 2>&1 | tee "$LOG_DIR/llama-server.log"
}

# Handle arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [MODEL_NAME]"
        echo ""
        echo "Examples:"
        echo "  $0                           # Use default (Qwen3VL-30B-A3B)"
        echo "  $0 Qwen3VL-8B-Thinking       # Use 8B Thinking model"
        echo "  $0 Qwen3VL-32B               # Use 32B model"
        echo "  $0 Mistral-Small-3.2         # Use Mistral 3.2"
        echo ""
        show_models
        exit 0
        ;;
    --list|-l)
        show_models
        exit 0
        ;;
    *)
        main
        ;;
esac
