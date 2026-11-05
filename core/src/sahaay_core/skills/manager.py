"""Reusable Skills Engine for Sahaay.

Discovers, parses, and provides reviewed SKILL.md methods to the planning model.
Skills teach the agent reusable operational methods, without bypassing permissions or the Action Gate.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Skill(BaseModel):
    """Authoritative representation of a reviewed operational skill."""

    name: str
    description: str
    version: str = "1.0.0"
    author: str = "Sahaay Core"
    allowedTools: List[str] = Field(default_factory=list)
    instructions: str = ""
    filePath: str = ""
    isEnabled: bool = True

    def to_prompt_text(self) -> str:
        tools_str = (
            ", ".join(self.allowedTools) if self.allowedTools else "all registered capabilities"
        )
        return (
            f"### Skill: {self.name} (v{self.version})\n"
            f"Description: {self.description}\n"
            f"Allowed Tools: {tools_str}\n"
            f"Method Instructions:\n{self.instructions.strip()}\n"
        )


class SkillsManager:
    """Manages skill discovery, parsing, and context injection."""

    def __init__(self, skills_dir: Optional[Path] = None) -> None:
        self.skills_dir = skills_dir or (
            Path(__file__).resolve().parent.parent.parent.parent / "skills"
        )
        self._skills: Dict[str, Skill] = {}
        self.load_skills()

    def load_skills(self) -> None:
        """Scan skills directory for .skill.md and SKILL.md files."""
        self._skills.clear()
        search_dirs = [self.skills_dir, Path.home() / ".sahaay" / "skills"]

        for d in search_dirs:
            if not d.exists() or not d.is_dir():
                continue
            for f in d.rglob("*.md"):
                if f.name.endswith(".skill.md") or f.name == "SKILL.md":
                    try:
                        skill = self._parse_skill_file(f)
                        if skill:
                            self._skills[skill.name.lower()] = skill
                    except Exception as ex:
                        logger.warning("Failed parsing skill file %s: %s", f, ex)

    def _parse_skill_file(self, file_path: Path) -> Optional[Skill]:
        """Parses YAML frontmatter and markdown body of a skill file."""
        text = file_path.read_text(encoding="utf-8")
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)

        name = file_path.stem.replace(".skill", "").replace("-", " ").title()
        description = "Operational skill method"
        version = "1.0.0"
        author = "Sahaay"
        allowed_tools: List[str] = []
        instructions = text

        if frontmatter_match:
            fm_text = frontmatter_match.group(1)
            instructions = frontmatter_match.group(2)
            for line in fm_text.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    k = key.strip().lower()
                    v = val.strip().strip('"').strip("'")
                    if k == "name":
                        name = v
                    elif k == "description":
                        description = v
                    elif k == "version":
                        version = v
                    elif k == "author":
                        author = v
                    elif k in ("tools", "allowed_tools", "allowedtools"):
                        allowed_tools = [t.strip() for t in v.strip("[]").split(",") if t.strip()]

        return Skill(
            name=name,
            description=description,
            version=version,
            author=author,
            allowedTools=allowed_tools,
            instructions=instructions.strip(),
            filePath=str(file_path),
            isEnabled=True,
        )

    def list_skills(self) -> List[Skill]:
        return list(self._skills.values())

    def get_skill(self, name: str) -> Optional[Skill]:
        return self._skills.get(name.lower())

    def get_relevant_skills(self, goal: str) -> List[Skill]:
        """Matches available skills to the user goal via keyword, stem, and domain relevance."""
        goal_lower = goal.lower()

        def _stem(w: str) -> str:
            w = re.sub(r"[^a-z0-9]", "", w)
            if w.endswith("ies"):
                return w[:-3]
            for suff in ("ing", "tion", "ment", "ed", "es", "s"):
                if len(w) > len(suff) + 3 and w.endswith(suff):
                    return w[: -len(suff)]
            return w

        goal_tokens = [_stem(w) for w in re.split(r"\W+", goal_lower) if len(w) >= 3]
        goal_raw_tokens = [w for w in re.split(r"\W+", goal_lower) if len(w) >= 3]

        matched = []
        for skill in self._skills.values():
            if not skill.isEnabled:
                continue
            skill_text = f"{skill.name} {skill.description} {' '.join(skill.allowedTools)}".lower()
            skill_tokens = set(re.split(r"\W+", skill_text))
            skill_stemmed = {_stem(w) for w in skill_tokens if len(w) >= 3}

            # Direct substring match
            direct_match = any(w in skill_text for w in goal_raw_tokens if len(w) >= 4)
            # Stemmed overlap
            stem_overlap = any(
                st in skill_stemmed
                or any(
                    st in sk or sk in st for sk in skill_stemmed if len(st) >= 4 and len(sk) >= 4
                )
                for st in goal_tokens
                if len(st) >= 4
            )

            # Domain specific semantic triggers
            domain_match = False
            if any(
                term in goal_lower
                for term in (
                    "report",
                    "doc",
                    "pdf",
                    "file",
                    "inconsist",
                    "audit",
                    "differ",
                    "contract",
                )
            ):
                if "document" in skill.name.lower() or "audit" in skill.name.lower():
                    domain_match = True
            if any(
                term in goal_lower
                for term in (
                    "data",
                    "stat",
                    "table",
                    "sheet",
                    "csv",
                    "excel",
                    "xlsx",
                    "math",
                    "sum",
                    "average",
                    "finance",
                    "financial",
                )
            ):
                if "data" in skill.name.lower() or "tabular" in skill.name.lower():
                    domain_match = True
            if any(
                term in goal_lower
                for term in (
                    "research",
                    "find",
                    "search",
                    "investigate",
                    "topic",
                    "web",
                    "summary",
                    "article",
                )
            ):
                if "research" in skill.name.lower():
                    domain_match = True
            if any(
                term in goal_lower
                for term in ("window", "app", "click", "screen", "type", "desktop", "ui", "button")
            ):
                if "desktop" in skill.name.lower() or "windows" in skill.name.lower():
                    domain_match = True

            if direct_match or stem_overlap or domain_match:
                matched.append(skill)
        return matched

    def format_skills_for_prompt(self, skills: List[Skill]) -> str:
        """Serializes relevant skills into planning prompt context."""
        if not skills:
            return ""
        skill_texts = [s.to_prompt_text() for s in skills]
        return "\n## OPERATIONAL SKILLS AND METHODS\n" + "\n---\n".join(skill_texts) + "\n"


skills_manager = SkillsManager()
