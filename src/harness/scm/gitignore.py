""".gitignore template generation with dynamic LLM-based reasoning."""

import json
from pathlib import Path

DEFAULT_GITIGNORE = """# Python
__pycache__/
*.py[cod]
*.pyo
*.egg-info/
dist/
build/
*.egg
*.whl
.pytest_cache/
.coverage
coverage/
htmlcov/
.mypy_cache/
.ruff_cache/

# Virtual environment
.venv/
venv/
.env/
env/

# IDE & Editor
.vscode/
.idea/
*.swp
*.swo
*~
*.code-workspace
*.iml
.cache/
.project
.classpath
.settings/
*.sublime-*

# OS
.DS_Store
Thumbs.db
*.localized

# Logs
*.log
logs/

# Temp
tmp/
temp/
"""

TEMPLATE_EXTENSIONS = {
    "backend-service": [
        "# Backend service: ignore infra configs, secrets",
        "*.pem",
        "*.key",
        ".env.*",
        "docker-compose.override.yml",
    ],
    "data-pipeline": [
        "# Data pipeline: large data files, temp outputs",
        "data/raw/",
        "data/processed/",
        "*.parquet",
        "*.arrow",
        "*.csv.gz",
    ],
    "library": [
        "# Library: ignore build artefacts for downstream consumers",
        "*.so",
        "*.dylib",
        "*.dll",
    ],
}


def get_default_gitignore(template: str = "") -> str:
    """Return a .gitignore string for the given project template."""
    content = DEFAULT_GITIGNORE.strip()
    ext = TEMPLATE_EXTENSIONS.get(template, [])
    if ext:
        content += "\n\n" + "\n".join(ext)
    return content + "\n"


def write_gitignore(path: Path, template: str = "") -> None:
    """Write a .gitignore file at the given path."""
    content = get_default_gitignore(template)
    path.write_text(content)


def suggest_dynamic_additions(project_root: Path) -> list[str]:
    """Scan the project root for untracked files and suggest .gitignore entries.

    This is a stub for Phase 2+. Eventually calls an LLM to reason about
    what new file types should be ignored based on what's appearing in
    `git status --porcelain` output.
    
    For now, returns known patterns that are commonly missed.
    """
    suggestions = []
    
    # Check for common unignored patterns
    untracked_dirs = [p for p in project_root.iterdir() 
                      if p.is_dir() and not p.name.startswith(".")]
    
    for d in untracked_dirs:
        # Check for node_modules in non-Node projects (leftover from tooling)
        if (d / "node_modules").exists():
            suggestions.append("node_modules/")
    
    return suggestions
