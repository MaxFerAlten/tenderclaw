"""Enhanced Skills Loader — Wave 2 skill discovery and injection.

Skills are directories containing SKILL.md files. This module provides
rich parsing of SKILL.md (trigger, agents, flow, rules) and a structured
Skill registry for the runtime. It replaces the basic legacy implementation
with a full parser and a skill registry that can be queried at runtime.

Sprint 5 additions:
- SkillMatch: structured result from SkillSelector
- SkillSelector: automatic skill selection by task, pipeline phase, risk level
- SkillTrace: in-memory audit trail of recent selections (last 200 entries)
"""

from __future__ import annotations

import re
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Self

logger = logging.getLogger("tenderclaw.core.skills")

DEFAULT_SKILLS_PATHS = [
    Path(__file__).parent.parent.parent / "skills",
    Path(r"d:\MY_AI\claude-code\superpowers\skills"),
]


@dataclass
class Skill:
    """Structured skill metadata parsed from SKILL.md."""

    name: str
    path: Path
    trigger: str = ""
    description: str = ""
    agents: list[str] = field(default_factory=list)
    flow: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    raw: str = ""


class SkillRegistry:
    """In-memory registry of discovered skills."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def by_agent(self, agent: str) -> list[Skill]:
        return [s for s in self._skills.values() if agent in s.agents]

    def __len__(self) -> int:
        return len(self._skills)


# Global singleton registry
_skill_registry: SkillRegistry | None = None


def get_registry() -> SkillRegistry:
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
        discover_skills(_skill_registry)
    return _skill_registry


def add_skills_path(path: str | Path) -> None:
    """Add a skills path to the default search paths."""
    p = Path(path)
    if p.exists() and p not in DEFAULT_SKILLS_PATHS:
        DEFAULT_SKILLS_PATHS.append(p)
        logger.info("Added skills path: %s", p)


def discover_skills(registry: SkillRegistry, paths: list[Path] | None = None) -> None:
    """Scan SKILLS_PATHS and register all discovered skills."""
    search_paths = paths or DEFAULT_SKILLS_PATHS
    for base_path in search_paths:
        if not base_path.exists():
            logger.debug("Skills path does not exist: %s", base_path)
            continue
        for skill_dir in base_path.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                skill = parse_skill(skill_dir.name, skill_md)
                registry.register(skill)
                logger.debug("Registered skill: %s", skill.name)
            except Exception as exc:
                logger.warning("Failed to parse skill %s: %s", skill_dir.name, exc)


def parse_skill(name: str, skill_md: Path) -> Skill:
    """Parse a SKILL.md file into a structured Skill object."""
    content = skill_md.read_text("utf-8")
    lines = content.splitlines()

    skill = Skill(name=name, path=skill_md, raw=content)

    # Extract ## Sections
    current_section = ""
    section_lines: list[str] = []

    def flush():
        nonlocal current_section, section_lines
        cn = current_section.lower().strip()
        if cn == "trigger":
            skill.trigger = "\n".join(section_lines).strip()
        elif cn == "description":
            skill.description = "\n".join(section_lines).strip()
        elif cn == "agents":
            skill.agents = [l.strip().lstrip("- *") for l in section_lines if l.strip()]
        elif cn == "flow":
            skill.flow = [re.sub(r"^\d+\.\s*", "", l).strip() for l in section_lines if l.strip()]
        elif cn == "rules":
            skill.rules = [l.strip().lstrip("- ") for l in section_lines if l.strip()]

    for line in lines:
        if line.startswith("## "):
            flush()
            current_section = line[3:].strip()
            section_lines = []
        elif line.startswith("# ") and not current_section:
            # Title line — use as description fallback
            skill.description = line[1:].strip().lstrip("/").strip()
        else:
            section_lines.append(line)

    flush()
    # Fallback description
    if not skill.description:
        skill.description = "Specialized workflow skill."
    return skill


def list_available_skills() -> list[dict[str, Any]]:
    """Return a list of all skills found in the SKILLS_PATHS (legacy dict format)."""
    reg = get_registry()
    return [
        {
            "name": s.name,
            "path": str(s.path),
            "description": s.description,
            "trigger": s.trigger,
            "agents": s.agents,
        }
        for s in reg.all()
    ]


def build_skills_instruction() -> str:
    """Consolidate all skills into a prompt section for the agent (enhanced format)."""
    skills = list_available_skills()
    if not skills:
        return ""

    instruction = "\n## Superpowers Skills\n"
    instruction += "You have access to specialized 'skills' for complex tasks.\n"
    instruction += "If a task matches one of these, you MUST read the SKILL.md file before proceeding:\n"

    for s in skills:
        trigger = f" (trigger: {s['trigger']})" if s.get("trigger") else ""
        instruction += f"- **{s['name']}**{trigger}: {s['description']}\n"
        instruction += f"  Path: `{s['path']}`\n"

    instruction += "\nTo read a skill, use the `Read` tool on its path listed above."
    return instruction


def get_skill_by_name(name: str) -> Skill | None:
    return get_registry().get(name)


def match_trigger(text: str) -> list[Skill]:
    """Return skills whose trigger pattern matches the given text."""
    reg = get_registry()
    matched = []
    for s in reg.all():
        if s.trigger and s.trigger.lstrip("/") in text:
            matched.append(s)
    return matched


# ---------------------------------------------------------------------------
# SkillMatch — structured selection result
# ---------------------------------------------------------------------------


@dataclass
class SkillMatch:
    """Result of a SkillSelector.select() call.

    Attributes:
        skill:      The matched Skill, or None if no relevant skill found.
        skill_name: Name of the matched skill (empty string if no match).
        confidence: 0.0–1.0 — how confident the selector is in the match.
        reason:     Human-readable rationale for the selection.
        phase:      Pipeline phase used during selection.
        risk:       Risk level used during selection.
    """

    skill: Skill | None
    skill_name: str
    confidence: float
    reason: str
    phase: str = ""
    risk: str = "medium"

    @property
    def matched(self) -> bool:
        return self.skill is not None and self.confidence > 0.0


@dataclass
class SkillTraceEntry:
    """A single entry in the skill selection audit trail."""

    timestamp: datetime
    task_snippet: str   # first 120 chars of the task
    phase: str
    risk: str
    skill_name: str
    confidence: float
    reason: str


# ---------------------------------------------------------------------------
# SkillSelector — automatic skill selection engine
# ---------------------------------------------------------------------------

# Phase → skill name hints (skills that are a natural fit for a pipeline phase)
_PHASE_AFFINITY: dict[str, list[str]] = {
    "research":    ["deepsearch", "analyze", "deep-interview"],
    "plan":        ["ralplan", "writing-plans", "brainstorming"],
    "implement":   ["autopilot", "ultrawork", "tdd", "build-fix"],
    "fix":         ["build-fix", "doctor"],
    "review":      ["code-review", "review", "security-review", "ultraqa"],
    "security":    ["security", "security-review"],
    "team":        ["team", "swarm", "worker"],
}

# Risk level → skills to prefer / avoid
_HIGH_RISK_BOOST: set[str] = {"security", "security-review", "code-review", "ultraqa"}
_HIGH_RISK_PENALTY: set[str] = {"autopilot", "ultrawork"}  # too autonomous for high-risk tasks


class SkillSelector:
    """Automatic skill selection based on task description, pipeline phase, and risk.

    Usage::

        selector = SkillSelector()
        match = selector.select("write tests for the auth module", phase="implement", risk="low")
        if match.matched:
            print(match.skill_name, match.confidence, match.reason)
    """

    # Minimum confidence to consider a match valid
    CONFIDENCE_THRESHOLD: float = 0.25

    def __init__(self) -> None:
        self._trace: deque[SkillTraceEntry] = deque(maxlen=200)

    def select(
        self,
        task: str,
        phase: str = "",
        risk: str = "medium",
        *,
        registry: SkillRegistry | None = None,
    ) -> SkillMatch:
        """Select the best skill for *task* at *phase* with *risk*.

        Args:
            task:     Natural-language task description.
            phase:    Pipeline phase: "research"|"plan"|"implement"|"fix"|"review"|"security"|"team".
            risk:     Risk level: "low"|"medium"|"high"|"critical".
            registry: Override registry (used in tests; defaults to global singleton).

        Returns:
            A :class:`SkillMatch` with the best candidate or an empty no-match result.
        """
        reg = registry if registry is not None else get_registry()
        skills = reg.all()

        if not skills:
            return self._no_match(task, phase, risk, "no skills registered")

        task_lower = task.lower()
        task_words = set(re.findall(r"\w+", task_lower))
        risk_lower = risk.lower()
        phase_lower = phase.lower()

        scored: list[tuple[float, Skill, str]] = []

        for skill in skills:
            score, reason_parts = self._score_skill(
                skill, task_lower, task_words, phase_lower, risk_lower
            )
            if score > 0:
                scored.append((score, skill, "; ".join(reason_parts)))

        if not scored:
            return self._no_match(task, phase, risk, "no skill scored above zero")

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_skill, best_reason = scored[0]

        # Normalise confidence to 0–1 (raw scores range ~0–5)
        confidence = min(best_score / 5.0, 1.0)

        if confidence < self.CONFIDENCE_THRESHOLD:
            return self._no_match(
                task, phase, risk,
                f"best candidate '{best_skill.name}' below threshold "
                f"(confidence={confidence:.2f})"
            )

        match = SkillMatch(
            skill=best_skill,
            skill_name=best_skill.name,
            confidence=round(confidence, 3),
            reason=best_reason,
            phase=phase,
            risk=risk,
        )
        self._record_trace(task, match)
        logger.info(
            "SkillSelector: task=%r → skill=%s confidence=%.2f (%s)",
            task[:60], best_skill.name, confidence, best_reason,
        )
        return match

    def select_many(
        self,
        task: str,
        phase: str = "",
        risk: str = "medium",
        limit: int = 3,
        *,
        registry: SkillRegistry | None = None,
    ) -> list[SkillMatch]:
        """Return up to *limit* ranked skill matches (all above threshold)."""
        reg = registry if registry is not None else get_registry()
        skills = reg.all()
        if not skills:
            return []

        task_lower = task.lower()
        task_words = set(re.findall(r"\w+", task_lower))
        risk_lower = risk.lower()
        phase_lower = phase.lower()

        scored: list[tuple[float, Skill, str]] = []
        for skill in skills:
            score, reason_parts = self._score_skill(
                skill, task_lower, task_words, phase_lower, risk_lower
            )
            if score > 0:
                scored.append((score, skill, "; ".join(reason_parts)))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: list[SkillMatch] = []
        for raw_score, skill, reason in scored[:limit]:
            confidence = min(raw_score / 5.0, 1.0)
            if confidence >= self.CONFIDENCE_THRESHOLD:
                results.append(SkillMatch(
                    skill=skill,
                    skill_name=skill.name,
                    confidence=round(confidence, 3),
                    reason=reason,
                    phase=phase,
                    risk=risk,
                ))
        return results

    # --- Trace access ---

    def get_trace(self, limit: int = 20) -> list[SkillTraceEntry]:
        """Return recent skill selection trace entries, newest first."""
        entries = list(self._trace)
        entries.reverse()
        return entries[:limit]

    def clear_trace(self) -> None:
        self._trace.clear()

    # --- Internal ---

    def _score_skill(
        self,
        skill: Skill,
        task_lower: str,
        task_words: set[str],
        phase_lower: str,
        risk_lower: str,
    ) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []

        # 1. Trigger keyword match (highest weight: 3.0 for first hit).
        # Split the trigger field on whitespace/punctuation and check each token
        # individually so multi-keyword triggers like
        # "`/ralplan <task>` or "ralplan", "consensus plan"…" still match.
        # Placeholder tokens like <task> are excluded by stripping angle brackets in split.
        _TRIGGER_PLACEHOLDERS = {"task", "item", "name", "text", "here"}
        trigger_raw = skill.trigger.lower()
        _raw_tokens = [
            re.sub(r"[^a-z0-9\-]", "", tok)
            for tok in re.split(r'[\s,|"\'\`/<>]', trigger_raw)
        ]
        # Also expand hyphenated tokens (e.g. "security-review" → ["security", "review"])
        trigger_tokens: list[str] = []
        for tok in _raw_tokens:
            if len(tok) >= 3 and tok not in _TRIGGER_PLACEHOLDERS:
                trigger_tokens.append(tok)
            for part in tok.split("-"):
                if len(part) >= 4 and part not in _TRIGGER_PLACEHOLDERS and part not in trigger_tokens:
                    trigger_tokens.append(part)
        for tok in trigger_tokens:
            if tok in task_lower:
                score += 3.0
                reasons.append(f"trigger keyword '{tok}' matched")
                break  # count only once per skill

        # 2. Keyword overlap with skill name + description + trigger (weight: 0.6 each)
        skill_words = set(re.findall(
            r"\w+",
            f"{skill.name} {skill.description} {skill.trigger}".lower()
        ))
        # Exclude very short stop-words from overlap scoring
        overlap = {w for w in (task_words & skill_words) if len(w) >= 4}
        if overlap:
            overlap_score = len(overlap) * 0.6
            score += overlap_score
            reasons.append(f"keyword overlap {sorted(overlap)[:4]}")

        # 3. Phase affinity (weight: 1.5)
        if phase_lower:
            phase_hints = _PHASE_AFFINITY.get(phase_lower, [])
            if skill.name in phase_hints:
                score += 1.5
                reasons.append(f"phase '{phase_lower}' affinity")

        # 4. Risk adjustments
        if risk_lower in ("high", "critical"):
            if skill.name in _HIGH_RISK_BOOST:
                score += 1.0
                reasons.append(f"risk={risk_lower} boost")
            if skill.name in _HIGH_RISK_PENALTY:
                score -= 0.8
                reasons.append(f"risk={risk_lower} penalty")

        return score, reasons

    def _no_match(self, task: str, phase: str, risk: str, reason: str) -> SkillMatch:
        match = SkillMatch(
            skill=None,
            skill_name="",
            confidence=0.0,
            reason=reason,
            phase=phase,
            risk=risk,
        )
        self._record_trace(task, match)
        logger.debug("SkillSelector: no match — %s", reason)
        return match

    def _record_trace(self, task: str, match: SkillMatch) -> None:
        self._trace.append(SkillTraceEntry(
            timestamp=datetime.now(),
            task_snippet=task[:120],
            phase=match.phase,
            risk=match.risk,
            skill_name=match.skill_name,
            confidence=match.confidence,
            reason=match.reason,
        ))


# Module-level singleton
skill_selector = SkillSelector()
