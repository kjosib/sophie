from functools import lru_cache
from .ontology import NS, Nom
from .syntax import Opaque, Variant, FFI_Symbol
from . import calculus

root_namespace = NS(place=None)
ops = {}

LIST : Variant  # Generated in the preamble.

def _built_in_type(name:str) -> calculus.OpaqueType:
	symbol = Opaque(Nom(name, None))
	term = calculus.OpaqueType(symbol)
	root_namespace[name] = symbol
	return term
literal_number = _built_in_type("number")
literal_string = _built_in_type("string")
literal_flag = _built_in_type("flag")

# Hack the console object into the root namespace
root_namespace['console'] = FFI_Symbol(Nom('console', None))


@lru_cache()
def _arrow_of_math(arity:int) -> calculus.ArrowType:
	return _arrow_of(literal_number, arity)

def _arrow_of(typ: calculus.SophieType, arity:int) -> calculus.ArrowType:
	assert arity > 0
	return calculus.ArrowType(calculus.ProductType((typ,) * arity), typ)

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
	
	variable = calculus.TypeVariable()
	pair_of_same = calculus.ProductType((variable, variable))
	comparison = calculus.ArrowType(pair_of_same, literal_flag)
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
	
_init()

