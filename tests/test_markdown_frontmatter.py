import unittest

from app.utils.markdown import MarkdownFrontmatter


class TestMarkdownFrontmatter(unittest.TestCase):
    def test_no_frontmatter(self) -> None:
        source = "Hello\nWorld"
        parsed = MarkdownFrontmatter.from_scratch(source)

        self.assertEqual(parsed.frontmatter, {})
        self.assertEqual(parsed.body, "Hello\nWorld")
        self.assertFalse(parsed.has_frontmatter)

    def test_key_value_frontmatter(self) -> None:
        source = """\
---
name: code
description: Implement code changes
tools: read, write
---
Body line
"""
        parsed = MarkdownFrontmatter.from_scratch(source)

        self.assertEqual(
            parsed.frontmatter,
            {
                "name": "code",
                "description": "Implement code changes",
                "tools": "read, write",
            },
        )
        self.assertEqual(parsed.body, "Body line")
        self.assertTrue(parsed.has_frontmatter)

    def test_bare_frontmatter_line(self) -> None:
        source = """\
---
Just a description line
---
Body
"""
        parsed = MarkdownFrontmatter.from_scratch(source)

        self.assertEqual(parsed.frontmatter, {"description": "Just a description line"})
        self.assertEqual(parsed.body, "Body")
        self.assertTrue(parsed.has_frontmatter)

    def test_missing_frontmatter_closing(self) -> None:
        source = """\
---
description: Missing closing
Body continues
"""
        parsed = MarkdownFrontmatter.from_scratch(source)

        self.assertEqual(parsed.frontmatter, {})
        self.assertEqual(
            parsed.body, "---\ndescription: Missing closing\nBody continues"
        )
        self.assertFalse(parsed.has_frontmatter)

    def test_strips_body_whitespace(self) -> None:
        source = """\
---
description: Trim body
---

  Body with padding  

"""
        parsed = MarkdownFrontmatter.from_scratch(source)

        self.assertEqual(parsed.body, "Body with padding")
        self.assertTrue(parsed.has_frontmatter)

    def test_parse_list(self) -> None:
        pl = MarkdownFrontmatter.parse_list
        self.assertEqual(pl("read, write ,  "), ["read", "write"])
        self.assertEqual(pl(""), [])


if __name__ == "__main__":
    unittest.main()
