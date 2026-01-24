from dataclasses import dataclass
from pathlib import Path
from typing import Self

from app.config import iter_config_files
from app.schemas import ToolSchema
from app.tool import Tool
from app.utils.markdown import MarkdownFrontmatter


@dataclass
class Skill:
    name: str
    description: str | None
    content: str

    @classmethod
    def from_file(cls, f: Path) -> Self:
        parsed = MarkdownFrontmatter.from_file(f)
        description = parsed.frontmatter.get("description")
        name = parsed.frontmatter.get("name", f.parent.name)
        return cls(name=name, content=parsed.body, description=description)


skills_description = """\
Load a skill to get detailed instructions for a specific task. Skills provide specialized knowledge and step-by-step guidance. Use this when a task matches an available skill's description.
<available_skills>{skills}</available_skills>
"""


class SkillsTool(Tool):
    description = skills_description
    args = {"skill_name": "string"}

    def __init__(self, skills: dict[str, Skill] | None = None) -> None:
        self._skills = skills

    @classmethod
    def compile(cls, **kwargs) -> "SkillsTool":
        return cls()

    def _load_skills(self) -> dict[str, Skill]:
        if self._skills is None:
            self._skills = {}
            for skill_file in iter_config_files("skills", "*/SKILL.md"):
                skill = Skill.from_file(skill_file)
                self._skills[skill.name] = skill
        return self._skills

    def _build_description(self) -> str:
        skills = self._load_skills()
        return skills_description.format(
            skills="".join(
                [
                    f"<skill><name>{skill.name}</name><description>{skill.description}</description></skill>"
                    for skill in skills.values()
                ]
            )
        )

    def make_schema(self, name: str) -> ToolSchema:
        skills = self._load_skills()
        return ToolSchema(
            name=name,
            description=self._build_description(),
            parameters={
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Exact identifier of the skill to load. Must be one of the supported skills.",
                        "enum": list(skills.keys()),
                    }
                },
                "required": ["skill_name"],
            },
        )

    def __call__(self, args) -> str:
        try:
            skill_name = args["skill_name"]
        except KeyError:
            return "error: missing skill_name."

        skills = self._load_skills()

        try:
            return skills[skill_name].content
        except KeyError:
            return f"error: skill {skill_name} not found."
