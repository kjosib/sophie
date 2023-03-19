"""
This is an interpreter for the Sophie programming language.

{0}

For example:

    py -m sophie program.sg

will run program.sg if possible, or else try to explain why not.

    py -m sophie -h

will explain all the arguments.

For more information, see:

Documentation: https://sophie.readthedocs.io/en/latest/
       GitHub: https://github.com/kjosib/sophie
"""
import os
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

parser = argparse.ArgumentParser(
	prog="py -m sophie",
	description="Interpreter for the Sophie programming langauge.",
)
parser.add_argument("program", help="try examples/turtle.sg for example.")
parser.add_argument('-c', "--check", action="store_true", help="Check syntax and types verbosely; Don't actually run the program.")
parser.add_argument('-n', "--no-preamble", action="store_true", help="Don't load the preamble.")
parser.add_argument('-x', "--experimental", action="store_true", help="Opt into whatever experiment is current, if any.")

def run(args):
	if args.no_preamble:
		from sophie.primitive import root_namespace as root
	else:
		from sophie.preamble import static_root as root
	
	from sophie.diagnostics import Report
	from sophie.modularity import Loader
	report = Report()
	loader = Loader(root, report, args.check)
	try:
		module = loader.need_module(os.getcwd(), args.program)
	except FileNotFoundError:
		print("There's no such file.", file=sys.stderr)
		return 1
	if report.issues:
		report.complain_to_console()
		return 1
	elif args.check:
		pass
	elif module.main:
		from sophie.simple_evaluator import run_program
		run_program(loader.module_sequence)
	else:
		print("That module has no `begin:` section and thus is not a main program.", file=sys.stderr)
		return 1
		
if len(sys.argv) > 1:
	exit(run(parser.parse_args()))
else:
	print(__doc__.strip().format(parser.format_usage()))

