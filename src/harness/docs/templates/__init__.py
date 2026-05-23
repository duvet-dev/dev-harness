"""Template rendering for generate-docs.

Provides simple string-template rendering for markdown templates.
Uses basic Python string formatting (not Jinja) to avoid external
dependencies.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


_TEMPLATES_DIR = Path(__file__).parent


def list_templates() -> list[str]:
    """List available template names (without extension)."""
    templates = []
    if _TEMPLATES_DIR.is_dir():
        for f in sorted(_TEMPLATES_DIR.iterdir()):
            if f.suffix == ".md":
                templates.append(f.stem)
    return templates


def load_template(name: str) -> str:
    """Load a template file by name.

    Args:
        name: Template name (e.g. "README", "CONTRIBUTING").

    Returns:
        The template content as a string.

    Raises:
        FileNotFoundError: If the template doesn't exist.
    """
    path = _TEMPLATES_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Template '{name}' not found at {path}")
    return path.read_text()


def render_template(
    name: str,
    context: dict,
) -> str:
    """Render a template with the given context.

    Uses simple Python format-string templating. Variable placeholders
    use ``{{ variable_name }}`` syntax.

    Args:
        name: Template name (e.g. "README", "CONTRIBUTING").
        context: Dict of template variables.

    Returns:
        The rendered template string.
    """
    template = load_template(name)

    # Handle Jinja-like for-loops: {% for x in list %}...{% endfor %}
    rendered = _render_simple_template(template, context)
    return rendered


def _render_simple_template(template: str, context: dict) -> str:
    """Basic template renderer supporting ``{{ var }}`` and ``{% for %}``.

    This is deliberately simple to avoid Jinja2 dependency.
    """
    lines = template.split("\n")
    output: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Handle {% for x in list %}
        for_match = _parse_for_tag(line)
        if for_match:
            var_name, list_name = for_match
            items = context.get(list_name, [])
            # Find endfor
            end_idx = _find_endfor(lines, i + 1)
            if end_idx is None:
                output.append(line)
                i += 1
                continue

            body_lines = lines[i + 1 : end_idx]
            for item in items:
                for body_line in body_lines:
                    # Replace dotted variables like {{ module.name }}
                    if isinstance(item, dict):
                        body_line = _replace_dotted_vars(
                            body_line, item
                        )
                    # Replace simple variables like {{ var_name }}
                    body_line = body_line.replace(
                        f"{{{{ {var_name} }}}}", str(item)
                    )
                    # Handle other {{ }} replacements from context
                    body_line = _replace_vars(body_line, context)
                    output.append(body_line)

            i = end_idx + 1
            continue

        # Handle {% endfor %} on its own line (skip)
        if line.strip().startswith("{% endfor %}"):
            i += 1
            continue

        # Replace {{ var }} placeholders
        line = _replace_vars(line, context)
        output.append(line)
        i += 1

    return "\n".join(output)


def _parse_for_tag(line: str) -> tuple[str, str] | None:
    """Parse a ``{% for x in list %}`` tag."""
    import re

    m = re.match(r"\s*\{\%\s*for\s+(\w+)\s+in\s+(\w+)\s*\%\}", line)
    if m:
        return m.group(1), m.group(2)
    return None


def _find_endfor(lines: list[str], start: int) -> int | None:
    """Find the matching {% endfor %} tag."""
    for i in range(start, len(lines)):
        if lines[i].strip().startswith("{% endfor %}"):
            return i
    return None


def _replace_vars(line: str, context: dict) -> str:
    """Replace ``{{ var_name }}`` placeholders with context values."""
    import re

    def replacer(m):
        var_name = m.group(1).strip()
        val = context.get(var_name, m.group(0))
        return str(val)

    return re.sub(r"\{{2}\s*([\w_]+)\s*\}{2}", replacer, line)


def _replace_dotted_vars(line: str, item: dict) -> str:
    """Replace ``{{ item.key }}`` placeholders with values from a dict."""
    import re

    def replacer(m):
        full = m.group(1).strip()
        parts = full.split(".", 1)
        if len(parts) == 2 and isinstance(item, dict):
            val = item.get(parts[1], m.group(0))
            if isinstance(val, str):
                return val
            if isinstance(val, (int, float)):
                return str(val)
        return m.group(0)

    return re.sub(r"\{{2}\s*([\w.]+)\s*\}{2}", replacer, line)



