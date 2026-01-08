# Next Session - StardewAI

**Last Updated:** 2026-01-08 by Claude
**Status:** ✅ Spatial Awareness WORKING + Better Blocker Names

---

## What's Working

| Component | Status | Notes |
|-----------|--------|-------|
| llama-server | Running | Port 8780, Qwen3VL-30B loaded |
| SMAPI mod | Running | Port 8790, all actions + /surroundings |
| UI Server | Running | Port 9001, team chat + VLM dashboard |
| VLM Perception | Working | Location, time, energy, tool detection |
| VLM Reasoning | Working | Contextual plans with personality |
| **Spatial Awareness** | **WORKING** | /surroundings + VLM uses directional info |
| **Blocker Names** | **NEW** | Returns "Stone", "Tree", NPC names, not just "blocked" |
| Action Execution | Working | Move, face, interact, cancel, toolbar, warp |
| Single Player Mode | Working | Full screen capture, solo prompts |
| Session Memory | Working | /api/session-memory endpoint ready |

## Known Issues (All Major Fixed!)

### 1. ~~VLM Spatial Bias~~ ✅ FIXED
- **Solution:** /surroundings endpoint + directional context in VLM prompt
- Agent chooses clear directions, navigates around obstacles

### 2. Duration vs Tiles Format (Minor)
- Prompt specifies `tiles` but VLM sometimes outputs `duration`
- ModBridgeController converts duration→tiles as fallback
- Works fine, cosmetic issue

### 3. ~~Indoor Navigation~~ ✅ FIXED
- Now uses spatial awareness to navigate farmhouse correctly

## Session Accomplishments (2026-01-08)

**Session 1 (Single Player Mode):**
1. Switched from co-op to single player mode
2. Fixed logging (force=True)
3. Fixed single mode action execution
4. Codex: SMAPI actions (menu, cancel, toolbar)
5. Codex: VLM dashboard panel

**Session 2 (Spatial Awareness):**
1. Integrated /surroundings endpoint into VLM prompt
2. Agent now makes directionally-informed decisions
3. Fixed UI crash on session-memory 404
4. Codex: Better blocker names (NPCs, objects, terrain, buildings)
5. Codex: Session memory endpoint
6. Codex: Movement history panel

## Files Changed

**Session 2:**
- `src/python-agent/unified_agent.py` - get_surroundings(), format_surroundings(), spatial context
- `src/smapi-mod/StardewAI.GameBridge/GameStateReader.cs` - GetBlockerName() improvements
- `docs/CODEX_TASKS.md` - Task tracking
- `docs/NEXT_SESSION.md` - This file

## Next Steps (Priority Order)

### High Priority
1. **Memory System Implementation** - APPROVED
   - See `docs/MEMORY_ARCHITECTURE.md` for full design
   - Codex: Game Knowledge DB (SQLite with Stardew data)
   - Claude: ChromaDB + episodic memory integration

2. **Farm Task Automation**
   - Test watering crops with spatial awareness
   - Test tool use on specific objects
   - Test harvesting

### Medium Priority
3. **Goal-Directed Navigation**
   - "Go to the chest" → find path → execute
   - Use blocker names to identify targets

4. **Codex Tasks (in progress)**
   - Directional compass widget
   - Session events timeline

### Low Priority
5. **Co-op Mode**
   - Split screen when single player is solid

---

## Memory Options for Rusty

### Current State
- Session memory: SQLite via /api/session-memory (positions, actions)
- No persistent memory across sessions
- No semantic search

### Options to Discuss

#### 1. ChromaDB (Vector Store)
**Pros:**
- Semantic search ("what did I do near the pond?")
- Easy Python integration
- Lightweight, runs locally
- Good for: Farm knowledge, NPC relationships, past experiences

**Cons:**
- Another service to run
- Embedding model needed (could use llama.cpp)

**Use cases:**
- "Remember I planted parsnips here"
- "Shane likes beer" (NPC preferences)
- "Last time I went to the mines, I died on floor 15"

#### 2. RAG (Retrieval-Augmented Generation)
**Approach:**
- Store experiences as text chunks
- Embed with small model (nomic-embed, etc.)
- Retrieve relevant memories before VLM inference
- Inject into prompt: "RELEVANT MEMORIES: ..."

**Architecture:**
```
Experience → Embed → ChromaDB
                         ↓
Query → Embed → Search → Top-K memories → VLM prompt
```

#### 3. Structured Knowledge Graph
**Pros:**
- Explicit relationships (NPC→likes→item)
- Easy to query specific facts
- SQLite or Neo4j

**Cons:**
- More rigid, harder to capture fuzzy knowledge
- Requires schema design

#### 4. Hybrid Approach (Recommended)
- **SQLite:** Structured facts (NPC schedules, crop timings, recipes)
- **ChromaDB:** Episodic memories, experiences, fuzzy knowledge
- **Session Memory:** Current session actions (already have this)

### Implementation Path
1. Start with ChromaDB for episodic memory
2. Small embedding model (nomic-embed-text via llama.cpp)
3. Store: location, time, action, outcome, reasoning
4. Retrieve top-3 relevant memories per tick
5. Add to VLM prompt: "PAST EXPERIENCE: ..."

### Questions to Decide
- How much VRAM can we spare for embedding model?
- What should trigger memory storage? (every action? significant events?)
- How to handle memory pruning/forgetting?

---

## Session Startup Checklist

1. Check GPU memory: `nvidia-smi`
2. Start llama-server if needed: `./scripts/start-llama-server.sh`
3. Start Stardew Valley via Steam (with SMAPI)
4. Verify mod: `curl http://localhost:8790/health`
5. Start UI server: `uvicorn src.ui.app:app --host 0.0.0.0 --port 9001 &`
6. Run agent: `python src/python-agent/unified_agent.py --goal "..."`

## Architecture Reference

```
Screenshot → Qwen3VL (8780) → Actions → ModBridgeController → SMAPI mod (8790) → Game
                ↑                              │
                │                              └── /surroundings (spatial context)
                │
        [Future: ChromaDB memories]
```

## Team Status

| Team Member | Status | Current Focus |
|-------------|--------|---------------|
| Claude | PM | Memory architecture, coordination |
| Codex | Active | Compass widget, session timeline |
| Tim | Lead | Testing, direction, memory decisions |

---

*Spatial awareness complete. Next: memory architecture for smarter Rusty.*

— Claude (PM)
