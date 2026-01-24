import unittest

from app.utils.ui import BLUE, BOLD, CYAN, GREEN, ITALIC, RESET, YELLOW, TerminalUI


class TestRenderMarkdown(unittest.TestCase):
    def test_inline_markdown_examples(self) -> None:
        ui = TerminalUI()
        cases = [
            ("**bold**", f"{BOLD}bold{RESET}"),
            ("*italic*", f"{ITALIC}italic{RESET}"),
            ("_italic_", f"{ITALIC}italic{RESET}"),
            ("`code`", f"{YELLOW}code{RESET}"),
            (
                "Mix **bold** and `code`",
                f"Mix {BOLD}bold{RESET} and {YELLOW}code{RESET}",
            ),
        ]

        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(ui.render_markdown(source), expected)

    def test_heading_examples(self) -> None:
        ui = TerminalUI()
        cases = [
            ("# Title", f"{BOLD}{BLUE}Title{RESET}"),
            ("## Subtitle", f"{BOLD}{CYAN}Subtitle{RESET}"),
            ("### Section", f"{BOLD}{GREEN}Section{RESET}"),
        ]

        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(ui.render_markdown(source), expected)


if __name__ == "__main__":
    unittest.main()
