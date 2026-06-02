"""Tests for harness.docs.templates — template listing, loading, rendering."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from harness.docs.templates import (
    list_templates,
    load_template,
    render_template,
    _render_simple_template,
    _parse_for_tag,
    _find_endfor,
    _replace_vars,
    _replace_dotted_vars,
)


class TestListTemplates:
    """Tests for list_templates()."""

    def test_empty_when_no_templates_dir(self):
        with patch("harness.docs.templates._TEMPLATES_DIR", Path("/nonexistent")):
            templates = list_templates()
            assert templates == []

    def test_returns_names_when_templates_exist(self, tmp_path):
        (tmp_path / "README.md").write_text("# {{ project_name }}")
        (tmp_path / "CONTRIBUTING.md").write_text("# How to contribute")
        with patch("harness.docs.templates._TEMPLATES_DIR", tmp_path):
            templates = list_templates()
            assert "README" in templates
            assert "CONTRIBUTING" in templates


class TestLoadTemplate:
    """Tests for load_template()."""

    def test_loads_template_content(self, tmp_path):
        (tmp_path / "README.md").write_text("# {{ project_name }}")
        with patch("harness.docs.templates._TEMPLATES_DIR", tmp_path):
            content = load_template("README")
            assert content == "# {{ project_name }}"

    def test_raises_on_missing(self):
        with pytest.raises(FileNotFoundError):
            load_template("__nonexistent_template__")


class TestReplaceVars:
    """Tests for _replace_vars()."""

    def test_simple_replacement(self):
        result = _replace_vars("Hello {{ name }}!", {"name": "World"})
        assert result == "Hello World!"

    def test_unknown_var_left_as_is(self):
        result = _replace_vars("{{ unknown }}", {"name": "value"})
        assert result == "{{ unknown }}"

    def test_multiple_replacements(self):
        result = _replace_vars(
            "{{ a }} and {{ b }}",
            {"a": "foo", "b": "bar"},
        )
        assert result == "foo and bar"

    def test_no_placeholders(self):
        result = _replace_vars("plain text", {"x": "y"})
        assert result == "plain text"


class TestReplaceDottedVars:
    """Tests for _replace_dotted_vars()."""

    def test_simple_dotted_var(self):
        result = _replace_dotted_vars(
            "{{ item.name }}",
            {"name": "Alice"},
        )
        assert result == "Alice"

    def test_unknown_key_left_as_is(self):
        result = _replace_dotted_vars(
            "{{ item.unknown }}",
            {"name": "Alice"},
        )
        assert result == "{{ item.unknown }}"

    def test_not_a_dict_no_replacement(self):
        result = _replace_dotted_vars("{{ item.name }}", "string")
        assert result == "{{ item.name }}"

    def test_no_dotted_placeholder(self):
        result = _replace_dotted_vars(
            "{{ name }} has no dot",
            {"name": "Alice"},
        )
        assert result == "{{ name }} has no dot"


class TestParseForTag:
    """Tests for _parse_for_tag()."""

    def test_simple_for(self):
        result = _parse_for_tag("{% for module in modules %}")
        assert result == ("module", "modules")

    def test_with_whitespace(self):
        result = _parse_for_tag("  {% for item in items %}  ")
        assert result == ("item", "items")

    def test_not_a_for_tag(self):
        assert _parse_for_tag("{{ variable }}") is None

    def test_malformed(self):
        assert _parse_for_tag("{% for x %") is None


class TestFindEndfor:
    """Tests for _find_endfor()."""

    def test_finds_endfor(self):
        lines = ["a", "{% endfor %}", "c"]
        assert _find_endfor(lines, 0) == 1

    def test_no_endfor(self):
        lines = ["a", "b", "c"]
        assert _find_endfor(lines, 0) is None

    def test_start_past_end(self):
        assert _find_endfor(["{% endfor %}"], 5) is None

    def test_many_lines(self):
        lines = ["{% for x in xs %}", "body1", "body2", "{% endfor %}", "after"]
        assert _find_endfor(lines, 1) == 3

    def test_whitespace_variations(self):
        lines = ["  {% endfor %}  ", "tail"]
        assert _find_endfor(lines, 0) == 0


class TestRenderSimpleTemplate:
    """Tests for _render_simple_template()."""

    def test_static_template(self):
        result = _render_simple_template("Hello World!", {})
        assert result == "Hello World!"

    def test_variable_substitution(self):
        result = _render_simple_template("Hello {{ name }}!", {"name": "World"})
        assert result == "Hello World!"

    def test_for_loop(self):
        template = "{% for item in items %}\n- {{ item }}\n{% endfor %}"
        result = _render_simple_template(template, {"items": ["a", "b", "c"]})
        lines = [l for l in result.split("\n") if l.strip()]
        assert "- a" in lines
        assert "- b" in lines
        assert "- c" in lines

    def test_for_loop_with_dict(self):
        template = "{% for m in modules %}\n{{ m.name }} - {{ m.version }}\n{% endfor %}"
        result = _render_simple_template(template, {
            "modules": [
                {"name": "foo", "version": "1.0"},
                {"name": "bar", "version": "2.0"},
            ],
        })
        assert "foo - 1.0" in result
        assert "bar - 2.0" in result

    def test_mixed_vars_and_for(self):
        template = "# {{ title }}\n{% for x in items %}\n- {{ x }}\n{% endfor %}"
        result = _render_simple_template(template, {
            "title": "Stuff",
            "items": ["one", "two"],
        })
        assert "# Stuff" in result
        assert "- one" in result
        assert "- two" in result

    def test_for_loop_without_endfor(self):
        """For loop without matching {% endfor %} is output as-is."""
        template = "{% for x in items %}\n- {{ x }}"
        result = _render_simple_template(template, {"items": ["a"]})
        assert "{% for x in items %}" in result

    def test_empty_for_loop(self):
        template = "{% for x in empty %}\n- {{ x }}\n{% endfor %}"
        result = _render_simple_template(template, {"empty": []})
        assert result.strip() == ""

    def test_for_loop_context_vars(self):
        """Non-dotted {{ }} references within a for loop pull from context."""
        template = "{% for x in items %}\n{{ greeting }} {{ x }}\n{% endfor %}"
        result = _render_simple_template(template, {
            "items": ["Alice", "Bob"],
            "greeting": "Hello",
        })
        assert "Hello Alice" in result
        assert "Hello Bob" in result


class TestRenderTemplate:
    """Integration tests for render_template()."""

    def test_render_with_variables(self, tmp_path):
        (tmp_path / "README.md").write_text("# {{ project_name }}\n\nDescription: {{ description }}")
        with patch("harness.docs.templates._TEMPLATES_DIR", tmp_path):
            result = render_template("README", {"project_name": "MyApp", "description": "Awesome"})
            assert "# MyApp" in result
            assert "Description: Awesome" in result

    def test_render_with_for_loop(self, tmp_path):
        (tmp_path / "CONTRIBUTING.md").write_text(
            "{% for item in items %}\n- {{ item }}\n{% endfor %}"
        )
        with patch("harness.docs.templates._TEMPLATES_DIR", tmp_path):
            result = render_template("CONTRIBUTING", {"items": ["a", "b"]})
            assert "- a" in result
            assert "- b" in result

class TestReplaceDottedVarsNumeric:
    """Tests for _replace_dotted_vars with non-string values."""

    def test_int_value_replaced(self):
        result = _replace_dotted_vars("{{ item.count }}", {"count": 42})
        assert result == "42"

    def test_float_value_replaced(self):
        result = _replace_dotted_vars("{{ item.ratio }}", {"ratio": 3.14})
        assert result == "3.14"

    def test_bool_value_not_replaced(self):
        """Booleans go through the str() path."""
        result = _replace_dotted_vars("{{ item.flag }}", {"flag": True})
        assert result == "True"
