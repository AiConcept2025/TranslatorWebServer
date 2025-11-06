"""
Unit tests for template service.
"""

import pytest
from pathlib import Path
from jinja2 import TemplateNotFound, TemplateSyntaxError

from app.services.template_service import TemplateService, template_service


class TestTemplateService:
    """Test suite for TemplateService."""

    def test_template_service_initialization(self):
        """Test that template service initializes correctly."""
        service = TemplateService()
        assert service.env is not None
        assert service.template_dir.exists()

    def test_render_string_simple(self):
        """Test rendering a simple template string."""
        template_str = "Hello {{ name }}!"
        context = {"name": "World"}

        result = template_service.render_string(template_str, context)

        assert result == "Hello World!"

    def test_render_string_with_loop(self):
        """Test rendering template with loop."""
        template_str = """
        {% for item in items %}
        - {{ item }}
        {% endfor %}
        """
        context = {"items": ["apple", "banana", "cherry"]}

        result = template_service.render_string(template_str, context)

        assert "apple" in result
        assert "banana" in result
        assert "cherry" in result

    def test_render_string_with_conditional(self):
        """Test rendering template with conditional."""
        template_str = """
        {% if is_admin %}
        Welcome, Admin!
        {% else %}
        Welcome, User!
        {% endif %}
        """

        # Test admin case
        result_admin = template_service.render_string(template_str, {"is_admin": True})
        assert "Welcome, Admin!" in result_admin
        assert "Welcome, User!" not in result_admin

        # Test user case
        result_user = template_service.render_string(template_str, {"is_admin": False})
        assert "Welcome, User!" in result_user
        assert "Welcome, Admin!" not in result_user

    def test_render_string_html_escaping(self):
        """Test that HTML is properly escaped for security."""
        template_str = "<p>{{ content }}</p>"
        context = {"content": "<script>alert('XSS')</script>"}

        result = template_service.render_string(template_str, context)

        # HTML should be escaped
        assert "<script>" not in result
        assert "&lt;script&gt;" in result or "&#" in result

    def test_render_string_syntax_error(self):
        """Test handling of template syntax errors."""
        template_str = "{% for item in items %} {{ item }} {# Missing endfor #}"
        context = {"items": ["test"]}

        with pytest.raises(TemplateSyntaxError):
            template_service.render_string(template_str, context)

    def test_template_exists(self):
        """Test checking if template file exists."""
        # Check existing template
        exists = template_service.template_exists("individual_notification.html")
        assert exists is True

        # Check non-existing template
        exists = template_service.template_exists("nonexistent_template.html")
        assert exists is False

    def test_list_templates(self):
        """Test listing available templates."""
        templates = template_service.list_templates()

        assert isinstance(templates, list)
        # Should contain our email templates
        assert "individual_notification.html" in templates
        assert "individual_notification.txt" in templates
        assert "corporate_notification.html" in templates
        assert "corporate_notification.txt" in templates

    def test_render_template_individual_html(self):
        """Test rendering individual notification HTML template."""
        context = {
            "user_name": "John Doe",
            "company_name": "Ind",
            "documents": [
                {
                    "document_name": "test.pdf",
                    "original_url": "https://example.com/original",
                    "translated_url": "https://example.com/translated"
                }
            ],
            "translation_service_company": "Iris Solutions"
        }

        result = template_service.render_template("individual_notification.html", context)

        assert "John Doe" in result
        assert "test.pdf" in result
        assert "https://example.com/original" in result
        assert "https://example.com/translated" in result
        assert "Iris Solutions" in result

    def test_render_template_individual_txt(self):
        """Test rendering individual notification text template."""
        context = {
            "user_name": "Jane Smith",
            "company_name": "Ind",
            "documents": [
                {
                    "document_name": "document.docx",
                    "original_url": "https://drive.google.com/original",
                    "translated_url": "https://drive.google.com/translated"
                }
            ],
            "translation_service_company": "Iris Solutions"
        }

        result = template_service.render_template("individual_notification.txt", context)

        assert "Jane Smith" in result
        assert "document.docx" in result
        assert "https://drive.google.com/original" in result
        assert "https://drive.google.com/translated" in result

    def test_render_template_corporate_html(self):
        """Test rendering corporate notification HTML template."""
        context = {
            "user_name": "Alice Johnson",
            "company_name": "Acme Corp",
            "documents": [
                {
                    "document_name": "report.xlsx",
                    "original_url": "https://example.com/original",
                    "translated_url": "https://example.com/translated"
                }
            ],
            "translation_service_company": "Iris Solutions"
        }

        result = template_service.render_template("corporate_notification.html", context)

        assert "Alice Johnson" in result
        assert "Acme Corp" in result
        assert "report.xlsx" in result
        assert "Iris Solutions" in result

    def test_render_template_corporate_txt(self):
        """Test rendering corporate notification text template."""
        context = {
            "user_name": "Bob Williams",
            "company_name": "Tech Inc",
            "documents": [
                {
                    "document_name": "presentation.pptx",
                    "original_url": "https://example.com/original",
                    "translated_url": "https://example.com/translated"
                }
            ],
            "translation_service_company": "Iris Solutions"
        }

        result = template_service.render_template("corporate_notification.txt", context)

        assert "Bob Williams" in result
        assert "Tech Inc" in result
        assert "presentation.pptx" in result

    def test_render_template_multiple_documents(self):
        """Test rendering template with multiple documents."""
        context = {
            "user_name": "Test User",
            "company_name": "Ind",
            "documents": [
                {
                    "document_name": "file1.pdf",
                    "original_url": "https://example.com/file1",
                    "translated_url": "https://example.com/file1_trans"
                },
                {
                    "document_name": "file2.docx",
                    "original_url": "https://example.com/file2",
                    "translated_url": "https://example.com/file2_trans"
                },
                {
                    "document_name": "file3.xlsx",
                    "original_url": "https://example.com/file3",
                    "translated_url": "https://example.com/file3_trans"
                }
            ],
            "translation_service_company": "Iris Solutions"
        }

        result = template_service.render_template("individual_notification.html", context)

        # All documents should be present
        assert "file1.pdf" in result
        assert "file2.docx" in result
        assert "file3.xlsx" in result

        # All URLs should be present
        assert "https://example.com/file1" in result
        assert "https://example.com/file2_trans" in result
        assert "https://example.com/file3" in result

    def test_render_template_not_found(self):
        """Test error handling for missing template."""
        context = {"test": "data"}

        with pytest.raises(TemplateNotFound):
            template_service.render_template("nonexistent_template.html", context)

    def test_render_template_special_characters(self):
        """Test rendering with special characters in data."""
        context = {
            "user_name": "François Müller",
            "company_name": "Café René",
            "documents": [
                {
                    "document_name": "données_spéciales.pdf",
                    "original_url": "https://example.com/original?param=value&foo=bar",
                    "translated_url": "https://example.com/translated"
                }
            ],
            "translation_service_company": "Iris Solutions"
        }

        # Should not raise an exception
        result = template_service.render_template("individual_notification.html", context)

        assert "François Müller" in result
        assert "Café René" in result
        assert "données_spéciales.pdf" in result
