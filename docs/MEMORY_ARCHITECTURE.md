# Rusty's Memory Architecture

**Created:** 2026-01-08 by Claude (PM)
**Status:** APPROVED - Ready for Implementation
**Priority:** High

---

## Overview

Give Rusty persistent memory so he can learn from experience and understand Stardew Valley.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     RUSTY'S BRAIN                            │
├────────────────────────┬─────────────────────────────────────┤
│   GAME KNOWLEDGE       │   EPISODIC MEMORY                   │
│   (SQLite - Static)    │   (ChromaDB - Dynamic)              │
│   ────────────────     │   ──────────────────                │
│   Pre-loaded:          │   Stored when:                      │
│   • NPC gift prefs     │   • Action succeeds/fails           │
│   • Crop data          │   • NPC interaction                 │
│   • Fish locations     │   • Discovery (new area/item)       │
│   • Tool upgrades      │   • VLM marks as "notable"          │
│   • Recipes            │                                     │
│   • Schedules          │   Retrieved: Top-3 relevant         │
│   • Map/building info  │   memories per tick                 │
├────────────────────────┴─────────────────────────────────────┤
│   SESSION MEMORY (Already implemented)                       │
│   • Current session positions, actions, tool uses            │
│   • /api/session-memory endpoint                             │
└──────────────────────────────────────────────────────────────┘
```

## Components

### 1. Game Knowledge Database (SQLite)

**Purpose:** Static facts about Stardew Valley - things Rusty "read in a book"

**Tables:**
```sql
-- NPCs and their preferences
CREATE TABLE npcs (
    name TEXT PRIMARY KEY,
    birthday TEXT,           -- "Spring 4"
    location TEXT,           -- Default location
    loved_gifts TEXT,        -- JSON array
    liked_gifts TEXT,
    neutral_gifts TEXT,
    disliked_gifts TEXT,
    hated_gifts TEXT,
    schedule_notes TEXT
);

-- Crop information
CREATE TABLE crops (
    name TEXT PRIMARY KEY,
    season TEXT,             -- "Spring", "Summer", etc.
    growth_days INTEGER,
    regrows BOOLEAN,
    regrow_days INTEGER,
    sell_price INTEGER,
    seed_name TEXT,
    seed_price INTEGER
);

-- Items
CREATE TABLE items (
    name TEXT PRIMARY KEY,
    category TEXT,           -- "Fish", "Forage", "Artifact", etc.
    description TEXT,
    sell_price INTEGER,
    locations TEXT           -- JSON array of where to find
);

-- Locations
CREATE TABLE locations (
    name TEXT PRIMARY KEY,
    type TEXT,               -- "Town", "Farm", "Mine", etc.
    unlocked_by TEXT,        -- How to access
    notable_features TEXT    -- JSON array
);

-- Recipes
CREATE TABLE recipes (
    name TEXT PRIMARY KEY,
    type TEXT,               -- "Cooking", "Crafting"
    ingredients TEXT,        -- JSON: {"Wood": 50, "Stone": 20}
    unlock_condition TEXT
);
```

**Data Sources:**
- Stardew Valley Wiki (structured scrape)
- Existing JSON data files from modding community
- Manual entry for critical facts

### 2. Episodic Memory (ChromaDB)

**Purpose:** Rusty's personal experiences - things he learned by doing

**Schema:**
```python
{
    "id": "mem_001",
    "text": "Gave Shane a beer at the Saloon. He loved it and said thanks.",
    "metadata": {
        "type": "npc_interaction",
        "location": "Saloon",
        "npc": "Shane",
        "item": "Beer",
        "outcome": "positive",
        "game_day": "Spring 5 Y1",
        "timestamp": "2026-01-08T12:00:00"
    }
}
```

**Memory Types:**
- `npc_interaction` - Gifts, conversations
- `discovery` - New areas, items found
- `task_result` - Action outcomes (success/fail)
- `death` - How/where Rusty died
- `notable` - VLM-flagged important moments

**Embedding Model:** nomic-embed-text (~500MB VRAM)

### 3. Memory Triggers

**Auto-store (always remember):**
```python
ALWAYS_REMEMBER = [
    "npc_interaction",    # Any NPC gift/talk
    "item_obtained",      # New item types
    "location_first",     # First visit to area
    "death",              # Always remember deaths
    "tool_upgrade",       # Tool improvements
]
```

**Conditional store:**
- VLM reasoning contains: "remember this", "notable", "important"
- Action failed unexpectedly
- Significant time passed in location (exploring)

### 4. Memory Retrieval

**Per-tick retrieval:**
```python
def get_relevant_memories(current_context):
    # Build query from current state
    query = f"{location} {nearby_npcs} {current_goal}"

    # Get top-3 relevant episodic memories
    memories = chromadb.query(query, n_results=3)

    # Get relevant game knowledge
    if npc_nearby:
        knowledge = db.query("SELECT * FROM npcs WHERE name = ?", npc)

    return format_for_prompt(memories, knowledge)
```

**Prompt injection:**
```
GAME KNOWLEDGE:
- Shane loves Beer, Pizza. Hates Pickles.
- Today is his birthday (Spring 20).

PAST EXPERIENCE:
- Last time you gave Shane a flower, he was grumpy.
- You found him at the Saloon yesterday evening.

CURRENT GOAL: Make friends with Shane
```

## VRAM Budget

| Component | VRAM | Notes |
|-----------|------|-------|
| Qwen3VL-30B | ~21GB | Main model |
| nomic-embed-text | ~500MB | Embedding |
| ChromaDB | ~100MB | In-memory index |
| **Total** | ~21.6GB | Within 24GB 3090 Ti |

## Implementation Phases

### Phase 1: Game Knowledge (Codex)
- [ ] Create SQLite schema
- [ ] Find/scrape Stardew data (NPCs, crops, items)
- [ ] Populate database
- [ ] Create query helpers
- [ ] Expose via `/api/game-knowledge`

### Phase 2: Episodic Memory (Claude)
- [ ] Set up ChromaDB
- [ ] Integrate embedding model
- [ ] Create memory storage triggers
- [ ] Create retrieval function

### Phase 3: Integration (Claude)
- [ ] Add memory context to VLM prompt
- [ ] Test with NPC interactions
- [ ] Test with farming tasks
- [ ] Tune retrieval (top-K, relevance threshold)

### Phase 4: Polish (Both)
- [ ] Memory viewer in UI (Codex)
- [ ] Memory pruning/consolidation (Claude)
- [ ] Performance optimization

## File Locations

```
src/
├── python-agent/
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── game_knowledge.py    # SQLite queries
│   │   ├── episodic.py          # ChromaDB operations
│   │   └── retrieval.py         # Combined retrieval
│   └── unified_agent.py         # Integration point
├── ui/
│   └── storage.py               # Add game_knowledge.db
└── data/
    ├── game_knowledge.db        # SQLite database
    ├── npcs.json                # Source data
    ├── crops.json
    └── items.json
```

## Success Criteria

1. Rusty knows NPC gift preferences without being told
2. Rusty remembers past interactions ("Shane liked the beer I gave him")
3. Rusty can answer "What did I do yesterday?"
4. Memory retrieval adds <100ms latency per tick
5. Total VRAM stays under 22GB

---

*Approved by Tim. Implementation starting next session.*

— Claude (PM)
