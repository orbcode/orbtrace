import sys
import pathlib
import os

ignore = [
	'__pycache__',
]

paths = [str(p) for p in pathlib.Path(__file__).parent.iterdir() if p.is_dir() and p not in ignore]

for p in paths:
	sys.path.insert(1, p)

os.environ['PYTHONPATH'] = ':'.join(paths)
