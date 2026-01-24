from dataclasses import dataclass, field
from pathlib import Path
from typing import Self, TypedDict

from app.tool import Tool
from app.utils.config import iter_config_files
from app.utils.markdown import MarkdownFrontmatter
from app.utils.schemas import ToolSchema


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


class Args(TypedDict):
    skill_name: str


@dataclass
class SkillsTool(Tool[Args]):
    skills: dict[str, Skill] = field(default_factory=dict)
    description = skills_description
    args_type = Args

    def __post_init__(self):
        for skill_file in iter_config_files("skills", "*/SKILL.md"):
            skill = Skill.from_file(skill_file)
            self.skills[skill.name] = skill

    def _build_description(self) -> str:
        skills = self.skills
        return skills_description.format(
            skills="".join(
                [
                    f"<skill><name>{skill.name}</name><description>{skill.description}</description></skill>"
                    for skill in skills.values()
                ]
            )
        )

    def make_schema(self, name: str) -> ToolSchema:
        skills = self.skills
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

    def __call__(self, args: Args) -> str:
        try:
            skill_name = args["skill_name"]
        except KeyError:
            return "error: missing skill_name."

        try:
            return self.skills[skill_name].content
        except KeyError:
            return f"error: skill {skill_name} not found."
