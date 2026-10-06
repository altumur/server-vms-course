# b5 (course): what the Backoff constructor refuses. ADR-0033: jitter in (0,1]; the product's Backoff.Check also refuses
# base <= 0 and max < base (reconcile.go:31). Tree: course. Expected parity: every line REFUSED.
# Usage: python b5_backoff_constructor.py <course Source>
import sys; sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
from w2cplatform.reconcile import Backoff
for kw in ({"jitter": 0}, {"jitter": float("nan")}, {"jitter": 1.5}, {"base": 0}, {"base": -1}, {"base": 10, "max": 1}):
    try:
        b = Backoff(**kw); print(kw, "ACCEPTED delays", [round(b.delay(n, 0.5), 2) for n in (1, 2, 3)])
    except ValueError:
        print(kw, "REFUSED")
