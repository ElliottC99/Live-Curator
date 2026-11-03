"""Template engine for rendering responsive HTML and plain-text monthly digests."""

import logging
from pathlib import Path
from typing import Optional, Tuple
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.core.models import MonthlyDigest
from src.__version__ import __version__

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


class TemplateEngine:
    """Renders MonthlyDigest objects into HTML and Plain-Text representations."""

    def __init__(self, template_dir: Optional[Path] = None):
        self.template_dir = template_dir or DEFAULT_TEMPLATE_DIR
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_html(self, digest: MonthlyDigest) -> str:
        """Render the HTML digest email."""
        template = self.env.get_template("digest.html")
        return template.render(digest=digest, version=__version__)

    def render_text(self, digest: MonthlyDigest) -> str:
        """Render the plain-text fallback digest email."""
        template = self.env.get_template("digest.txt")
        return template.render(digest=digest, version=__version__)

    def render_all(self, digest: MonthlyDigest) -> Tuple[str, str]:
        """Return (html_content, text_content)."""
        return self.render_html(digest), self.render_text(digest)
