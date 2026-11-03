"""Change only the fixture observation budget, in an isolated child process."""
from pathlib import Path
import runpy
import sys

root, probe, output = map(Path, sys.argv[1:])
sys.path.insert(0, str(root / 'portable'))
import check
assert check.RECOVERY_GRACE == 300
assert check.RECOVERY_POLL == 5
check.RECOVERY_GRACE = -59  # unchanged fixture timeout=60; observation budget is one second
sys.argv = [str(probe), str(root), str(output)]
runpy.run_path(str(probe), run_name='__main__')
