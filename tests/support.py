"""Import the pure modules without running the Anki add-on entry point."""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("gamified_under_test")
package.__path__ = [str(ROOT)]
sys.modules.setdefault(package.__name__, package)
