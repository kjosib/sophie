"""
This is an interpreter for the Sophie programming language.

{0}

For example:

    sophie program.sg

will run program.sg if possible, or else try to explain why not.

    sophie -h

will explain all the arguments.

For more information, see:

Documentation: https://sophie.readthedocs.io/en/latest/
       GitHub: https://github.com/kjosib/sophie
"""
import sys, argparse
from pathlib import Path

EXPERIMENT = "to stop after name resolution"

sys.path.insert(0, str(Path(__file__).parent.parent))

parser = argparse.ArgumentParser(
	prog="sophie",
	description="Interpreter for the Sophie programming langauge.",
)
parser.add_argument("program", help="try examples/turtle.sg for example.")
parser.add_argument('-c', "--check", action="count", help="Check the program verbosely but do not actually execute the program.")
parser.add_argument('-t', "--translate", action="store_true", help="Translate the program into input for the VM.")
parser.add_argument('-x', "--experimental", action="store_true", help="Opt into experiment-mode, which is presently %s."%EXPERIMENT)

def run(args):
	from .diagnostics import Report, TooManyIssues
	from .resolution import RoadMap, Yuck
	report = Report(verbose=args.check)
	try:
		try: roadmap = RoadMap(Path.cwd() / args.program, report)
		except Yuck:
			assert report.sick()
			report.complain_to_console()
			return 1
		assert report.ok()
		if args.experimental: return
		from .static.check import TypeChecker
		TypeChecker(report).check_program(roadmap)
		if report.sick():
			report.complain_to_console()
			return 1
	except TooManyIssues:
		report.complain_to_console()
		print(" *"*35, file=sys.stderr)
		print("Giving up after a few issues. One crisis at a time, eh?", file=sys.stderr)
		return 1
	if args.check:
		print("Looks plausible to me.", file=sys.stderr)
	else:
		from .demand import analyze_demand
		analyze_demand(roadmap)
		if args.translate:
			from .intermediate import translate
			translate(roadmap)
		else:
			from .tree_walker.executive import run_program
			run_program(roadmap)

def main():
	if len(sys.argv) > 1:
		exit(run(parser.parse_args()))
	else:
		print(__doc__.strip().format(parser.format_usage()))

