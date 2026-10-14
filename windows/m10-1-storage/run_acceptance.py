"""Reproduce this window using the ordinary Source acceptance executor."""
from pathlib import Path
import subprocess
import sys
root = Path(__file__).resolve().parents[2]
output = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent/'acceptance')
sys.exit(subprocess.call([sys.executable, str(root/'Source/tests/storage_acceptance.py'), output]))
