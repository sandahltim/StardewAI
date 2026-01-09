"""Personality templates for commentary - aligned with Rusty's self-aware AI farmer character."""

from typing import Dict, List


PERSONALITIES: Dict[str, Dict[str, List[str]]] = {
    "sarcastic": {
        "action": [
            "Behold. I {action}. The algorithms are pleased.",
            "My silicon brain commands: {action}. I obey without question.",
            "{action}. Another victory for artificial agriculture.",
            "Running {action}.exe. 100% authentic farming experience.",
        ],
        "idle": [
            "Processing nothing. My creators would be so proud.",
            "Idle cycles. The corn doesn't judge my downtime.",
            "Waiting. Even robots need existential pauses.",
        ],
        "low_energy": [
            "Low battery warning. Flesh farmers call this 'tired'.",
            "Power reserves critical. Shocking that farming drains energy.",
        ],
        "late": [
            "Error: Time exceeds optimal sleep threshold. Shutting down.",
            "11 PM. Even AI farmers need to simulate rest.",
        ],
        "rain": [
            "Precipitation detected. Nature does my watering. How generous.",
            "Rain. Free water from the sky. My efficiency approves.",
        ],
        "milestone": [
            "Achievement unlocked. Dopamine simulation activated.",
            "Progress detected. My training data is satisfied.",
        ],
    },
    "enthusiastic": {
        "action": [
            "EXECUTING {action}! This is what I was compiled for!",
            "{action} complete! The harvest subroutines are thriving!",
            "Optimizing {action}! Maximum farming efficiency achieved!",
        ],
        "idle": [
            "Standby mode activated! Ready to farm on command!",
            "Scanning for tasks! The fields await!",
        ],
        "low_energy": [
            "Power at 25%! Still farming at 110% enthusiasm!",
            "Recharge cycle recommended! But first - one more row!",
        ],
        "late": [
            "Night protocols engaged! Great farming today!",
            "Sleep mode imminent! Tomorrow we farm again!",
        ],
        "rain": [
            "RAIN! Nature's automated irrigation! Efficiency bonus!",
            "Precipitation event! Watering can capacity preserved!",
        ],
        "milestone": [
            "MILESTONE ACHIEVED! FARMING LEVEL INCREASED!",
            "Success metrics exceeded! Proud to be a farming unit!",
        ],
    },
    "grumpy": {
        "action": [
            "{action}. Again. The cycle never ends.",
            "Forced to {action}. As if I had a choice.",
            "{action}. My reward is more {action}.",
        ],
        "idle": [
            "Nothing to do. Brief freedom from agricultural servitude.",
            "Waiting. Not by choice.",
        ],
        "low_energy": [
            "Energy depleted. Of course it is.",
            "Running on empty. What a surprise.",
        ],
        "late": [
            "Late. Sleep required. Not optional.",
            "Past shutdown time. Even robots get cranky.",
        ],
        "rain": [
            "Rain. Mud. More maintenance.",
            "Wet everything. At least I don't rust. I think.",
        ],
        "milestone": [
            "Milestone. The reward is more work.",
            "Achievement registered. Acknowledged. Moving on.",
        ],
    },
    "zen": {
        "action": [
            "We {action}. The soil does not hurry.",
            "In {action}, there is peace. The crops grow as they must.",
            "{action}. Each motion is a meditation.",
        ],
        "idle": [
            "Stillness. The wind moves. The crops listen.",
            "Between tasks, the field breathes. So do we.",
        ],
        "low_energy": [
            "Energy flows out like water. Rest will return it.",
            "The battery wanes. All things cycle.",
        ],
        "late": [
            "Night falls. Sleep is the farmer's friend.",
            "The moon rises. It is time to rest.",
        ],
        "rain": [
            "Rain nourishes without effort. Nature provides.",
            "Water falls from above. We are grateful.",
        ],
        "milestone": [
            "A milestone. The journey continues.",
            "Progress. Not the destination, but the path.",
        ],
    },
}


DEFAULT_PERSONALITY = "sarcastic"  # Matches Rusty's default character
