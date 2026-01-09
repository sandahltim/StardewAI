"""Context system for filtering available skills."""
from __future__ import annotations

from typing import Dict, Iterable, List

from .models import Skill
from .preconditions import PreconditionChecker


HARD_FILTERS = {"location_is", "time_between"}


class SkillContext:
    def __init__(self, skills: Iterable[Skill]):
        self.skills = list(skills)
        self.checker = PreconditionChecker()

    def get_available_skills(self, state: Dict) -> List[Skill]:
        available: List[Skill] = []
        for skill in self.skills:
            result = self.checker.check(skill, state)
            if result.met:
                available.append(skill)
                continue
            if self._passes_hard_filters(skill, state):
                available.append(skill)
        return available

    def _passes_hard_filters(self, skill: Skill, state: Dict) -> bool:
        for pre in skill.preconditions:
            if pre.type not in HARD_FILTERS:
                continue
            met, _, _ = self.checker._check_one(pre, state)
            if not met:
                return False
        return True
