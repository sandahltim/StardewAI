"""Skill loader for YAML definitions."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import yaml

from .models import Skill, SkillAction, SkillPrecondition


ALLOWED_CATEGORIES = {
    "farming",
    "mining",
    "fishing",
    "social",
    "crafting",
    "navigation",
    "economy",
    "time_management",
}


class SkillLoader:
    def load_skills(self, skills_dir: str) -> Dict[str, Skill]:
        skills: Dict[str, Skill] = {}
        base = Path(skills_dir)
        if not base.exists():
            return skills
        for path in base.glob("*.yml"):
            skills.update(self._load_file(path))
        for path in base.glob("*.yaml"):
            skills.update(self._load_file(path))
        return skills

    def validate_skill(self, skill: dict) -> bool:
        if not isinstance(skill, dict):
            return False
        if "description" not in skill or "category" not in skill:
            return False
        if skill.get("category") not in ALLOWED_CATEGORIES:
            return False
        # Accept either actions (primitive) or steps (composite)
        has_actions = "actions" in skill and isinstance(skill["actions"], list)
        has_steps = "steps" in skill and isinstance(skill["steps"], list)
        if not has_actions and not has_steps:
            return False
        return True

    def _load_file(self, path: Path) -> Dict[str, Skill]:
        data = yaml.safe_load(path.read_text()) or {}
        if not isinstance(data, dict):
            return {}
        skills: Dict[str, Skill] = {}
        for name, raw in data.items():
            if not self.validate_skill(raw):
                continue
            preconditions = []
            required = (raw.get("preconditions") or {}).get("required") or []
            for entry in required:
                if not isinstance(entry, dict) or "type" not in entry:
                    continue
                params = dict(entry)
                pre_type = params.pop("type")
                preconditions.append(SkillPrecondition(type=pre_type, params=params))
            actions = []
            for action in raw.get("actions", []):
                if isinstance(action, dict):
                    if len(action) != 1:
                        continue
                    action_type, value = next(iter(action.items()))
                    params = {}
                    if isinstance(value, dict):
                        params.update(value)
                    elif value is not None:
                        if action_type == "select_slot":
                            params["slot"] = value
                        elif action_type == "move":
                            params["direction"] = value
                        elif action_type == "face":
                            params["direction"] = value
                        elif action_type == "warp":
                            params["location"] = value
                        else:
                            params["value"] = value
                    actions.append(SkillAction(action_type=action_type, params=params))
                elif isinstance(action, str):
                    actions.append(SkillAction(action_type=action, params={}))
            skill = Skill(
                name=name,
                description=raw.get("description", ""),
                category=raw.get("category", ""),
                preconditions=preconditions,
                actions=actions,
                on_failure=raw.get("on_failure") or {},
            )
            skills[name] = skill
        return skills
