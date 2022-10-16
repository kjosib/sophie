"""
"""
import sys
from pathlib import Path
from boozetools.macroparse.runtime import TypicalApplication, make_tables
from boozetools.scanning.engine import IterableScanner
from . import forms

_tables = make_tables(Path(__file__).parent/"Sophie.md")

class SophieParser(TypicalApplication):
	RESERVED = frozenset(t for t in _tables["parser"]["terminals"] if t.isupper() and t.isalpha())
	
	def scan_ignore(self, yy: IterableScanner): pass
	def scan_punctuation(self, yy: IterableScanner):
		punctuation = sys.intern(yy.match())
		yy.token(punctuation, punctuation)
	def scan_integer(self, yy: IterableScanner): yy.token("integer", int(yy.match()))
	def scan_real(self, yy: IterableScanner): yy.token("real", float(yy.match()))
	def scan_short_string(self, yy: IterableScanner): yy.token("short_string", yy.match()[1:-1])
	
	def scan_word(self, yy: IterableScanner):
		upper = yy.match().upper()
		if upper in self.RESERVED: yy.token(upper, upper)
		else: yy.token("name", sys.intern(yy.match()))
	
	def scan_relop(self, yy: IterableScanner, op:str):
		yy.token("relop", op)
	
	def parse_nothing(self): return None
	def parse_first(self, item): return [item]
	def parse_more(self, some, another):
		some.append(another)
		return some
	
	def default_parse(self, ctor, *args):
		return getattr(forms, ctor)(*args) if hasattr(forms, ctor) else (ctor, *args)
	pass

sophie_parser = SophieParser(_tables)
