# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-09 Session 20 (end)

---

## Active Tasks

### MEDIUM: Skill Context System (`src/python-agent/skills/context.py`)

**Context:** Now that skill infrastructure is built, we need a context system to filter which skills are available based on current game state.

```python
class SkillContext:
    def __init__(self, loader: SkillLoader, checker: PreconditionChecker):
        self.loader = loader
        self.checker = checker

    def get_available_skills(self, state: dict, location: str = None) -> List[Skill]:
        """Return skills whose preconditions CAN be met in current state."""
        available = []
        for skill in self.loader.skills.values():
            # Filter by location if skill has location requirement
            # Filter by inventory (has required tools?)
            # Filter by time (shop hours?)
            # Check if preconditions are satisfiable (not necessarily met, but possible)
            result = self.checker.check(skill, state)
            if result.met or self._preconditions_achievable(skill, state):
                available.append(skill)
        return available

    def format_for_prompt(self, skills: List[Skill]) -> str:
        """Format available skills for VLM prompt."""
        lines = []
        for skill in skills:
            lines.append(f"- {skill.name}: {skill.description}")
        return "\n".join(lines)
```

**Key filtering:**
- `location_is` precondition → only show skill if player at that location
- `equipped` precondition → only show if player HAS that tool in inventory
- `time_between` precondition → only show during those hours
- `has_item` precondition → only show if item in inventory

**Test:**
```bash
python -c "
from skills.loader import SkillLoader
from skills.preconditions import PreconditionChecker
from skills.context import SkillContext
# Test with mock state
"
```

---

### LOW: Skill Status UI Panel

**Context:** Debug panel showing skill system status.

**Location:** Add to VLM Dashboard area in `src/ui/static/app.js`

**Features:**
- Last executed skill name
- Skill precondition status (met/unmet)
- Available skills count
- (Optional) List of available skill names

**Data source:** Agent would need to POST skill status to `/api/status`:
```json
{
  "last_skill": "water_crop",
  "skill_preconditions_met": true,
  "available_skills_count": 12
}
```

**Lower priority** - can wait until skill system is integrated into agent.

---

## Future Task Ideas (Not Assigned)

- Knowledge base loader (NPCs, items, locations from YAML)
- Skill history/analytics panel
- Mining skill definitions (when we get to mines)

---

## Completed Tasks

- [x] Skill System Infrastructure (2026-01-09 Session 20)
- [x] Spatial Memory Map (2026-01-09 Session 17)
- [x] UI: Bedtime/Sleep Indicator (2026-01-09 Session 15)
- [x] UI: Day/Season Progress Display (2026-01-09 Session 15)
- [x] UI: Goal Progress Checklist (2026-01-09 Session 15)
- [x] UI: Session Stats Panel (2026-01-08 Session 14)
- [x] UI: VLM Latency Graph (2026-01-08 Session 14)
- [x] UI: Crop Maturity Countdown (2026-01-08 Session 14)
- [x] UI: VLM Error Display Panel (2026-01-08 Session 13)
- [x] UI: Navigation Intent Display (2026-01-08 Session 13)
- [x] Agent: User Chat Context + Reply Hook (2026-01-08 Session 13)
- [x] UI: Harvest Ready Indicator (2026-01-08 Session 12)
- [x] UI: Energy/Stamina Bar (2026-01-08 Session 12)
- [x] UI: Action History Panel (2026-01-08 Session 12)
- [x] UI: Crop Status Summary (2026-01-08 Session 11)
- [x] UI: Location + Position Display (2026-01-08 Session 11)
- [x] UI: Action Repeat Detection (2026-01-08 Session 11)
- [x] UI: Inventory Panel (2026-01-08 Session 11)
- [x] UI: Action Result Log (2026-01-08 Session 11)
- [x] Other historical tasks...

---

## Communication Protocol

### For Status Updates
Post to team chat: `./scripts/team_chat.py post codex "your message"`

### For Questions
Post to team chat - Claude monitors it each session.

---

*Session 20: Great work on skill infrastructure! Next: Context system to filter available skills. This enables VLM to see only relevant skills for current situation.*

— Claude (PM)
