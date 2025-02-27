import sys
from pathlib import Path
from typing import Union

from boozetools.macroparse.runtime import TypicalApplication, make_tables
from boozetools.macroparse.expansion import CompactHFA
from boozetools.scanning.engine import IterableScanner
from boozetools.parsing.interface import UnexpectedTokenError, UnexpectedEndOfTextError
from boozetools.support.failureprone import Issue
from boozetools.support.pretty import DOT
from . import syntax
from .location import reset_location_index, start_segment, insert_token
from .diagnostics import Report

_tables = make_tables(Path(__file__).parent/"Sophie.md")
_parse_table = _tables['parser']
RESERVED = frozenset(t for t in _parse_table["terminals"] if t.isupper() and t.isalpha())

class SophieParser(TypicalApplication):

	def unexpected_token(self, kind, semantic, pds):
		raise UnexpectedTokenError(kind, semantic, pds)
	def unexpected_eof(self, pds):
		raise UnexpectedEndOfTextError(pds)

	def scan_ignore(self, yy: IterableScanner): pass

	@staticmethod
	def scan_punctuation(yy: IterableScanner):
		punctuation = sys.intern(yy.match())
		nom = syntax.Nom(punctuation, insert_token(yy.slice()))
		yy.token(punctuation, nom)
	
	@staticmethod
	def scan_integer(yy: IterableScanner): yy.token("integer", syntax.Literal(int(yy.match()), insert_token(yy.slice())))
	
	@staticmethod
	def scan_hexadecimal(yy: IterableScanner):
		yy.token("integer", syntax.Literal(int(yy.match()[1:], 16), insert_token(yy.slice())))
	
	@staticmethod
	def scan_real(yy: IterableScanner): yy.token("real", syntax.Literal(float(yy.match()), insert_token(yy.slice())))
	
	@staticmethod
	def scan_short_string(yy: IterableScanner): yy.token("short_string", syntax.Literal(yy.match()[1:-1], insert_token(yy.slice())))
	
	@staticmethod
	def scan_word(yy: IterableScanner):
		upper = yy.match().upper()
		if upper in RESERVED: yy.token(upper, syntax.Nom(upper, insert_token(yy.slice())))
		else: yy.token("name", syntax.Nom(sys.intern(yy.match()), insert_token(yy.slice())))
	
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
		
	pass

sophie_parser = SophieParser(_tables)



def reset_parser():
	reset_location_index()

def parse_text(text:str, path:Path, report:Report) -> Union[syntax.Module, Issue]:
	""" Submit text to parser; submit the resulting tree to subsequent pass """
	
	start_segment(path)
	try:
		module = sophie_parser.parse(text, filename=str(path))
		return module
	except syntax.MismatchedBookendsError as ex:
		report.error(ex.args, "These names don't line up. Has part of a function been lost?")
	except UnexpectedTokenError as ex:
		report.generic_parse_error(ex.kind, ex.semantic, _choose_hint(ex.pds, ex.kind))
	except UnexpectedEndOfTextError as ex:
		report.ran_out_of_tokens(path, _choose_hint(ex.pds, "<END>"))

##########################
#
#  I've been meaning to improve parse error messages.
#  Code from here down represents progress in that direction.
#

def _choose_hint(pds, lookahead):
	stack_symbols = sophie_parser.stack_symbols(pds)
	expected = sophie_parser.expected_tokens(pds)
	hint = _best_hint(stack_symbols, lookahead)
	return "Expected any of: %s\n%s"%(" ".join(expected), hint)

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
_hint("CASE : semicolon_list(tag_spec) ● END", "Do you mean ESAC here?")
_hint("semicolon_list(alternative) ELSE ● ->", "This doesn't take an arrow. Just ELSE is enough.")
_hint("CASE semicolon_list(when_clause) ● ESAC", "CASE-WHEN needs an ELSE clause.")
_hint("ELSE expr ● ???", "Probably missing a semicolon just before here.")
_hint("THEN expr ● WHEN", "Probably missing a semicolon just before here.")
_hint("expr ● END", "Probably missing a semicolon just before here.")
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
_hint("name type_parameters IS ( name : name ● ???", "Anticipated a comma or perhaps open-square-bracket here.")
_hint("WHEN expr ● ->", "WHEN goes with THEN. The arrow is for type matches.")
_hint("TYPE : ??? round_list(simple_type) ● ;", "Might be a record missing field types, or the first part of a function-type (expecting '->' and a result-type ).")
_hint("ACTOR ??? END ● ;", "End actors by name: ACTOR foo ... END foo;")
_hint("name formals annotation = expr WHERE semicolon_list(subroutine) END ● ;", "End enclosing functions by name: foo(x) = ... WHERE ... END foo;")
_hint("TYPE : ??? ! ● name", "you have !foo and probably want !(foo) to represent a message/procedure of one argument.")
_hint("IS ROLE ● [", "`foo[T] is role:`, not `foo is role[T]`.")

assert _best_hint("export_section import_section TYPE : name square_list(name) IS".split(), 'OPAQUE')

