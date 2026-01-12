from dataclasses import dataclass
from glob import glob
from pathlib import Path
from typing import Self

from app.schemas import ToolSchema
from app.tools.base_tool import Tool


def list_files_next_to_script(pattern: str = "*") -> list[Path]:
    script_dir = Path(__file__).resolve().parent
    return sorted(Path(p) for p in glob(str(script_dir / pattern)))


@dataclass
class Skill:
    name: str
    description: str | None
    content: str

    @classmethod
    def from_file(cls, f: Path) -> Self:
        name = f.name.rstrip(".md")
        content = f.read_text().strip()
        if not content.startswith("---"):
            return cls(name=name, content=content, description=None)

        lines = content.split("\n")
        description = lines[1]
        content = "\n".join(lines[2:])
        return cls(name=name, content=content, description=description)


skills_description = """\
Load a skill to get detailed instructions for a specific task. Skills provide specialized knowledge and step-by-step guidance. Use this when a task matches an available skill's description.
<available_skills>{skills}</available_skills>
"""


def get_skills() -> dict[str, Skill]:
    skills = {}
    for f in list_files_next_to_script("*.md"):
        skill = Skill.from_file(f)
        skills[skill.name] = skill
    return skills


skills = get_skills()


class SkillsTool(Tool):
    description = skills_description.format(
        skills="".join(
            [
                f"<skill><name>{skill.name}</name><description>{skill.description}</description></skill>"
                for skill in skills.values()
            ]
        )
    )
    args = {"skill_name": "string"}

    def make_schema(self, name: str) -> ToolSchema:
        return ToolSchema(
            name=name,
            description=self.description,
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
            return skills[skill_name].content
        except KeyError:
            return f"error: skill {skill_name} not found."
