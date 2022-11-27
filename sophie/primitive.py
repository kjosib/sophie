import inspect
from functools import lru_cache
from .ontology import SymbolTableEntry, NS, TypeVariable, PrimitiveType
from .algebra import Term, Product, Arrow

root_namespace = NS(place=None)
ops = {}


class Native:
	""" Superclass of built-in run-time things. """
	def has_value_domain(self): return True

class NativeValue(Native):
	def __init__(self, value):
		self.value = value

class NativeFunction(Native):
	""" Distinct from NativeValue in that the runtime needs to deal well with calling native functions. """
	def __init__(self, native):
		self.value = native
		self.arity = len(inspect.signature(native).parameters.keys())
		self.typ = _arrow_of_math(self.arity)

def _built_in_type(name:str) -> Term:
	typ = PrimitiveType(name)
	entry = SymbolTableEntry(name, typ, typ)
	entry.quantifiers = ()
	root_namespace[name] = entry
	return typ
literal_number = _built_in_type("number")
literal_string = _built_in_type("string")
literal_flag = _built_in_type("flag")

@lru_cache()
def _arrow_of_math(arity:int) -> Arrow:
	return _arrow_of(literal_number, arity)

def _arrow_of(typ:Term, arity:int) -> Arrow:
	assert arity > 0
	return Arrow(Product((typ,) * arity), typ)

def _init():
	"""
	Build and return the primitive namespace.
	Oh, and also some bits used for operator syntax.
	
	It's special because it's pre-typed.
	"""
	import math, operator
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
	
	NON_WORKING = {"hypot", "log"}
	def value(name:str, dfn, typ:Term):
		root_namespace[name] = SymbolTableEntry(name, dfn, typ)
	def mathfn(name, native):
		arity = len(inspect.signature(native).parameters.keys())
		value(name, NativeFunction(native), _arrow_of_math(arity))
	for name in dir(math):
		if not (name.startswith("_") or name in NON_WORKING):
			native = getattr(math, name)
			if isinstance(native, float):
				value(name, NativeValue(native), literal_number)
			elif callable(native):
				mathfn(name, native)
			else: raise ValueError(native)
	mathfn('log', lambda x:math.log(x))
	mathfn('log_base', lambda x,b: math.log(x, b))
	value('yes', NativeValue(True), literal_flag)
	value('no', NativeValue(False), literal_flag)

_init()

