"""Generates the CSS stylesheet for Pygments-highlighted code blocks.

Kept separate from the Jinja2 template so the color theme can be swapped
(e.g. a future "dark mode" PDF template) by changing one function call
instead of hand-maintaining a duplicate, easily-drifting stylesheet.
"""
from pygments.formatters import HtmlFormatter

# "friendly" is a light, high-contrast theme that prints legibly on paper —
# several of Pygments' built-in themes are tuned for dark editor
# backgrounds and look washed out on a white PDF page.
DEFAULT_PYGMENTS_STYLE = "friendly"


def get_pygments_css(style: str = DEFAULT_PYGMENTS_STYLE, css_class: str = "codehilite") -> str:
    """Return CSS rules that colorize the `.{css_class}` blocks MarkdownRenderer produces."""
    return HtmlFormatter(style=style).get_style_defs(f".{css_class}")
