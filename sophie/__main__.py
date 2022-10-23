import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from sophie.compiler import parse_file
from sophie.simple_evaluator import run_module

if len(sys.argv) == 2:
	module = parse_file(sys.argv[1])
	if module:
		print(run_module(module))
else:
	print("    py -m sophie program.sg")
	print("will attempt to parse and analyze the program.")

