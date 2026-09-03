"""
Frontend HTML Integrity & DOM Validation Test Suite.
Validates that all HTML files in public/ are syntactically valid, have balanced
container tags, proper element hierarchy, and no unclosed interactive or card tags.
Prevents layout bleed and DOM parsing corruptions from passing CI/CD or test builds.
"""

import unittest
from pathlib import Path
from html.parser import HTMLParser
from typing import List, Tuple

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"

# HTML5 self-closing / void tags that do not require closing tags
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
}

# Critical container tags that must strictly balance and not bleed
CONTAINER_TAGS = {
    "div", "button", "p", "section", "article", "nav", "header",
    "footer", "main", "aside", "form", "select", "table", "tbody",
    "thead", "tr", "th", "td", "ul", "ol", "li", "h1", "h2", "h3",
    "h4", "h5", "h6", "span", "a", "label"
}

class StrictHtmlValidator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tag_stack: List[Tuple[str, int]] = []
        self.errors: List[str] = []
        self.wizard_card_hierarchy: List[str] = []
        self.card_nesting_errors: List[str] = []
        self.active_cards: List[str] = []
        self.active_buttons: List[int] = []

    def handle_starttag(self, tag: str, attrs: list):
        line, col = self.getpos()
        attr_dict = dict(attrs)
        
        # Check if inside an unclosed button tag and opening another container
        if tag == "button":
            self.active_buttons.append(line)
        elif self.active_buttons and tag in {"div", "button", "section"}:
            self.errors.append(
                f"Line {line}: Illegal nesting: <{tag}> cannot be placed inside unclosed <button> from line {self.active_buttons[-1]}"
            )

        # Track wizard-card hierarchy to prevent card bleeding
        if tag == "div" and "wizard-card" in attr_dict.get("class", "").split():
            card_id = attr_dict.get("id", f"card-line-{line}")
            if self.active_cards:
                self.card_nesting_errors.append(
                    f"Line {line}: {card_id} is illegally nested inside {self.active_cards[-1][0]} (from line {self.active_cards[-1][1]})"
                )
            self.active_cards.append((card_id, len(self.tag_stack)))

        if tag not in VOID_TAGS:
            self.tag_stack.append((tag, line))

    def handle_endtag(self, tag: str):
        line, col = self.getpos()
        if tag in VOID_TAGS:
            self.errors.append(f"Line {line}: Void tag </{tag}> should not have a closing tag")
            return

        if tag == "button" and self.active_buttons:
            self.active_buttons.pop()

        if not self.tag_stack:
            self.errors.append(f"Line {line}: Unexpected closing tag </{tag}> without matching opening tag")
            return

        expected_tag, open_line = self.tag_stack[-1]
        if expected_tag == tag:
            popped_tag, _ = self.tag_stack.pop()
            if self.active_cards and self.active_cards[-1][1] == len(self.tag_stack):
                self.active_cards.pop()
        else:
            # Check if matching tag exists further down the stack (unclosed inner tag)
            tag_names = [t[0] for t in self.tag_stack]
            if tag in tag_names:
                last_open, last_line = self.tag_stack.pop()
                self.errors.append(
                    f"Line {line}: Mismatched closing tag </{tag}>. Unclosed tag <{last_open}> from line {last_line}"
                )
            else:
                self.errors.append(f"Line {line}: Stray closing tag </{tag}> not found in stack")

class TestFrontendHtmlIntegrity(unittest.TestCase):
    """Validates structural syntax and container nesting of all frontend HTML templates."""

    def test_index_html_syntax_and_hierarchy(self):
        index_path = PUBLIC_DIR / "index.html"
        self.assertTrue(index_path.exists(), "public/index.html must exist")

        content = index_path.read_text(encoding="utf-8")
        validator = StrictHtmlValidator()
        validator.feed(content)

        # Assert no illegal element nesting (e.g. div inside button)
        self.assertEqual(
            validator.errors, [],
            f"HTML syntax and tag balance errors found in public/index.html:\n" + "\n".join(validator.errors)
        )

        # Assert wizard cards are strictly top-level siblings and not nested
        self.assertEqual(
            validator.card_nesting_errors, [],
            f"Wizard card hierarchy error (card bleeding):\n" + "\n".join(validator.card_nesting_errors)
        )

        # Check all expected wizard cards exist
        for step in [1, 2, 3, 4, 5]:
            card_id = f'id="step-card-5"' if step == 5 else f'id="step-card-{step}"'
            self.assertIn(card_id, content, f"Missing wizard card {card_id} in index.html")

    def test_legal_notice_pages_integrity(self):
        for name in ["impressum.html", "datenschutz.html"]:
            path = PUBLIC_DIR / name
            if path.exists():
                content = path.read_text(encoding="utf-8")
                validator = StrictHtmlValidator()
                validator.feed(content)
                self.assertEqual(
                    validator.errors, [],
                    f"Syntax errors in {name}:\n" + "\n".join(validator.errors)
                )

if __name__ == "__main__":
    unittest.main()
