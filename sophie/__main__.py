import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from sophie.front_end import parse_file, complain
from sophie.resolution import resolve_words
from sophie.preamble import static_root
from sophie.unification import infer_types
from sophie.simple_evaluator import run_module
from sophie.syntax import Module

if len(sys.argv) == 2:
	module = parse_file(sys.argv[1])
	if isinstance(module, Module):
		issues = resolve_words(module, static_root)
		if not issues:
			issues = infer_types(module)
		if issues:
			complain(issues)
		elif module.main:
			run_module(module)
		else:
			print("That module has no `begin:` section and thus is not a main program.", file=sys.stderr)
	else:
		complain([module])
else:
	print("    py -m sophie program.sg")
	print("will run program.sg if possible, or else try to explain why not.")

