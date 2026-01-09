"""Dataclasses for skills and execution results."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SkillPrecondition:
    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillAction:
    action_type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Skill:
    name: str
    description: str
    category: str
    preconditions: List[SkillPrecondition] = field(default_factory=list)
    actions: List[SkillAction] = field(default_factory=list)
    on_failure: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class PreconditionResult:
    met: bool
    failures: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    success: bool
    actions_taken: List[str] = field(default_factory=list)
    error: Optional[str] = None
    recovery_skill: Optional[str] = None
