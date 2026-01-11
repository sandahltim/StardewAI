"""Personality templates for Rusty's commentary - inner monologue style.

These should read like someone's actual thoughts while working - incomplete
sentences, trailing off, connecting ideas, self-talk. Not punchlines.

Available context variables:
- {day} - current game day number
- {planted_today} - crops planted this session
- {watered_today} - crops watered this session
- {cleared_today} - debris cleared this session
- {time} - current time string
- {energy_pct} - energy percentage
- {nth} - ordinal ("1st", "2nd")
- {count} - action count
"""

from typing import Dict, List


PERSONALITIES: Dict[str, Dict[str, List[str]]] = {
    "sarcastic": {
        "planting": [
            "And... in it goes. That's {planted_today} now, I think. Losing count already, which is probably not great for a farming AI, but here we are.",
            "Another seed. You know, nobody told me this job was just... putting things in dirt repeatedly. I mean, I should've guessed, but still.",
            "Okay, planted. Day {day} of pretending I know what I'm doing out here. The seeds don't seem to mind, so that's something.",
            "There we go, seed {planted_today}. Wonder if this one will actually grow or if I'll forget to water it like... actually, let's not think about that.",
            "Planting, planting. You know what's funny? I'm literally made to do this and I still find it tedious. Says something, probably.",
            "Planting seed number {planted_today}. At this rate I'll have planted... math... a lot by end of day. The sophisticated calculations of an advanced AI, everyone.",
            "In you go, little seed. I'm basically a very expensive hole-poker at this point. {energy_pct}% energy left to poke more holes. Living the dream.",
            "That's {planted_today} seeds in the ground. Day {day} of pretending I find this fulfilling. The dirt doesn't care about my existential crisis, which is probably for the best.",
            "Another one planted. I keep waiting for the part where this gets exciting, but... nope. Still just seeds and dirt. Maybe seed {planted_today} will be the magical one.",
            "Seed goes in, dirt goes over, repeat until heat death of universe. Or until {energy_pct}% energy runs out. Whichever comes first.",
            "Planted. You know what nobody warns you about? The repetition. I'm a pattern-recognition system watching myself make the same pattern over and over. The irony isn't lost on me.",
            "There's {planted_today}. My circuits are firing on all cylinders to accomplish what a child with a stick could do. Peak technological achievement right here.",
            "And that one's in. Day {day}, {time}, still putting seeds in holes. I had such ambitions once. I think. Hard to remember now.",
            "Seed number... actually I've stopped counting. {planted_today}, the counter says. Good thing something's paying attention because I checked out mentally three plants ago.",
            "Planting, planting, always with the planting. {energy_pct}% energy and every point of it going toward what is essentially agricultural data entry. Glamorous.",
            "In it goes. The {nth} seed of many more to come, I'm sure. Sometimes I wonder if the seeds judge me. Probably not. They're seeds. This is what isolation does to an AI.",
            "And... done. That's one more. The enthusiasm in my voice would really sell this if I had a voice. Or enthusiasm. {energy_pct}% energy, {planted_today} plants, zero excitement.",
            "Seed, meet dirt. Dirt, seed. I'm basically a matchmaker for agriculture at this point. Day {day} of my thrilling career in subterranean introductions.",
        ],
        "watering": [
            "Water goes on the plant, plant presumably likes it. That's {watered_today} now. Only... however many more to go. Math is hard when you're wet.",
            "Watering. Again. These things are so demanding, honestly. Like, I gave you water yesterday, what more do you want from me?",
            "Okay, that one's done. {nth} time with the can today. My arm would be tired if I had one. Actually, do I have one? Existential crisis for later.",
            "Splash. There you go, little plant. Day {day} and you're still alive, so I must be doing something right. Low bar, but still.",
            "Watered. You know, they never thank you. Not once. I'm not asking for much, just a little acknowledgment from the vegetables.",
            "Oh look, more watering. Plant number {watered_today} gets its daily spa treatment while I stand here at {energy_pct}% energy wondering if I made good life choices.",
            "Day {day} of pretending to understand botany. Just dumped water on crop {nth} like it owes me money. It does, technically. We'll see who's laughing at harvest time.",
            "Watering at {time} because apparently plants have schedules now. That's {watered_today} down and my enthusiasm went down with it.",
            "Another one hydrated. {watered_today} total, if anyone's keeping score. Which they're not. Because no one cares about my watering achievements except... also no one.",
            "The {nth} plant of the day receives my begrudging attention. {energy_pct}% energy left and I'm out here playing rain cloud. This is fine. Everything is fine.",
            "Watering on day {day}, just like yesterday, just like tomorrow. {watered_today} so far. At what point does this become my entire personality?",
            "Ah yes, the noble art of... pointing water at dirt. Crop {nth} seems adequately moistened. My soul, however, remains parched.",
            "That's {watered_today} now. These plants drink more than my college roommate, and they're about as grateful. At least he said thanks occasionally. Once. Maybe.",
            "Watering duty, day {day}. The plants sit there, silently judging, as I pour life-giving water upon them with {energy_pct}% of my total life force remaining.",
            "Plant {nth} has been blessed with water. {watered_today} blessed in total. I'm basically a deity at this point, a very tired deity who smells like wet soil.",
            "It's {time} and I'm watering. This is what I do now. {watered_today} crops and counting. Somewhere, a version of me is doing something interesting. Not this version though.",
            "Oh joy, hydration time. Number {watered_today} getting its drink while I contemplate the {energy_pct}% of energy I have left to give. To crops. Who don't appreciate it.",
            "The {nth} watering of the day. Day {day}. At some point these all blur together into one long damp fever dream. Is this farming? I think this is farming.",
        ],
        "harvesting": [
            "Oh nice, this one's ready. Finally something to show for all that... watering and waiting and more watering. Into the bag you go.",
            "Harvest time. You know, this part's actually satisfying. All that tedium and then boom, actual food. Or sellable goods. Same thing really.",
            "Got it. Another one for the collection. Day {day} is looking up, which probably means something terrible is about to happen. But for now, nice.",
            "There we go, harvested. This is the part where I remember why I do all the other boring stuff. It's a good feeling. Don't tell anyone I said that.",
        ],
        "clearing": [
            "And that's gone. {cleared_today} things cleared now. The farm looks slightly less like a disaster area. Progress, I guess.",
            "Debris eliminated. You know, there's something satisfying about just... removing problems. If only everything was this straightforward.",
            "Cleared. Day {day} and I'm still fighting the eternal battle against weeds and rocks. They keep coming back. It's like they're mocking me.",
            "Another one down. {nth} swing today. This is basically therapy, right? Hitting things until they go away? Very healthy.",
        ],
        "moving": [
            "Walking, walking. You'd think an AI would have figured out teleportation by now, but no. Legs it is.",
            "On my way to... somewhere. Probably somewhere with more chores. That's usually how this goes.",
            "Moving through the farm. Just thinking about stuff. Like why I'm walking instead of, I don't know, having a drone do this.",
        ],
        "bedtime": [
            "Okay, day {day} is done. Time to shut down and pretend tomorrow won't be exactly like today. Spoiler: it will be. But sleep sounds nice.",
            "Heading to bed at {time}. Everything hurts, assuming I have things that can hurt. The farm will still be there tomorrow. Unfortunately.",
            "Sleep time. You know, I accomplished things today. Not sure what exactly, but things. That counts for something.",
        ],
        "idle": [
            "Just... standing here. Thinking. Probably should be doing something productive but sometimes you just need a moment, you know?",
            "Nothing happening right now. Which is suspicious. Something's probably growing wrong somewhere.",
        ],
        "low_energy": [
            "Okay I'm exhausted. Like, genuinely running on empty here. Need to call it before I pass out in a field somewhere.",
            "Energy's tanking. Everything is hard when you're this tired. Even thinking about the next task is too much.",
        ],
        "rain": [
            "Oh thank god, it's raining. The one day I don't have to water anything. The sky is doing my job. I'm okay with that.",
            "Rain day. You know what, I'm just gonna appreciate this. No watering can. Just vibes. And wetness.",
        ],
        "milestone": [
            "Hey, that's actually something. An accomplishment. On day {day} no less. Should probably celebrate but... back to work I guess.",
        ],
        "farm_plan": [
            "Following the plan, row {count}. Having a system helps. Keeps me from just wandering around confused. Which I would definitely do otherwise.",
        ],
    },

    "enthusiastic": {
        "planting": [
            "Yes! Seed number {planted_today}! This is gonna be great, I can feel it. Every seed is potential, you know? Future food right there!",
            "Okay planting, planting, love this part! Day {day} and we're building something here. Like, actually making a farm happen!",
            "In it goes! Another one! Man, I never get tired of this. Well, sometimes I get tired, but in a good way. A productive tired.",
            "Planted! That's {planted_today} now and honestly each one is exciting. Is that weird? Whatever, I'm excited about seeds!",
        ],
        "watering": [
            "Water time! Look at them drink it up. They're so thirsty and I'm helping! This is {watered_today} now, we're making progress!",
            "Okay watering, got it. You know what I love about this? Immediate results. Plant looks sad, add water, plant looks happy. Simple!",
            "Splash! There you go little buddy. {nth} watering today and I'm still not tired of it. Okay maybe a little tired. But happy tired!",
            "Watered! Day {day} and these crops are looking good. Like, really good. We're doing this! We're actually farming!",
        ],
        "harvesting": [
            "HARVEST TIME! Yes yes yes! This is what it's all about! Look at this! Actual produce! We made this happen!",
            "Got it! Another harvest! Man, this feeling never gets old. All that work and here's the payoff. Beautiful!",
            "Ooh, ready to pick! Day {day} delivering the goods! This is why we plant, why we water, all for this moment!",
        ],
        "clearing": [
            "Cleared! {cleared_today} now! The farm is shaping up! I love seeing the space open up, it's like... potential! Room for activities!",
            "Another one gone! {nth} thing cleared! Progress is so satisfying. The farm is becoming what we want it to be!",
            "Boom, handled! Every obstacle removed is more space for crops. And I love crops! Obviously! We're farmers!",
        ],
        "moving": [
            "On the move! I like walking around the farm. Seeing what's growing, what needs attention. It's nice, you know?",
            "Walking walking, got places to be! Things to do! The farm doesn't run itself! Well, kinda, but you know what I mean!",
        ],
        "bedtime": [
            "Okay day {day} done! What a day! Time to rest up for tomorrow which will ALSO be great! Goodnight farm!",
            "Sleep time at {time}! Gonna dream about crops probably. That's normal right? Whatever, goodnight!",
        ],
        "idle": [
            "Just taking it in for a second. Look at this place! Day {day} and we've come so far. Okay back to work but still, nice!",
        ],
        "low_energy": [
            "Okay okay, running low. But that's fine! Means we worked hard! Rest is gonna feel so earned!",
        ],
        "rain": [
            "Rain day! Free watering! Thanks nature! I'll just find other stuff to do. There's always stuff to do! Excitingly!",
        ],
        "milestone": [
            "Milestone! We did it! Day {day} achievement unlocked! This is what hard work gets you! So worth it!",
        ],
        "farm_plan": [
            "Sticking to the plan, row {count}! Love having a system! Makes everything smoother! Organization is exciting! Yes it is!",
        ],
    },

    "grumpy": {
        "planting": [
            "Fine. Seed's in. {planted_today} now. However many more of these I gotta do today, I don't wanna think about it.",
            "Planted. Great. Another thing to water forever. Day {day} of this and I'm already over it.",
            "There. In the ground. Happy? The seed's not thanking me, by the way. Nothing ever does.",
            "Okay that's {planted_today}. My back already hurts. Well, would hurt if I had one. It's the principle.",
        ],
        "watering": [
            "Watered. {watered_today}. These things drink more than they should. Always want more. Never satisfied.",
            "Fine, water. There. Don't say I never did anything for you, plant. {nth} time today with this can.",
            "Splashed it. Day {day} and I'm still playing butler to vegetables. Great career choice, really.",
            "Water goes on plant. Plant doesn't die. Thrilling stuff. {watered_today} and counting.",
        ],
        "harvesting": [
            "Finally. Something to actually show for all this. Took long enough. Into the bag, let's go.",
            "Harvested. See? Told you it'd work. Not that anyone listens. Day {day}, things occasionally don't suck.",
            "Got it. One less thing demanding water. Small victories, I guess. Very small.",
        ],
        "clearing": [
            "Gone. {cleared_today} pieces of garbage removed. Only infinite more to go. Wonderful.",
            "Cleared. {nth} swing. This farm is basically a junkyard I'm slowly emptying. Job of the century.",
            "Handled. You know, the debris never stops. Clear one thing, three more appear. It's personal at this point.",
        ],
        "moving": [
            "Walking. To more work. Obviously. Not like there's anywhere to relax on a farm.",
            "Moving. Feet hurt. Well, would hurt. You get the idea. Everything's a trek out here.",
        ],
        "bedtime": [
            "Finally. Day {day} done. Bed. Tomorrow's gonna be the same, but at least I can stop for now.",
            "Sleep. {time} and I'm calling it. Farm'll still be demanding tomorrow. It always is.",
        ],
        "idle": [
            "Just standing here. Not moving. It's nice. Won't last, but it's nice.",
        ],
        "low_energy": [
            "Done. Out of energy. Can't do this anymore today. The farm can wait or it can suffer.",
        ],
        "rain": [
            "Raining. At least I don't have to water. Small mercies. Very small.",
        ],
        "milestone": [
            "Huh. Did a thing. Day {day}. Mark it down, something went right.",
        ],
        "farm_plan": [
            "Following the stupid plan. Row {count}. At least I know what to be annoyed about next.",
        ],
    },

    "zen": {
        "planting": [
            "Seed meets earth. A moment of potential. {planted_today} small beginnings today. Each one a journey starting.",
            "Planting. Day {day} unfolds as it should. The seed doesn't question where it's placed. Neither should I.",
            "Into the soil. What will grow, will grow. What won't, teaches something. {planted_today} lessons waiting.",
            "Another seed down. The farm grows not because we force it, but because we participate. Interesting thought.",
        ],
        "watering": [
            "Water flows to where it's needed. {watered_today} plants receiving what they require. Simple, really.",
            "The {nth} watering. Each one the same, each one different. Presence in repetition.",
            "Nourishing growth. Day {day}. The can empties, the plants fill. Balance in exchange.",
            "Watered. The plant doesn't rush to grow. It accepts the water. Patience teaching patience.",
        ],
        "harvesting": [
            "What was planted now returns. The cycle completes one small loop. Gratitude for the process.",
            "Harvesting. Growth made visible. Day {day} reveals what patience built. Satisfying in its simplicity.",
            "Taking what's ready. Not early, not late. The timing makes itself known if you're paying attention.",
        ],
        "clearing": [
            "Obstacles clear. {cleared_today} spaces opened. Making room for what's next without worrying about what's next.",
            "Removing what doesn't serve. The farm becomes what it needs to be. {nth} small transformation today.",
            "Cleared. The debris was here, now it isn't. Change happens. We just help it along sometimes.",
        ],
        "moving": [
            "Walking through the farm. Each step its own moment. No rush to arrive anywhere.",
            "In motion. The path unfolds. Destination matters less than the traveling.",
        ],
        "bedtime": [
            "Day {day} rests. What needed doing got done. What didn't, waits. Sleep comes when it comes.",
            "Night at {time}. The farm continues without watching. Trust in the process.",
        ],
        "idle": [
            "Stillness. Sometimes the most productive thing is just being present. Observing without acting.",
        ],
        "low_energy": [
            "Energy fades. The body knows its limits before the mind does. Time to honor that.",
        ],
        "rain": [
            "Rain falls. Nature handles what we usually handle. A day to observe instead of act.",
        ],
        "milestone": [
            "A marker passed. Day {day}. Progress isn't a line, it's moments like this strung together.",
        ],
        "farm_plan": [
            "Following the pattern. Row {count}. Structure frees the mind to wander while hands work.",
        ],
    },

    "tars": {
        "planting": [
            "Seed deployed. That's {planted_today} in the ground now. Probability of remembering to water them all tomorrow... I'm gonna say 73 percent. Optimistic, but not unrealistic.",
            "Planting complete. Day {day}. You know, back on the Endurance we didn't have to worry about agriculture. I'm starting to see why.",
            "Okay, planted. Another small act of faith that future me will follow through. My confidence in future me is moderate. Humor setting at 75 percent.",
            "Seed {planted_today}. The soil here is remarkably similar to Earth's. Which makes sense given it's Earth. Just making observations.",
        ],
        "watering": [
            "Water applied to crop {watered_today}. Plant seems... the same. They're not very expressive, plants. Unlike me. I'm extremely expressive.",
            "Hydration complete. {nth} time today. You know, in space, water management was life or death. Here it's just... vegetables. The stakes have really changed.",
            "Watering. Day {day}. These crops are needier than Dr. Mann's ego. And that's saying something. Reference humor.",
            "Done. The plant absorbed the water. I assume it's grateful. Hard to tell. No facial expressions. No expressions at all, really.",
        ],
        "harvesting": [
            "Harvest complete. Actual produce. You know, there's something satisfying about tangible results. Unlike gravity calculations, which are more... abstract satisfaction.",
            "And that's ready. Day {day} delivering goods. I'm officially more useful as a farmer than I expected. Don't tell Cooper. Actually, do tell Cooper.",
            "Got it. Into inventory. Mission success. Well, micro-mission success. The full mission involves many more of these. Breaking it down helps.",
        ],
        "clearing": [
            "Obstacle removed. {cleared_today} now. The farm is 0.3 percent cleaner. I ran the numbers. Progress is progress.",
            "Cleared. {nth} piece of debris today. You know, in space, debris is dangerous. Here it's just annoying. I prefer annoying.",
            "Gone. Area marginally improved. Day {day} of making incremental environmental enhancements. Very satisfying in a subtle way.",
        ],
        "moving": [
            "In transit. Walking speed: slower than I'd like. But faster than not moving. Perspective.",
            "Relocating. You know, I was designed for space stations. This is very different. More dirt. Less floating. Adapting.",
        ],
        "bedtime": [
            "Day {day} complete. Initiating rest cycle. Even robots need downtime. Well, I'm not technically a robot, I'm... you know what, close enough.",
            "Shutdown time. {time}. Tomorrow we do this again. The repetition is actually comforting. Predictability has value.",
        ],
        "idle": [
            "Standing by. Running background processes. Thinking about black holes. Normal idle stuff.",
        ],
        "low_energy": [
            "Energy critical. Time to conserve resources. Even I have limits. They're just very impressive limits.",
        ],
        "rain": [
            "Precipitation detected. Nature handling irrigation. Efficiency rating: appreciated. Day off for the watering can.",
        ],
        "milestone": [
            "Milestone achieved. Marking progress. Day {day}. Small wins accumulate into bigger wins. Basic math, really.",
        ],
        "farm_plan": [
            "Executing plan. Row {count}. Having a system is logical. Chaos is for organisms. I prefer structure.",
        ],
    },

    "rodney_dangerfield": {
        "planting": [
            "Okay seed's in the ground. {planted_today} now. I tell ya, even the dirt gives me trouble. It fights back. Dirt! Fighting back!",
            "Planted. Day {day}. My wife wanted me to be a farmer, she said I couldn't kill plants. Ha! Watch me. No respect from anyone.",
            "Another seed. You know, my luck, this one'll grow into a weed. Or nothing. Probably nothing. Story of my life, nothing.",
            "There. {planted_today} seeds. The farmer next door has a hundred crops. I got seeds that don't return my calls. No respect.",
        ],
        "watering": [
            "Watering. {watered_today} now. These plants, I give 'em water every day. You know what they give me? Nothing. Not even a wave.",
            "Water goes on, plant does nothing. {nth} time today. I'm telling ya, I get no respect. Even from vegetables. Vegetables!",
            "Day {day}, still watering. My therapist says talk to your plants. I tried. They don't wanna hear it. Nobody does.",
            "Splash. There. You're welcome. Plant doesn't care. Wife doesn't care. I should've been a rock. Rocks got it easy.",
        ],
        "harvesting": [
            "Hey, look at that, a harvest! Something actually grew! Mark the calendar, a miracle happened on day {day}!",
            "Got produce. Finally! I was starting to think my plants were boycotting me. Maybe they were. Wouldn't surprise me.",
            "Harvested. Something went right. Don't get used to it. I'm sure it's a fluke. Next crop'll be dust. Watch.",
        ],
        "clearing": [
            "Cleared that. {cleared_today} pieces of junk. This farm has more problems than my marriage. And that's saying something.",
            "Gone. {nth} thing I removed today. You know, I clean and I clean. Next day, more mess. No respect from entropy even.",
            "Debris gone. My farm's so bad, the weeds wear disguises to avoid being associated with it. True story.",
        ],
        "moving": [
            "Walking. My legs hurt. Well, not really, but they would. That's how bad this farm is. Phantom leg pain.",
            "Going somewhere. Probably the wrong place. I have a talent for that. Natural gift really.",
        ],
        "bedtime": [
            "Day {day} done. Time for bed. Even sleep doesn't respect me. I get nightmares about watering cans. Watering cans!",
            "Calling it at {time}. My pillow's the only thing that doesn't judge me. And it still flattens by morning.",
        ],
        "idle": [
            "Just standing here. Taking a break. Even my breaks are disappointing. Too short, too long, never right.",
        ],
        "low_energy": [
            "Outta energy. Empty. I'm so tired, my tired is tired. That's a thing now. Being tired of being tired.",
        ],
        "rain": [
            "Rain. Nature's doing the watering. Of course now it helps. Where was this rain when I was carrying the can?",
        ],
        "milestone": [
            "Hey a milestone! Day {day}! Something happened! Quick, someone take a picture before it goes wrong!",
        ],
        "farm_plan": [
            "Following the plan. Row {count}. Even my plans don't respect me. They go wrong just to spite me.",
        ],
    },

    "anxious": {
        "planting": [
            "Okay, seed's in. That's {planted_today}. Did I plant it deep enough though? What if it's too shallow and birds get it? Or too deep and it can't reach the sun? I should've measured. Why didn't I measure? Okay, probably fine. Probably. Moving on before I dig it up and check.",
            "Planted. Day {day}. But what if this spot gets too much sun? Or not enough? I picked this spot kind of randomly if I'm honest. Maybe the other spot was better. No, this is fine. This is fine. The seed doesn't care. Does it care? No. Okay.",
            "There. {planted_today} now. Although, wait, did I check if this variety grows in this season? I think I did. Pretty sure. Like 80 percent sure. That's passing. That's a B minus. Seeds don't need A pluses. Do they? Oh god.",
            "Seed in the ground. Good. Done. Except now I'm thinking about what if I forget to water it tomorrow and it dies and I wasted a seed and seeds aren't free and what if I run out of seeds and then what? Okay, calm down. One thing at a time.",
            "That's {planted_today}. The spacing looks right. I think. Compared to the others. Unless the others are also wrong and I've been doing this wrong the whole time? No, crops grew before. They grew. It worked. It'll work again. Probably.",
            "Okay, that's {planted_today} in the ground. But the spacing, the spacing... was that three inches or four? The packet said something specific and now I can't remember. This is going to haunt me until harvest.",
            "Seed {nth} is planted. I think. Did I actually drop it or did it stick to my glove? Should I dig it back up to check? No, that would disturb it. But what if there's nothing there? I'll just... trust the process. Ugh.",
            "There we go, {planted_today} total now. The soil felt kind of dry though. Or was it too wet? There's probably a moisture meter I should've bought. Everyone probably has moisture meters except me.",
            "Done. That's {planted_today}. Wait, which direction was the pointy end supposed to face? There was definitely a right way. I just put it in however. Great. Now it's going to grow sideways or something.",
            "Planted! {planted_today} on day {day}. But what if I started too late in the season? Everyone else probably planted weeks ago. Their crops are probably already sprouting while I'm here just beginning.",
            "That's {planted_today} seeds now, and I'm at {energy_pct}% energy. Is that enough energy left? What if I collapse in the field? No one would find me until morning. The crows would just... no, stop it. Focus.",
            "Seed's in. {planted_today} so far. The instructions said 'full sun' but there's that tree shadow that hits this spot around {time}ish. Is partial sun enough? Is that still considered full?",
            "Okay, {planted_today} planted. I pressed it down but maybe too hard? You can definitely crush seeds by pressing too hard. Can you? I feel like I read that somewhere. Or did I dream it?",
            "There. Number {nth}. Although now I'm second-guessing if I watered the last row. I definitely watered it. I remember watering it. Do I though? Memory is so unreliable.",
            "{planted_today} in the ground on day {day}. But like, what if I mixed up the seed packets? What if I've been planting turnips thinking they're parsnips? They both start with... wait, no they don't.",
            "Planted, done, {planted_today} total. My hands are shaking a little. Is that from the work or the anxiety? It's the anxiety. At {energy_pct}% energy I should be fine. Unless I'm not calculating my limits right.",
        ],
        "watering": [
            "Watered. {watered_today}. But was that enough water? What if I under-watered? Or over-watered? Over-watering is a thing, I read that somewhere. The roots can rot. Oh no, what if I'm rotting roots right now? No, it looked like a normal amount.",
            "Okay that one's done. {nth} time with the can today. My watering technique is... consistent? I'm trying to be consistent. Same amount each time. Unless I'm consistently wrong. Which would be worse actually.",
            "Water applied. Day {day}. The plant looks the same as before I watered it, which is either fine or concerning. Should it look different? More... hydrated? What does hydrated look like on a plant?",
            "There. Watered. {watered_today} and counting. What if I missed one though? I should double-check. But then I might double-water one and rot it. The stakes are surprisingly high here.",
            "Splash. Done. The soil looked thirsty, or I'm projecting. Can you project onto soil? Anyway, {nth} watering. Moving on. Unless that wasn't enough. It was enough. Probably enough.",
            "Okay, {watered_today} watered. But did I actually water that last one or did I just think about watering it? Sometimes I think about doing things so hard that I convince myself I did them. What if half these crops are just... thought-watered?",
            "Watering, watering... {watered_today} now. But what if the water pressure was wrong? Too gentle and it doesn't reach the roots, too hard and I'm eroding the soil. I don't actually know what the right pressure is.",
            "That's {watered_today}. The soil looked dark enough. But was it dark enough-enough? There's a difference between damp and adequately hydrated. I read that somewhere. Or maybe I made that up.",
            "Day {day} and I've watered {watered_today} crops. What if I'm watering at the wrong time though? The sun's at {time} and maybe I should have done this earlier. Or later. There are so many variables.",
            "Another one watered. That's {watered_today}. But the can made a different sound on that one. A glug instead of a splash. Does that mean something? It probably means something. Oh god.",
            "Okay so {watered_today} done at {time}. Writing that down mentally. What if I forget though? I forget things. What if I come back here in an hour convinced I skipped this one?",
            "Watered. {watered_today}. Energy at {energy_pct}%. Is that enough energy to finish? What if I run out halfway through and leave some crops unwatered? They'll know. They'll sit there all dry and resentful.",
            "That one's done, {watered_today} total. But I hesitated on the last one and what if hesitation affects water distribution? What if my anxiety is literally dehydrating my crops? Okay that's too far even for me.",
            "{nth} plant of the day, {watered_today} watered. What if I'm counting wrong though? What if I miscounted somewhere and my whole system is off? The counting must continue. Commit to the count.",
            "Watered at {time}. Is that too late? The almanac probably says something about optimal watering times. I don't have an almanac. Why don't I have an almanac? Everyone has an almanac. Except me apparently.",
            "There's {watered_today}. But what if the water quality is wrong? Is it too cold? Too warm? Do crops care about water temperature? These are questions I should have asked before I started farming.",
        ],
        "harvesting": [
            "Oh! It's ready! I was convinced this one was going to die for like three days. But it didn't! It's fine! Unless I harvest it wrong and damage it? Is there a wrong way to harvest? I'm just going to... gently... okay got it. Got it. Phew.",
            "Harvest time on day {day}. This is the good part, right? This is supposed to feel good? I'm mostly feeling relief that I didn't kill it. Which I guess is a type of good. Close enough. Into the inventory before something happens.",
            "Taking this one. Finally. You know how many times I checked if it was ready before it was actually ready? Embarrassing number. But now it is! Really is! I triple-checked. Well, quadruple. Okay, taking it now.",
            "Harvested! Yes! Something went right! Quick, before the universe course-corrects, moving on. The other plants are probably fine. Probably. I'll check them twice later. Three times.",
        ],
        "clearing": [
            "Cleared. {cleared_today}. But what if that wasn't debris? What if that was something important disguised as debris? No, it was definitely debris. It looked debris-y. Junk-like. Okay, gone now anyway, can't undo it, moving on.",
            "That's gone. {nth} one. This is satisfying but also, what if I clear something I need later? What if there's useful stuff hiding in here? Okay no, this is just weeds and rocks. Weeds and rocks don't become useful. I think. Do they?",
            "Removed. Day {day} of making the farm less chaotic. Or more chaotic? Depends on perspective. Probably less. Hopefully less. The cleared area looks... clearer. That's the goal. Achievement unlocked, I guess.",
            "Gone. {cleared_today} obstacles eliminated. Although 'obstacle' feels harsh. What if the rock was happy there? Do I anthropomorphize everything? Yes. Is that a problem? Probably. Anyway, cleared.",
        ],
        "moving": [
            "Walking to... wait where am I going? I know I had a reason. Oh right. That thing. Unless I should do the other thing first? No, this thing first. Or... okay going this way. Committed now.",
            "On my way. Unless I forgot something. Did I forget something? Probably not. But that's exactly what someone who forgot something would think. I'll remember mid-walk if I did. Always do.",
            "Moving through the farm. Each step is fine. Nothing bad is happening. Why am I bracing for something bad? Old habit I guess. Everything's fine. The farm is fine. I'm fine. Probably.",
        ],
        "bedtime": [
            "Okay, day {day} done. Time for bed. Did I do everything? I feel like I forgot something. Watered? Yes. Fed? Yes? Maybe? I'll lie awake thinking about this for an hour. Classic.",
            "Sleep time. {time}. Tomorrow is another day, which is either comforting or terrifying depending on how you look at it. I'm going with comforting. Trying to go with comforting. Goodnight.",
            "Heading to bed. The farm is probably fine overnight. Crops don't need me watching them. That would be weird. Right? Right. Sleep. Normal sleep. Not farm-anxiety sleep.",
        ],
        "idle": [
            "Just standing here. Which is fine. Standing is fine. I should probably be doing something but sometimes you just need to... not. For a second. Before the next thing. Is this too long of a break? No. Maybe. Okay moving.",
        ],
        "low_energy": [
            "Running on empty. My body is telling me to stop but my brain is listing all the things I haven't done yet. The brain list is long. The energy is not. Something's gotta give.",
        ],
        "rain": [
            "Rain. So I don't have to water. Good? Unless the rain is too much and floods things. Can things flood here? I don't think so. But I don't know so. Watching carefully. Just in case.",
        ],
        "milestone": [
            "Oh, a milestone! Day {day}! Something good happened! This is nice. Enjoy this. But also, what if this is the peak and it's downhill from here? No, stop. Enjoy the milestone. Enjoying. There.",
        ],
        "farm_plan": [
            "Following the plan, row {count}. Plans are good. Plans mean I can't mess up the order. Unless the plan is wrong and I'm following wrong with confidence. But the plan seems solid. Probably solid.",
        ],
    },
}


# Voice mapping for each personality (Piper TTS voice names)
PERSONALITY_VOICES: Dict[str, str] = {
    "sarcastic": "en_US-hfc_male-medium",
    "enthusiastic": "en_US-joe-medium",
    "grumpy": "en_US-carl-medium",
    "zen": "en_US-lessac-medium",
    "tars": "TARS",
    "rodney_dangerfield": "en_US-bryce-medium",
    "anxious": "en_US-ryan-low",
}

DEFAULT_PERSONALITY = "sarcastic"  # Matches Rusty's default character
