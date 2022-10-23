"""
Main driver for Sophie langauge.

This will be done in phases:

1. to parse Sophie. This works on the happy path and a few error cases (not many) are also tested.
2. a simple-minded call-by-need evaluator. This also works, leaving out list comprehensions.
3. a type checker. Not started yet.
4. strictness propagation, with call-site strictness where indicated.
5. interfacing to more outputs than a print-out of the computed value, such as turtle graphics
6. contemplating inputs
7. a deeper consideration for explicit concurrency
8. emitting native or VM code
9. an ecosystem
"""
from pathlib import Path
from boozetools.parsing.interface import ParseError, SemanticError
from boozetools.support.symtab import NoSuchSymbol, SymbolAlreadyExists
from .front_end import sophie_parser
from .syntax import Module

def parse_file(pathname):
	"""Read file given by name; pass contents to next phase."""
	with open(pathname, "r") as fh:
		text = fh.read()
	return parse_text(text, pathname)

def parse_text(text:str, pathname:Path):
	""" Submit text to parser; submit the resulting tree to subsequent pass """
	try:
		return sophie_parser.parse(text, filename=pathname)
	except SemanticError as ex:
		sophie_parser.source.complain(ex.args[1].slice, ex.args[0])
	except NoSuchSymbol:
		pass
	except SymbolAlreadyExists:
		pass
	except ParseError:
		pass
