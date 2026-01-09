# StardewAI Skill Architecture

**Author:** Claude (PM)
**Created:** 2026-01-09 Session 20
**Status:** Design Draft

---

## Overview

Current approach: Dump all game knowledge into system prompt, hope VLM remembers it.

New approach: **Hierarchical skill system** with context-aware availability, preconditions, and composable actions.

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     GOAL LAYER                               │
│  "Establish profitable farm" "Befriend Shane" "Floor 40"    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PLANNING LAYER                            │
│  Breaks goals into skill sequences, handles failures         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    SKILL LAYER                               │
│  Contextual skills with preconditions and action sequences   │
│  - water_crop, mine_rock, give_gift, catch_fish, craft_item │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   PRIMITIVE LAYER                            │
│  Raw game commands: move, face, use_tool, interact, menu    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   EXECUTION LAYER                            │
│  SMAPI mod HTTP API - actual game control                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Skill Definition Schema

```yaml
# skills/farming.yaml
water_crop:
  description: "Water an unwatered planted crop"
  category: farming

  preconditions:
    required:
      - type: adjacent_to
        target: unwatered_crop
      - type: equipped
        item: Watering Can
      - type: resource_above
        resource: watering_can_water
        minimum: 1

  actions:
    - face: "{target_direction}"
    - use_tool

  on_success:
    - update: crop.isWatered = true
    - stat: crops_watered_count += 1

  on_failure:
    can_empty:
      message: "Watering can is empty"
      recovery_skill: refill_watering_can
    not_adjacent:
      message: "Not adjacent to crop"
      recovery_skill: navigate_to_crop

harvest_crop:
  description: "Pick a mature crop ready for harvest"
  category: farming

  preconditions:
    required:
      - type: adjacent_to
        target: ready_crop

  actions:
    - face: "{target_direction}"
    - interact

  on_success:
    - update: crop.harvested = true
    - stat: crops_harvested_count += 1
    - inventory: add {crop_yield}
```

---

## Skill Categories

### 1. Farming Skills
```yaml
- clear_debris      # Scythe weeds, axe wood, pickaxe stone
- till_soil         # Hoe on clear ground
- plant_seed        # Seeds on tilled soil
- water_crop        # Watering can on planted crop
- harvest_crop      # Interact with ready crop
- refill_can        # Watering can at water source
- fertilize         # Apply fertilizer before planting
- use_sprinkler     # Place/check sprinkler coverage
```

### 2. Mining Skills
```yaml
- descend_floor     # Find and use ladder/hole
- mine_rock         # Pickaxe on rock/ore
- mine_ore          # Pickaxe on ore node (copper, iron, gold, iridium)
- fight_monster     # Combat engagement
- dodge_attack      # Defensive movement
- use_weapon        # Sword/club attack
- heal              # Eat food for health
- escape_mine       # Use ladder up or warp
```

### 3. Fishing Skills
```yaml
- cast_line         # Start fishing at water
- reel_fish         # Minigame execution (complex!)
- attach_bait       # Add bait to rod
- attach_tackle     # Add tackle to rod
- check_crab_pot    # Harvest crab pot
- bait_crab_pot     # Add bait to crab pot
```

### 4. Social Skills
```yaml
- give_gift         # Give item to NPC (checks preferences)
- talk_to_npc       # Daily conversation
- attend_event      # Festival participation
- accept_quest      # Take quest from board/NPC
- complete_quest    # Turn in quest
- trigger_cutscene  # Heart event conditions
```

### 5. Crafting Skills
```yaml
- craft_item        # Make item from recipe
- process_item      # Put item in machine (keg, preserve jar, etc)
- collect_output    # Get finished product from machine
- smelt_ore         # Furnace operation
- geode_crack       # Blacksmith geode opening
```

### 6. Navigation Skills
```yaml
- go_to_location    # Pathfind to named location
- go_to_npc         # Find NPC by schedule
- go_to_object      # Navigate to specific object
- enter_building    # Door interaction
- exit_building     # Leave interior
- use_minecart      # Fast travel (if unlocked)
- use_horse         # Mount/ride horse
```

### 7. Economy Skills
```yaml
- sell_item         # Shipping bin or shop
- buy_item          # Purchase from shop
- check_prices      # Compare shop prices
- ship_crops        # End of day shipping
```

### 8. Time Management Skills
```yaml
- go_to_bed         # Sleep to end day
- eat_food          # Restore energy
- check_time        # Evaluate remaining day
- wait_for_event    # Wait until specific time
```

---

## Context System

Skills are filtered by current context before presenting to VLM:

```python
class SkillContext:
    def get_available_skills(self, state: GameState) -> List[Skill]:
        """Return only skills whose preconditions CAN be met."""

        available = []
        for skill in self.all_skills:
            # Location filter
            if skill.location_required and state.location != skill.location_required:
                continue

            # Inventory filter
            if skill.item_required and skill.item_required not in state.inventory:
                continue

            # Time filter
            if skill.time_required and not self._time_matches(state.time, skill.time_required):
                continue

            # Energy filter
            if skill.energy_cost > state.energy:
                continue

            # Check if preconditions are satisfiable
            if self._preconditions_possible(skill, state):
                available.append(skill)

        return available
```

---

## Knowledge Base Integration

Skills reference the knowledge base for dynamic information:

