"""
"""
import sys
from pathlib import Path
from typing import Union

from boozetools.macroparse.runtime import TypicalApplication, make_tables
from boozetools.scanning.engine import IterableScanner
from boozetools.parsing.interface import ParseError
from boozetools.support.failureprone import Issue, Evidence, Severity
from boozetools.support.pretty import DOT
from . import syntax

class SophieParseError(ParseError):
	pass

_tables = make_tables(Path(__file__).parent/"Sophie.md")

class SophieParser(TypicalApplication):
	RESERVED = frozenset(t for t in _tables["parser"]["terminals"] if t.isupper() and t.isalpha())
	
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
		else: yy.token("name", syntax.Name(sys.intern(yy.match()), yy.slice()))
	
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

def parse_file(pathname):
	"""Read file given by name; pass contents to next phase."""
	with open(pathname, "r") as fh:
		text = fh.read()
	return parse_text(text, pathname)

def parse_text(text:str, pathname:Path) -> Union[syntax.Module, Issue]:
	""" Submit text to parser; submit the resulting tree to subsequent pass """
	try:
		return sophie_parser.parse(text, filename=str(pathname))
	except syntax.MismatchedBookendsError as ex:
		return Issue(
			phase="Checking Bookends",
			severity=Severity.ERROR,
			description="Mismatched where-clause end needs to match",
			evidence={"": [Evidence(where) for where in ex.args]}
		)
	except ParseError as ex:
		stack_symbols, kind, where = ex.args
		return Issue(
			phase="Parsing",
			severity=Severity.ERROR,
			description="Unexpected token at %r %s %r" % (stack_symbols, DOT, kind),
			evidence={"": [Evidence(where)]},
		)

def complain(issues:list[Issue]):
	for i in issues:
		i.emit(lambda x:sophie_parser.source)
