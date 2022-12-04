"""
This is an interpreter for the Sophie programming language.

{0}

For example:

    py -m sophie program.sg

will run program.sg if possible, or else try to explain why not.

For more information, see:

Documentation: https://sophie.readthedocs.io/en/latest/
       GitHub: https://github.com/kjosib/sophie
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

parser = argparse.ArgumentParser(
	prog="py -m sophie",
	description="Interpreter for the Sophie programming langauge.",
)
parser.add_argument("program", help="try examples/turtle.sg for example.")
parser.add_argument('-n', "--no-preamble", action="store_true", help="Don't load the preamble.")
parser.add_argument('-x', "--experimental", action="store_true", help="Run the experimental pass.")

if len(sys.argv) > 1:
	args = parser.parse_args()
	
	from sophie.diagnostics import Report
	from sophie.front_end import parse_file, complain
	report = Report()
	module = parse_file(args.program, report)
	if not report.issues:
		from sophie.resolution import resolve_words
		if args.no_preamble:
			from sophie.primitive import root_namespace as root
		else:
			from sophie.preamble import static_root as root
		resolve_words(module, root, report)
	if not report.issues:
		from sophie.manifest import type_module
		type_module(module, report)
	if args.experimental and not report.issues:
		from sophie.experimental import Experiment
		Experiment(module, report.on_error("Experimental Pass"))
	if report.issues:
		complain(report)
	elif module.main:
		from sophie.simple_evaluator import run_module
		run_module(module)
	else:
		print("That module has no `begin:` section and thus is not a main program.", file=sys.stderr)
else:
	print(__doc__.strip().format(parser.format_usage()))

