import sys
from pathlib import Path


# The application package lives directly under backend/. Add that directory
# when pytest is launched from the repository root.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
