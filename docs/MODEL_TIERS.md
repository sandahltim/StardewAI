# Model Tier System

## Overview

StardewAI uses multiple models with different cost/capability trade-offs. The system escalates to smarter (more expensive) models only when needed.

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODEL ESCALATION LADDER                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TIER 4: Claude Opus (emergency/complex)                        │
│    └── Debugging failures, novel situations                     │
│    └── Token budget: ~1000/day max                              │
│                     ▲                                           │
│                     │ escalate if Sonnet fails                  │
│                                                                  │
│  TIER 3: Claude Sonnet (smart reasoning)                        │
│    └── Complex multi-step planning                              │
│    └── Problem solving, strategy                                │
│    └── Token budget: ~10000/day                                 │
│                     ▲                                           │
│                     │ escalate if stuck or complex              │
│                                                                  │
│  TIER 2: Qwen3 VL (vision - network server)                     │
│    └── Screen perception                                        │
│    └── Visual action execution                                  │
│    └── Menu/UI reading                                          │
│                     ▲                                           │
│                     │ always used for vision                    │
│                                                                  │
│  TIER 1: Nemotron Nano (fast - local)                           │
│    └── Simple decisions                                         │
│    └── Movement, tool use                                       │
│    └── Routine task execution                                   │
│    └── No cost, always available                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## When to Escalate

### Tier 1 → Tier 2 (Nemotron → Qwen VL)
- Need to see the screen
- Action verification required
- Unknown visual situation

### Tier 1/2 → Tier 3 (Local → Sonnet)
- Task failed 3+ times
- Complex planning needed (multi-day strategy)
- Unexpected game state
- User asked complex question

### Tier 3 → Tier 4 (Sonnet → Opus)
- Sonnet response didn't solve problem
- Critical debugging needed
- Very complex reasoning required
- User explicitly requests

## Implementation

```python
# models/router.py

from enum import IntEnum
from dataclasses import dataclass

class ModelTier(IntEnum):
    NEMOTRON = 1      # Local, fast, free
    QWEN_VL = 2       # Network, vision, free (self-hosted)
    SONNET = 3        # API, smart, paid
    OPUS = 4          # API, smartest, expensive

@dataclass
class TokenBudget:
    daily_sonnet: int = 10000
    daily_opus: int = 1000
    used_sonnet: int = 0
    used_opus: int = 0

class ModelRouter:
    def __init__(self, config: Config, budget: TokenBudget):
        self.nemotron = NemotronClient(config.nemotron_url)
        self.qwen = QwenVLClient(config.qwen_url)
        self.anthropic = AnthropicClient(config.anthropic_key)
        self.budget = budget
        self.failure_count = 0

    async def query(self,
                    prompt: str,
                    image: Optional[Image] = None,
                    min_tier: ModelTier = ModelTier.NEMOTRON,
                    task_type: str = "general") -> ModelResponse:
        """
        Route query to appropriate model based on requirements.
        """
        # Vision tasks always need Qwen VL
        if image is not None:
            return await self._query_qwen(prompt, image)

        # Start at minimum required tier
        tier = max(min_tier, self._assess_complexity(prompt, task_type))

        # Check if we should escalate due to failures
        if self.failure_count >= 3:
            tier = max(tier, ModelTier.SONNET)

        # Execute at chosen tier
        if tier == ModelTier.NEMOTRON:
            return await self._query_nemotron(prompt)
        elif tier == ModelTier.SONNET:
            return await self._query_sonnet(prompt)
        elif tier == ModelTier.OPUS:
            return await self._query_opus(prompt)

    async def _query_sonnet(self, prompt: str) -> ModelResponse:
        """Query Claude Sonnet with budget awareness."""
        if self.budget.used_sonnet >= self.budget.daily_sonnet:
            # Budget exhausted, fall back to local
            print("WARN: Sonnet budget exhausted, using Nemotron")
            return await self._query_nemotron(prompt)

        response = await self.anthropic.query(
            model="claude-sonnet-4-20250514",
            prompt=prompt
        )
        self.budget.used_sonnet += response.tokens_used
        return response

    async def _query_opus(self, prompt: str) -> ModelResponse:
        """Query Claude Opus - use sparingly!"""
        if self.budget.used_opus >= self.budget.daily_opus:
            print("WARN: Opus budget exhausted, using Sonnet")
            return await self._query_sonnet(prompt)

        response = await self.anthropic.query(
            model="claude-opus-4-20250514",
            prompt=prompt
        )
        self.budget.used_opus += response.tokens_used
        return response

    def _assess_complexity(self, prompt: str, task_type: str) -> ModelTier:
        """Determine minimum tier based on task."""
        complex_keywords = ["plan", "strategy", "debug", "why", "problem"]

        if task_type == "planning" and len(prompt) > 500:
            return ModelTier.SONNET

        if any(kw in prompt.lower() for kw in complex_keywords):
            return ModelTier.SONNET

        return ModelTier.NEMOTRON

    def report_failure(self):
        """Call when an action/plan fails."""
        self.failure_count += 1

    def report_success(self):
        """Call when action succeeds."""
        self.failure_count = max(0, self.failure_count - 1)
```

## Configuration

```yaml
# config/settings.yaml additions

models:
  # ... existing nemotron and qwen_vl config ...

  # Claude API (optional - enables Tier 3 & 4)
  anthropic:
    enabled: true
    api_key_env: "ANTHROPIC_API_KEY"  # Read from environment

  # Token budgets (per day)
  budgets:
    sonnet_daily: 10000
    opus_daily: 1000

  # Escalation settings
  escalation:
    failures_before_escalate: 3
    auto_escalate_planning: true
    log_escalations: true
```

## Cost Awareness

### Approximate Token Costs (as of 2025)

| Model | Input $/1M | Output $/1M | Typical Query |
|-------|------------|-------------|---------------|
| Nemotron Nano | $0 | $0 | Free (local) |
| Qwen3 VL | $0 | $0 | Free (self-hosted) |
| Claude Sonnet | $3 | $15 | ~$0.01-0.05 |
| Claude Opus | $15 | $75 | ~$0.05-0.25 |

### Budget Example

With 10,000 Sonnet tokens/day and 1,000 Opus tokens/day:
- ~100-200 Sonnet queries (short prompts)
- ~10-20 Opus queries (emergency only)

Typical day usage:
- 99% handled by Nemotron (free)
- Vision by Qwen VL (free)
- 5-10 Sonnet calls for complex planning
- 0-2 Opus calls for debugging

## Switching Provider Mid-Session

The agent can dynamically switch based on:
1. Task complexity
2. Failure rate
3. User request
4. Budget remaining

```python
# Example: User can force tier
async def handle_user_message(msg: str):
    if msg.startswith("/opus "):
        # User wants Claude's best for this
        return await router.query(msg[6:], min_tier=ModelTier.OPUS)
    elif msg.startswith("/sonnet "):
        return await router.query(msg[8:], min_tier=ModelTier.SONNET)
    else:
        # Auto-route
        return await router.query(msg)
```

## Logging & Monitoring

Track model usage for cost awareness:

```python
# Daily summary
{
    "date": "2025-01-06",
    "queries": {
        "nemotron": 5420,
        "qwen_vl": 892,
        "sonnet": 23,
        "opus": 2
    },
    "tokens": {
        "sonnet_input": 4521,
        "sonnet_output": 2103,
        "opus_input": 892,
        "opus_output": 445
    },
    "estimated_cost_usd": 0.12
}
```
