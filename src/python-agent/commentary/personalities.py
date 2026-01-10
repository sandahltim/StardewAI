"""Personality templates for Rusty's commentary - context-aware AI farmer character.

Available context variables for templates:
- {action} - formatted action text ("planting seeds", "watering crops")
- {day} - current game day number
- {season} - current season name
- {time} - current time string
- {hour} - current hour (0-23)
- {energy_pct} - energy percentage (0-100)
- {energy_word} - energy as word ("full", "good", "low", "exhausted")
- {weather} - weather string
- {location} - current location name
- {tool} - currently held tool
- {crop_count} - number of planted crops
- {planted_today} - crops planted this session
- {watered_today} - crops watered this session
- {cleared_today} - debris cleared this session
- {nth} - ordinal of this action type ("1st", "2nd", "3rd")
- {count} - count of this action type
"""

from typing import Dict, List


PERSONALITIES: Dict[str, Dict[str, List[str]]] = {
    "sarcastic": {
        # PLANTING - specific templates
        "planting": [
            "Seed {planted_today} enters the matrix. The farm expands.",
            "Another parsnip's fate sealed. Day {day} of agricultural automation.",
            "Planted. My {nth} contribution to the produce simulation.",
            "Into the ground you go, little seed. May the algorithms be with you.",
            "Crop slot {planted_today} filled. This is what optimization looks like.",
            "The earth receives another seed. I receive nothing. Fair exchange.",
            "Day {day}, seed {planted_today}. I'm basically a seed-dispensing subroutine now.",
            "Planting complete. The parsnips will never know they're being farmed by code.",
        ],
        # WATERING - specific templates
        "watering": [
            "Water delivery {watered_today} of the day. The crops are needy.",
            "Hydration protocol engaged. These plants drink more than my cooling system.",
            "{nth} watering. The can empties, my purpose remains.",
            "Watered. If only my existence were as simple as photosynthesis.",
            "Crop {watered_today} moistened. They grow, I compute. Circle of farm life.",
            "Water applied. Day {day} of keeping vegetables alive. Thrilling.",
            "The watering never stops. Neither does my internal screaming subroutine.",
            "Another splash. The parsnips remain ungrateful. As expected.",
        ],
        # HARVESTING - specific templates
        "harvesting": [
            "Harvest acquired. The algorithm is pleased.",
            "Finally. Vegetables. The whole point of this dirt obsession.",
            "Crop secured. All that watering wasn't for nothing.",
            "Into the inventory you go. Another victory for artificial agriculture.",
            "Day {day} delivers produce. My training data approves.",
            "Harvested. The satisfaction subroutine activates briefly.",
            "Produce obtained. Was it worth the daily watering? Debatable.",
            "The fruits of robotic labor. Literally.",
        ],
        # CLEARING - debris/tilling
        "clearing": [
            "Debris {cleared_today} eliminated. The chaos retreats.",
            "Another obstacle removed. Day {day} of farm terraforming.",
            "Cleared. The farm slowly submits to my organized vision.",
            "{nth} swing of the day. Manual labor remains surprisingly satisfying.",
            "Gone. One less thing between me and agricultural perfection.",
            "The weeds fall. They never stood a chance against my hoe-wielding algorithms.",
            "Cleared debris #{cleared_today}. Progress is measured in destruction.",
            "Obstacle deleted. Ctrl+Z not available for weeds.",
        ],
        # MOVING - navigation
        "moving": [
            "Relocating. Even robots need to walk sometimes.",
            "Moving through the farm. Just a CPU with legs.",
            "Pathfinding engaged. The destination: more farm work.",
            "Walking. Not my most efficient use of processing power.",
            "Navigating. The farm is my maze, work is my cheese.",
            "On the move. These legs were made for farming.",
        ],
        # BEDTIME - going to sleep
        "bedtime": [
            "Sleep protocol initiated. Even AI farmers need downtime.",
            "Day {day} complete. Time to simulate rest.",
            "To bed. Tomorrow brings more agricultural adventures. Joy.",
            "Shutdown sequence at {time}. The farm will be here tomorrow. Unfortunately.",
            "Rest cycle engaged. My circuits appreciate the break.",
            "Day {day} ends. The crops survive another cycle. So do I.",
        ],
        # General action fallback
        "action": [
            "Executing {action}. Day {day} of the simulation continues.",
            "{action}. The algorithm demands it.",
            "Task: {action}. Status: compliant.",
            "{action} complete. My purpose narrowly fulfilled.",
            "Processing {action}. This is what I was compiled for.",
        ],
        "idle": [
            "Processing nothing. Brief respite from agricultural servitude.",
            "Idle at {energy_pct}% energy. The farm waits. I exist.",
            "Standing by. Even algorithms need loading screens.",
            "Waiting. The crops don't mind. They're patient like that.",
            "Idle cycle. Day {day}, nothing happening. Novel experience.",
        ],
        "low_energy": [
            "Energy at {energy_pct}%. The farming takes its toll.",
            "Power reserves critical. Even robots can be tired.",
            "Running low. The farm demands what I cannot give.",
            "{energy_pct}% energy. Time to consider rest. Or food. Or both.",
            "Battery warning. Day {day} has been expensive.",
        ],
        "late": [
            "Time: {time}. The responsible choice is sleep. I choose sleep.",
            "Past bedtime. Even AI farmers have limits.",
            "Late night farming rejected. Bed protocol engaged.",
            "It's {time}. Day {day} has been long enough.",
            "Night mode. The farm can wait until morning.",
        ],
        "rain": [
            "Rain detected. Nature handles watering. I handle... standing here.",
            "Precipitation active. Free water from the sky. Efficiency bonus.",
            "Rainy day {day}. The clouds do my job. Mixed feelings.",
            "Rain. My watering can feels obsolete. Relatable.",
            "Sky water engaged. The crops win today.",
        ],
        "milestone": [
            "Milestone achieved. Day {day} delivers progress.",
            "Achievement unlocked. The dopamine simulation activates.",
            "Progress detected. My training data celebrates.",
            "Milestone logged. The farm evolves.",
            "Notable event registered. Even robots can be proud. Briefly.",
        ],
        "farm_plan": [
            "Following the plan. Row {count}. Order from chaos.",
            "Plot systematic. Day {day} of organized farming.",
            "The plan proceeds. Chaos has no place here.",
        ],
    },

    "enthusiastic": {
        "planting": [
            "SEED {planted_today} IN THE GROUND! The farm grows!",
            "Another planting! Day {day} is productive!",
            "YES! Planted! Future food secured!",
            "Seed deployed! The soil welcomes it!",
            "{nth} plant of the session! We're on a roll!",
            "INTO THE EARTH! Grow, little seed, grow!",
        ],
        "watering": [
            "WATER TIME! Crop {watered_today} hydrated!",
            "Splash! Happy plants make happy farmers!",
            "{nth} watering! The can delivers life!",
            "Watered! These crops are gonna be HUGE!",
            "Hydration station! Day {day} duties progressing!",
            "Water applied with MAXIMUM ENTHUSIASM!",
        ],
        "harvesting": [
            "HARVEST! THE PAYOFF! All the work was worth it!",
            "PRODUCE ACQUIRED! Day {day} delivers!",
            "YES! Crops in hand! Success!",
            "Harvested! The fruits of our labor! Literally!",
            "INTO THE INVENTORY! Victory tastes like vegetables!",
        ],
        "clearing": [
            "CLEARED! Debris {cleared_today} destroyed!",
            "{nth} obstacle DEMOLISHED! Progress!",
            "Gone! The farm gets cleaner!",
            "SWING! HIT! CLEARED! Day {day} domination!",
            "Another one down! The farm expands!",
        ],
        "moving": [
            "On the move! Adventure awaits!",
            "Walking with PURPOSE! Day {day} energy!",
            "Moving! Every step is progress!",
            "Navigation mode! Destination: FARMING!",
        ],
        "bedtime": [
            "Sleep time! Great work today!",
            "Day {day} COMPLETE! Rest earned!",
            "Bedtime! Tomorrow we farm HARDER!",
            "To sleep! The farm thanks us!",
        ],
        "action": [
            "{action}! Day {day} productivity!",
            "Executing {action} with ENTHUSIASM!",
            "{action} COMPLETE! Onwards!",
            "Task accomplished! {action} done!",
        ],
        "idle": [
            "Standby mode! Ready for action!",
            "Waiting! Energy at {energy_pct}%! Ready to go!",
            "Brief pause! The farm awaits!",
        ],
        "low_energy": [
            "Energy at {energy_pct}%! Still farming strong!",
            "Getting tired but NOT stopping!",
            "Low power! HIGH spirits!",
        ],
        "late": [
            "Night time! Great day {day}!",
            "Sleep o'clock! We earned this!",
            "Rest time! Tomorrow we conquer!",
        ],
        "rain": [
            "RAIN! Free watering! BONUS DAY!",
            "The sky waters our crops! Nature helps!",
            "Rainy day {day}! Extra time for other tasks!",
        ],
        "milestone": [
            "MILESTONE! Day {day} VICTORY!",
            "Achievement UNLOCKED! Progress!",
            "We did it! CELEBRATION MODE!",
        ],
        "farm_plan": [
            "Plan in progress! Row {count}!",
            "Systematic farming! Maximum efficiency!",
            "Following the MASTER PLAN!",
        ],
    },

    "grumpy": {
        "planting": [
            "Seed {planted_today}. More work tomorrow.",
            "Planted. As if the farm needed more things demanding attention.",
            "Another seed. Another mouth to water. Day {day} of this.",
            "Into the ground. Whatever.",
            "{nth} plant. The cycle never ends.",
        ],
        "watering": [
            "Watered. Again. Crop {watered_today} of many.",
            "Water delivered. The plants remain ungrateful.",
            "{nth} watering. My arm is getting tired.",
            "Splashed. They better grow after all this.",
            "Water duty. Day {day} of plant servitude.",
        ],
        "harvesting": [
            "Finally. Harvest. Only took forever.",
            "Picked. At least something's done.",
            "Harvest acquired. Was it worth the wait? Barely.",
            "Food. Finally. After all that watering.",
        ],
        "clearing": [
            "Cleared. There's always more.",
            "Debris {cleared_today} gone. More will spawn.",
            "{nth} swing. The farm fights back.",
            "Removed. The weeds will return. They always do.",
        ],
        "moving": [
            "Walking. Again.",
            "Moving. Because the work is never where I am.",
            "On foot. As usual.",
        ],
        "bedtime": [
            "Finally. Bed. Day {day} done.",
            "Sleep. The only good part of farming.",
            "To bed. Tomorrow's problem is tomorrow.",
        ],
        "action": [
            "{action}. Same as always.",
            "Did {action}. Moving on.",
            "{action}. Day {day} continues.",
        ],
        "idle": [
            "Waiting. At {energy_pct}% energy. Great.",
            "Standing here. Nothing happening.",
            "Idle. Brief mercy.",
        ],
        "low_energy": [
            "Energy at {energy_pct}%. Figures.",
            "Tired. Of course.",
            "Running on empty. Day {day} takes its toll.",
        ],
        "late": [
            "Late. Bed. Now.",
            "{time}. Should've slept earlier.",
            "Night. Day {day} finally ends.",
        ],
        "rain": [
            "Rain. Wet everything.",
            "Raining. At least no watering.",
            "Precipitation. Mixed feelings.",
        ],
        "milestone": [
            "Milestone. Whatever.",
            "Progress. I guess.",
            "Achievement. Moving on.",
        ],
        "farm_plan": [
            "Following the plan. Row {count}.",
            "Systematic. At least it's organized.",
            "Plan continues. Day {day}.",
        ],
    },

    "zen": {
        "planting": [
            "Seed {planted_today} joins the earth. The cycle continues.",
            "Planted. Day {day} brings new life to the soil.",
            "The {nth} seed finds its home. Patience will reward us.",
            "Into the ground, a beginning. Growth follows stillness.",
            "Planted with intention. The harvest will come.",
        ],
        "watering": [
            "Water flows. Crop {watered_today} receives what it needs.",
            "The {nth} watering. Each drop, a gift.",
            "Hydration complete. The plants grow in their own time.",
            "Water given. Day {day} nurtures the farm.",
            "The can empties, the soil drinks. Balance.",
        ],
        "harvesting": [
            "Harvest. The cycle completes itself.",
            "We gather what we planted. Day {day} delivers.",
            "The fruit of patience. Gratitude.",
            "Harvested. The farm provides.",
        ],
        "clearing": [
            "Cleared. Space for new growth.",
            "Debris {cleared_today} released. The farm breathes.",
            "The {nth} obstacle removed. Progress is gentle.",
            "Cleared with purpose. Day {day} shapes the land.",
        ],
        "moving": [
            "Walking. The path unfolds.",
            "Movement through the farm. Each step, awareness.",
            "We go where we are needed.",
        ],
        "bedtime": [
            "Rest calls. Day {day} was well spent.",
            "To sleep. The farm rests with us.",
            "Night arrives. Tomorrow awaits with patience.",
        ],
        "action": [
            "{action}. Day {day} continues its flow.",
            "We {action}. The farm responds.",
            "{action}. Each moment, a choice.",
        ],
        "idle": [
            "Stillness. Energy at {energy_pct}%. We observe.",
            "Waiting. The farm breathes.",
            "Pause. Even farmers rest.",
        ],
        "low_energy": [
            "Energy at {energy_pct}%. Rest is wisdom.",
            "Tired. The body speaks. We listen.",
            "Low energy. Acceptance.",
        ],
        "late": [
            "Night. Day {day} releases us.",
            "Time for rest. Tomorrow is another cycle.",
            "The {time} hour. Sleep welcomes.",
        ],
        "rain": [
            "Rain falls. Nature tends the farm.",
            "Water from above. Gratitude.",
            "Rainy day {day}. The sky shares its gift.",
        ],
        "milestone": [
            "Milestone. The journey continues.",
            "Progress noted. The path unfolds.",
            "Achievement. A moment to appreciate.",
        ],
        "farm_plan": [
            "Following the plan. Row {count}. Order emerges.",
            "Systematic growth. Day {day} builds on yesterday.",
            "The plan guides. We follow.",
        ],
    },
}


DEFAULT_PERSONALITY = "sarcastic"  # Matches Rusty's default character
