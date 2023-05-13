"""
"""
import sys
from pathlib import Path
from typing import Union

from boozetools.macroparse.runtime import TypicalApplication, make_tables
from boozetools.scanning.engine import IterableScanner
from boozetools.parsing.interface import ParseError
from boozetools.support.failureprone import Issue
from boozetools.support.pretty import DOT
from . import syntax
from .diagnostics import Report

class SophieParseError(ParseError):
	pass

_tables = make_tables(Path(__file__).parent/"Sophie.md")
_parse_table = _tables['parser']

class SophieParser(TypicalApplication):
	RESERVED = frozenset(t for t in _parse_table["terminals"] if t.isupper() and t.isalpha())
	
	def scan_ignore(self, yy: IterableScanner): pass
	def scan_punctuation(self, yy: IterableScanner):
		punctuation = sys.intern(yy.match())
		yy.token(punctuation, yy.slice())
	def scan_integer(self, yy: IterableScanner): yy.token("integer", syntax.Literal(int(yy.match()), yy.slice()))
	def scan_real(self, yy: IterableScanner): yy.token("real", syntax.Literal(float(yy.match()), yy.slice()))
	def scan_short_string(self, yy: IterableScanner): yy.token("short_string", syntax.Literal(yy.match()[1:-1], yy.slice()))
	
	def scan_word(self, yy: IterableScanner):
		upper = yy.match().upper()
		if upper in self.RESERVED: yy.token(upper, yy.slice())
		else: yy.token("name", syntax.Nom(sys.intern(yy.match()), yy.slice()))
	
	def scan_relop(self, yy: IterableScanner, op:str):
		yy.token("relop", op)
	
	def parse_nothing(self): return None
	def parse_empty(self): return ()
	def parse_first(self, item): return [item]
	def parse_more(self, some, another):
		some.append(another)
		return some
	
	def default_parse(self, ctor, *args):
		return getattr(syntax, ctor)(*args)
		
	def unexpected_token(self, kind, semantic, pds):
		raise SophieParseError(self.stack_symbols(pds), kind, self.yy.slice())
	
	pass

sophie_parser = SophieParser(_tables)

def parse_file(path:Path, report:Report):
	"""Read file given by name; pass contents to next phase."""
	try:
		with open(path, "r") as fh:
			text = fh.read()
	except FileNotFoundError:
		report.file_error(path, "I see no file called " + str(path))
	except OSError:
		report.file_error(path, "Something went pear-shaped while trying to read " + str(path))
	else:
		return parse_text(text, path, report)

def parse_text(text:str, path:Path, report:Report) -> Union[syntax.Module, Issue]:
	""" Submit text to parser; submit the resulting tree to subsequent pass """
	assert isinstance(path, Path)
	try:
		module = sophie_parser.parse(text, filename=str(path))
		module.path = path
		return module
	except syntax.MismatchedBookendsError as ex:
		report.error("Checking Bookends", ex.args, "These names don't line up. Has part of a function been lost?")
	except ParseError as ex:
		stack_symbols, lookahead, where = ex.args
		hint = _best_hint(stack_symbols, lookahead)
		description = "Sophie is confused by this %r here.\n%s"%(lookahead, hint)
		report.error("Parsing", [where], description)

##########################
#
#  I've been meaning to improve parse error messages.
#  Code from here down represents progress in that direction.
#

_vocabulary = set(_parse_table['terminals']).union(_parse_table['nonterminals'])
ETC = "???"
assert ETC not in _vocabulary
_advice_tree = {t:{} for t in _parse_table['terminals']}
_advice_tree[ETC] = {}

def _hint(path, text):
	symbols = path.split()
	node = _advice_tree[symbols.pop()]
	for symbol in reversed(symbols):
		if symbol == ETC:
			node[ETC] = True
		else:
			assert symbol in _vocabulary, symbol
			if symbol not in node:
				node[symbol] = {}
			node = node[symbol]
	assert '' not in node, path
	node[''] = text

def _best_hint(stack_symbols, lookahead):
	"""
	What we have here tries to find a match between parse stack situations and hints.
	If it fails utterly, then it reads out the parser state so it's easy to add a corresponding hint.
	"""
	best = None
	nodes = [_advice_tree[ETC]]
	if lookahead in _advice_tree: nodes.append(_advice_tree[lookahead])
	for symbol in reversed(stack_symbols):
		subsequent = []
		for n in nodes:
			if symbol in n: subsequent.append(n[symbol])
			if ETC in n: subsequent.append(n)
		nodes = subsequent
		for n in nodes:
			if '' in n: best = n['']
	if best:
		return "Here's my best hint:\n\t"+best
	else:
		return "Guru Meditation:\n\t"+" ".join(stack_symbols + [DOT, lookahead])

# I suppose I could read the hints from a data file on demand.
# But for now, I'll just hard-code some.

_hint("TYPE : ??? name square_list(name) IS OPAQUE", "Opaque types cannot be made generic.")
_hint("( ??? expr ;", "I suspect a missing ')' closing parentheses.")
_hint("CASE WHEN ??? :", "CASE WHEN needs THEN")
_hint("CASE semicolon_list(when_clause) ELSE expr ; ???", "CASE expression is missing ESAC")

assert _best_hint("export_section import_section TYPE : name square_list(name) IS".split(), 'OPAQUE')

