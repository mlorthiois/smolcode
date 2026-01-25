from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MarkdownFrontmatter:
    frontmatter: dict[str, str]
    body: str
    has_frontmatter: bool

    @staticmethod
    def parse_list(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @classmethod
    def from_file(cls, path: Path) -> "MarkdownFrontmatter":
        return cls.from_scratch(path.read_text())

    @classmethod
    def from_scratch(cls, markdown: str) -> "MarkdownFrontmatter":
        content = markdown.strip()
        if not content.startswith("---"):
            return cls(frontmatter={}, body=content, has_frontmatter=False)

        lines = content.split("\n")
        frontmatter_lines: list[str] = []
        end_frontmatter = None

        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_frontmatter = i
                break
            frontmatter_lines.append(line)

        if end_frontmatter is None:
            return cls(frontmatter={}, body=content, has_frontmatter=False)

        frontmatter = cls._parse_frontmatter_lines(frontmatter_lines)
        body = "\n".join(lines[end_frontmatter + 1 :]).strip()
        return cls(frontmatter=frontmatter, body=body, has_frontmatter=True)

    @staticmethod
    def _parse_frontmatter_lines(lines: list[str]) -> dict[str, str]:
        frontmatter: dict[str, str] = {}
        bare_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                frontmatter[key.strip()] = value.strip()
            else:
                bare_lines.append(stripped)

        if not frontmatter and bare_lines:
            frontmatter["description"] = bare_lines[0]

        return frontmatter
