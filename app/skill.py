from dataclasses import dataclass
from pathlib import Path
from typing import Self

from app.registry import Registry
from app.schemas import ToolSchema
from app.core.tool import Tool
from app.utils.markdown import MarkdownFrontmatter


def list_skill_files() -> list[Path]:
    skills_dir = Path(__file__).resolve().parent / "skills"
    return sorted(skills_dir.glob("*/SKILL.md"))


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

    def _build_description(self) -> str:
        skills = Registry.skills()
        return skills_description.format(
            skills="".join(
                [
                    f"<skill><name>{skill.name}</name><description>{skill.description}</description></skill>"
                    for skill in skills.values()
                ]
            )
        )

    def make_schema(self, name: str) -> ToolSchema:
        skills = Registry.skills()
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

        skills = Registry.skills()

        try:
            return skills[skill_name].content
        except KeyError:
            return f"error: skill {skill_name} not found."
