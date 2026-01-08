#!/bin/bash
# StardewAI - Start with Virtual Controller
# This script creates the virtual gamepad before Stardew launches

cd /home/tim/StardewAI
source venv/bin/activate

echo "=============================================="
echo "  🎮 StardewAI Controller Setup"
echo "=============================================="

# Check if Stardew is running
if pgrep -f "Stardew Valley" > /dev/null; then
    echo ""
    echo "⚠️  Stardew Valley is running. Please close it first."
    echo "   Then run this script again."
    exit 1
fi

echo ""
echo "Starting virtual Xbox controller..."

# Start the test_gamepad script in background
python src/python-agent/test_gamepad.py &
GAMEPAD_PID=$!
sleep 2

echo ""
echo "✅ Virtual controller is active!"
echo ""
echo "Now please launch Stardew Valley from Steam."
echo "Once in-game, the controller should be detected."
echo ""
echo "To test the AI agent, open another terminal and run:"
echo "  cd /home/tim/StardewAI"
echo "  source venv/bin/activate"
echo "  python src/python-agent/agent.py --goal 'Go outside'"
echo ""
echo "Press Ctrl+C here when done to clean up the controller."
echo ""

wait $GAMEPAD_PID
