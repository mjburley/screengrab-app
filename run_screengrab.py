"""Top-level launcher used by PyInstaller so the package's relative imports
resolve correctly. Source-mode users should still prefer ``python -m
screengrab.main``."""
import sys

from screengrab.main import main

if __name__ == "__main__":
    sys.exit(main())
