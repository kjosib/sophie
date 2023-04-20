from functools import lru_cache
from .ontology import NS, Symbol, Nom, Native
from .hot.concrete import ConcreteType, Product, Arrow, TypeVariable, Nominal

root_namespace = NS(place=None)
ops = {}

LIST : Nominal  # Generated in the preamble.

class PrimitiveType(Symbol):
	""" Presumably add clerical details here. """
	quantifiers = ()
	def __init__(self, name:str):
		self.nom = Nom(name, None)
		self.typ = Nominal(self, ())
	def __repr__(self): return "<%s>"%self.nom
	def has_value_domain(self): return False  # .. HACK ..


def _built_in_type(name:str) -> Nominal:
	entry = PrimitiveType(name)
	term = Nominal(entry, ())
	root_namespace[name] = entry
	return term
literal_number = _built_in_type("number")
literal_string = _built_in_type("string")
literal_flag = _built_in_type("flag")

@lru_cache()
def _arrow_of_math(arity:int) -> Arrow:
	return _arrow_of(literal_number, arity)

def _arrow_of(typ:ConcreteType, arity:int) -> Arrow:
	assert arity > 0
	return Arrow(Product((typ,) * arity), typ)

def _init():
	"""
	Build and return the primitive namespace.
	Oh, and also some bits used for operator syntax.
	
	It's special because it's pre-typed.
	"""
	import operator
	binary = _arrow_of_math(2)
	ops["PowerOf"] = operator.pow, binary
	ops["Mul"] = operator.mul, binary
	ops["FloatDiv"] = operator.truediv, binary
	ops["FloatMod"] = operator.mod, binary
	ops["IntDiv"] = operator.ifloordiv, binary
	ops["IntMod"] = operator.imod, binary
	ops["Add"] = operator.add, binary
	ops["Sub"] = operator.sub, binary
	
	variable = TypeVariable()
	pair_of_same = Product((variable, variable))
	comparison = Arrow(pair_of_same, literal_flag)
	ops["EQ"] = operator.eq, comparison
	ops["NE"] = operator.ne, comparison
	ops["LE"] = operator.le, comparison
	ops["LT"] = operator.lt, comparison
	ops["GE"] = operator.ge, comparison
	ops["GT"] = operator.gt, comparison
	
	ops["Negative"] = operator.neg, _arrow_of_math(1)
	ops["LogicalNot"] = operator.not_, _arrow_of(literal_flag, 1)
	
	logical = _arrow_of(literal_flag, 2)
	ops["LogicalAnd"] = False, logical
	ops["LogicalOr"] = True, logical
	
	def install_flag(name: str, value):
		symbol = Native(Nom(name, None))
		symbol.val = value
		symbol.typ = literal_flag
		root_namespace[name] = symbol
	install_flag('yes', True)
	install_flag('no', False)

_init()

