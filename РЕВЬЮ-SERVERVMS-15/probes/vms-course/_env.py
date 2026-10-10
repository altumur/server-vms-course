"""Общая обвязка проб 15-го ревью: путь к снимку курса, pinned W2C_COURSE_DIR, тихий лог."""
import logging
import os
import sys

COURSE = os.environ.get("COURSE_SOURCE_ROOT") or (sys.argv[1] if len(sys.argv) > 1 else os.getcwd())  # корень снимка курса (каталог с Source/)
SOURCE = os.path.join(COURSE, "Source")
os.environ.setdefault("W2C_COURSE_DIR", COURSE)
sys.path.insert(0, SOURCE)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
