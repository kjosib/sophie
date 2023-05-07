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
import os, sys, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

parser = argparse.ArgumentParser(
	prog="py -m sophie",
	description="Interpreter for the Sophie programming langauge.",
)
parser.add_argument("program", help="try examples/turtle.sg for example.")
parser.add_argument('-c', "--check", action="store_true", help="Check the program verbosely but do not actually execute the program.")
# parser.add_argument('-p', "--no-preamble", action="store_true", help="Don't load the preamble.")
parser.add_argument('-x', "--experimental", action="store_true", help="Opt into experimental code, which is presently nothing.")

def run(args):
	# if args.no_preamble:
	
	from sophie.diagnostics import Report
	from sophie.modularity import Loader
	report = Report(verbose=args.check)
	loader = Loader(report, experimental=args.experimental)
	loader.load_program(Path.cwd(), args.program)
	if report.sick():
		report.complain_to_console()
		return 1
	elif args.check:
		print("Looks plausible to me.", file=sys.stderr)
	else:
		loader.run()
		
if len(sys.argv) > 1:
	exit(run(parser.parse_args()))
else:
	print(__doc__.strip().format(parser.format_usage()))