```yaml
# knowledge/npcs.yaml
shane:
  loved_gifts: [Beer, Pizza, Hot Pepper, Pepper Poppers]
  liked_gifts: [All Eggs (except Void), All Fruits]
  schedule:
    default:
      "9:00": Marnie's Ranch (inside)
      "13:00": JojaMart
      "17:00": Saloon
    wednesday:
      "9:00": Pierre's Shop (closed, outside)
      "17:00": Saloon
  heart_events:
    2: "Enter Marnie's when Shane is there"
    4: "Enter town, sunny day, 12-17:00"
    6: "Enter Marnie's 8:30-17:00"

# knowledge/crops.yaml
parsnip:
  seasons: [spring]
  days_to_mature: 4
  sell_price: 35
  seed_price: 20
  seed_source: [Pierre]
```

---

## VLM Prompt Integration

Instead of dumping all knowledge, inject relevant context:

```python
def build_prompt(self, state: GameState, goal: str) -> str:
    # Get available skills for current context
    available_skills = self.context.get_available_skills(state)

    # Format skills for VLM
    skills_text = self._format_skills(available_skills)

    # Get relevant knowledge for goal
    relevant_knowledge = self.knowledge.query_for_goal(goal, state)

    prompt = f"""
CURRENT STATE:
{self._format_state(state)}

AVAILABLE SKILLS:
{skills_text}

RELEVANT INFO:
{relevant_knowledge}

GOAL: {goal}

Choose a skill and provide parameters, or explain why you can't proceed.
Response format:
{{
  "reasoning": "why this skill",
  "skill": "skill_name",
  "parameters": {{"target": "...", ...}},
  "fallback": "what to do if this fails"
}}
"""
    return prompt
```

---

## Implementation Phases

### Phase 1: Foundation (This Sprint)
- [ ] Skill schema definition (YAML format)
- [ ] Skill loader and validator
- [ ] Basic farming skills (water, harvest, plant, till)
- [ ] Precondition checker
- [ ] Action sequence executor

### Phase 2: Context System
- [ ] Location-based skill filtering
- [ ] Inventory-based skill filtering
- [ ] Time/energy filtering
- [ ] Dynamic skill availability in prompt

### Phase 3: Knowledge Base
- [ ] NPC data (schedules, gifts, relationships)
- [ ] Item data (prices, sources, uses)
- [ ] Location data (contents, connections)
- [ ] Calendar data (events, seasons)

### Phase 4: Planning Layer
- [ ] Goal decomposition
- [ ] Skill sequencing
- [ ] Failure recovery
- [ ] Progress tracking

### Phase 5: Complex Systems
- [ ] Mining skills + combat
- [ ] Fishing minigame
- [ ] Social interaction
- [ ] Crafting chains

---

## File Structure

```
src/python-agent/
├── skills/
│   ├── __init__.py
│   ├── loader.py           # Load skills from YAML
│   ├── executor.py         # Execute skill action sequences
│   ├── context.py          # Filter available skills
│   └── definitions/
│       ├── farming.yaml
│       ├── mining.yaml
│       ├── fishing.yaml
│       ├── social.yaml
│       ├── crafting.yaml
│       ├── navigation.yaml
│       └── economy.yaml
├── knowledge/
│   ├── __init__.py
│   ├── base.py             # Knowledge query interface
│   ├── data/
│   │   ├── npcs.yaml
│   │   ├── items.yaml
│   │   ├── locations.yaml
│   │   ├── crops.yaml
│   │   └── calendar.yaml
├── planning/
│   ├── __init__.py
│   ├── goal_parser.py      # Break goals into subgoals
│   ├── sequencer.py        # Order skills for goal
│   └── tracker.py          # Track progress
```

---

## Example Flow

**Goal:** "Water all crops and harvest any ready ones"

1. **Planning Layer** decomposes:
   - Subgoal 1: Find and water unwatered crops
   - Subgoal 2: Find and harvest ready crops

2. **Context System** checks state:
   - Location: Farm ✓
   - Has watering can ✓
   - Can water: 25/40 ✓
   - Unwatered crops: 3
   - Ready crops: 2

3. **Skill Layer** presents options:
   ```
   AVAILABLE SKILLS:
   - water_crop: Water unwatered crop (3 available, nearest: 2 tiles right)
   - harvest_crop: Pick ready crop (2 available, nearest: 1 tile up)
   - refill_can: Refill watering can (water source: 15 tiles south)
   ```

4. **VLM** reasons and selects:
   ```json
   {
     "reasoning": "Crop 1 tile up is ready - harvest first since it's closest",
     "skill": "harvest_crop",
     "parameters": {"target": "crop_at_72_17"},
     "fallback": "If not adjacent, navigate closer first"
   }
   ```

5. **Executor** runs skill:
   - Check preconditions: adjacent_to ready_crop? YES
   - Execute: `face up`, `interact`
   - Verify success: crop harvested? YES
   - Update stats: crops_harvested_count += 1

---

## Questions to Resolve

1. **Skill granularity:** How atomic? "water_crop" or "water_crop_at_position"?
2. **Failure handling:** Retry same skill? Switch to recovery skill? Ask VLM?
3. **VLM role:** Pick skills only? Also determine parameters? Full control?
4. **State updates:** Trust SMAPI? Verify visually? Both?

---

*This architecture scales from farming to full game mastery. Start simple, expand systematically.*

— Claude (PM)
