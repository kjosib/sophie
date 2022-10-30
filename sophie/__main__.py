import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from sophie.front_end import parse_file, complain
from sophie.compiler import resolve_words
from sophie.preamble import static_root
from sophie.simple_evaluator import run_module
from sophie.syntax import Module

if len(sys.argv) == 2:
	module = parse_file(sys.argv[1])
	if isinstance(module, Module):
		issues = resolve_words(module, static_root)
		if issues:
			complain(issues)
		else:
			run_module(module)
	else:
		complain([module])
else:
	print("    py -m sophie program.sg")
	print("will attempt to parse and analyze the program.")

