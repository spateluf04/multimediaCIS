import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
KB_DIR = REPO_ROOT / "kb"

sys.path.insert(0, str(BACKEND_DIR))
