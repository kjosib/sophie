import sys
from pathlib import Path
from pprint import pprint

sys.path.insert(0, str(Path(__file__).parent.parent))
from sophie.compiler import main


if len(sys.argv) == 2:
	pprint(main(sys.argv[1]), width=200)
else:
	print("    py -m sophie program.sg")
	print("will attempt to parse and analyze the program.")

