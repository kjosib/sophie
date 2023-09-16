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
RESERVED = frozenset(t for t in _parse_table["terminals"] if t.isupper() and t.isalpha())

class SophieParser(TypicalApplication):
	
	def scan_ignore(self, yy: IterableScanner): pass

	@staticmethod
	def scan_punctuation(yy: IterableScanner):
		punctuation = sys.intern(yy.match())
		yy.token(punctuation, yy.slice())
	
	@staticmethod
	def scan_integer(yy: IterableScanner): yy.token("integer", syntax.Literal(int(yy.match()), yy.slice()))
	
	@staticmethod
	def scan_hexadecimal(yy: IterableScanner):
		yy.token("integer", syntax.Literal(int(yy.match()[1:], 16), yy.slice()))
	
	@staticmethod
	def scan_real(yy: IterableScanner): yy.token("real", syntax.Literal(float(yy.match()), yy.slice()))
	
	@staticmethod
	def scan_short_string(yy: IterableScanner): yy.token("short_string", syntax.Literal(yy.match()[1:-1], yy.slice()))
	
	@staticmethod
	def scan_word(yy: IterableScanner):
		upper = yy.match().upper()
		if upper in RESERVED: yy.token(upper, yy.slice())
		else: yy.token("name", syntax.Nom(sys.intern(yy.match()), yy.slice()))
	
	@staticmethod
	def scan_relop(yy: IterableScanner, op:str):
		yy.token("relop", op)
	
	@staticmethod
	def parse_nothing(): return None
	@staticmethod
	def parse_empty(): return ()
	@staticmethod
	def parse_first(item): return [item]
	@staticmethod
	def parse_more(some, another):
		some.append(another)
		return some
	
	@staticmethod
	def default_parse(ctor, *args):
		return getattr(syntax, ctor)(*args)
		
	def unexpected_token(self, kind, semantic, pds):
		raise SophieParseError(self.stack_symbols(pds), kind, self.yy.slice())
	
	pass

sophie_parser = SophieParser(_tables)

def parse_text(text:str, path:Path, report:Report) -> Union[syntax.Module, Issue]:
	""" Submit text to parser; submit the resulting tree to subsequent pass """
	assert isinstance(path, Path)
	try:
		module = sophie_parser.parse(text, filename=str(path))
		return module
	except syntax.MismatchedBookendsError as ex:
		report.error("Checking Bookends", ex.args, "These names don't line up. Has part of a function been lost?")
	except ParseError as ex:
		stack_symbols, lookahead, span = ex.args
		hint = _best_hint(stack_symbols, lookahead)
		report.generic_parse_error(path, lookahead, span, hint)

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
	def dig(where, what):
		if what not in where: where[what] = {}
		return where[what]
	symbols = path.split()
	node = dig(_advice_tree, symbols.pop())
	for symbol in reversed(symbols):
		if symbol == DOT:
			continue
		if symbol == ETC:
			node[ETC] = True
		else:
			assert symbol in _vocabulary, symbol
			node = dig(node, symbol)
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
		return "Here's my best guess:\n\t"+best
	else:
		return "Guru Meditation:\n\t"+" ".join(stack_symbols + [DOT, lookahead])

# I suppose I could read the hints from a data file on demand.
# But for now, I'll just hard-code some.

_hint("TYPE : ??? name square_list(name) IS ● OPAQUE", "Opaque types cannot be made generic.")
_hint("( ??? expr ● ;", "I suspect a missing ')' closing parentheses.")
_hint("CASE WHEN ??? ● :", "CASE WHEN needs THEN")
_hint("CASE semicolon_list(when_clause) ELSE expr ; ● ???", "CASE expression is missing ESAC")
_hint("annotation = expr ● name", "Probably missing a semicolon after the previous definition.")
_hint("BEGIN : semicolon_list(expr) expr ● <END>", "You need a semicolon after that last expression.")
_hint("expr ● \"", "Seems to be missing some sort of operator before the string that starts here.")
_hint("TYPE : ??? name ● =", "A type-name IS something, but a function = something.")
_hint("TYPE : ??? name type_parameters ● =", "A type-name IS something, but a function = something.")
_hint("CASE : semicolon_list(subtype) ● END", "Do you mean ESAC here?")
_hint("semicolon_list(alternative) ELSE ● ->", "This doesn't take an arrow. Just ELSE is enough.")
_hint("CASE semicolon_list(when_clause) ● ESAC", "CASE-WHEN needs an ELSE clause.")
_hint("ELSE expr ● ???", "Probably a missing semicolon just before here.")
_hint("expr ● ,", "Not sure, but might be some stray parentheses nearby.")
_hint("( ● )", """
	Gentle breezes formed
	emptiness parenthesized.
	The birds are singing.
""")
_hint("name formals : name ● (", """
	If you are trying to declare the type of this function,
		then you want [square brackets] here, not (parentheses).
	If you are giving the value of this function (by reference to another function),
		then the colon before this name needs to be an equals = sign.
""")
_hint("CASE subject hint OF ● ESAC", """
	Two roads diverged in a wood, and I --
	I got distracted, didn't I?
""")
_hint("name formals annotation = ● ;", """
	Sometimes the absence of value is the greatest value.
	You cannot lose what you do not possess.
	But this is a computer program.
""")
_hint("name formals : name ● ???", "It seems to cut off after perhaps a type-annotation?")

assert _best_hint("export_section import_section TYPE : name square_list(name) IS".split(), 'OPAQUE')

