"""
Template service for rendering email templates using Jinja2.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound, TemplateSyntaxError

from app.config import settings

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for rendering Jinja2 email templates."""

    def __init__(self):
        """Initialize Jinja2 environment with template directory."""
        self.template_dir = Path(settings.email_template_dir)
        self.env: Optional[Environment] = None
        self._initialize_environment()

    def _initialize_environment(self):
        """Initialize Jinja2 environment with template loader."""
        try:
            if not self.template_dir.exists():
                logger.warning(
                    f"Template directory does not exist: {self.template_dir}. "
                    "Creating directory..."
                )
                self.template_dir.mkdir(parents=True, exist_ok=True)

            self.env = Environment(
                loader=FileSystemLoader(str(self.template_dir)),
                autoescape=True,  # Auto-escape HTML for security
                trim_blocks=True,  # Remove first newline after block
                lstrip_blocks=True  # Strip leading spaces/tabs from start of line
            )
            logger.info(f"Template environment initialized with directory: {self.template_dir}")

        except Exception as e:
            logger.error(f"Failed to initialize template environment: {e}")
            self.env = None

    def render_template(
        self,
        template_name: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Render a Jinja2 template with the given context.

        Args:
            template_name: Name of the template file (e.g., 'individual_notification.html')
            context: Dictionary of variables to pass to the template

        Returns:
            Rendered template as a string

        Raises:
            TemplateNotFound: If the template file doesn't exist
            TemplateSyntaxError: If the template has syntax errors
            Exception: For other template rendering errors
        """
        if not self.env:
            raise RuntimeError("Template environment not initialized")

        try:
            template = self.env.get_template(template_name)
            rendered = template.render(**context)
            logger.info(f"Successfully rendered template: {template_name}")
            return rendered

        except TemplateNotFound as e:
            logger.error(f"Template not found: {template_name}")
            raise TemplateNotFound(f"Template '{template_name}' not found in {self.template_dir}")

        except TemplateSyntaxError as e:
            logger.error(f"Template syntax error in {template_name}: {e}")
            raise

        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            raise

    def render_string(
        self,
        template_string: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Render a template from a string instead of a file.

        Useful for inline templates or testing.

        Args:
            template_string: Template content as a string
            context: Dictionary of variables to pass to the template

        Returns:
            Rendered template as a string
        """
        try:
            template = Template(template_string, autoescape=True)
            rendered = template.render(**context)
            logger.debug("Successfully rendered template from string")
            return rendered

        except TemplateSyntaxError as e:
            logger.error(f"Template syntax error: {e}")
            raise

        except Exception as e:
            logger.error(f"Error rendering template string: {e}")
            raise

    def template_exists(self, template_name: str) -> bool:
        """
        Check if a template file exists.

        Args:
            template_name: Name of the template file

        Returns:
            True if template exists, False otherwise
        """
        template_path = self.template_dir / template_name
        return template_path.exists()

    def list_templates(self) -> list:
        """
        List all available template files.

        Returns:
            List of template filenames
        """
        if not self.template_dir.exists():
            return []

        return [
            f.name
            for f in self.template_dir.iterdir()
            if f.is_file() and f.suffix in ['.html', '.txt', '.j2']
        ]


# Create singleton instance
template_service = TemplateService()
