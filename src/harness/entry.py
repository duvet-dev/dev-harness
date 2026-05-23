"""Entry point for PyInstaller single executable build.

This is the script that PyInstaller wraps into harness binary.
"""
import sys
from harness.cli import main

if __name__ == "__main__":
    sys.exit(main())
