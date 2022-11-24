import inspect
from functools import lru_cache
from boozetools.support.symtab import NameSpace
from .ontology import SymbolTableEntry, KIND_TYPE, KIND_VALUE
from .algebra import SophieType, ProductType, Arrow, TypeVariable

class Primitive:
	""" Superclass of things that can't occur in syntax. """


class PrimitiveType(Primitive):
	""" The numbers, strings, and flags. """
	
	def __init__(self, name: str):
		self.name = name
	
	def __str__(self):
		return self.name
	
	def has_value_domain(self): return False
	pass


class NativeValue(Primitive):
	def __init__(self, value):
		self.value = value
	def has_value_domain(self): return True

class NativeFunction(Primitive):
	""" Distinct from NativeValue in that the runtime needs to deal well with calling native functions. """
	def __init__(self, native):
		self.value = native
		self.arity = len(inspect.signature(native).parameters.keys())
		self.typ = _arrow_of_math(self.arity)
	def has_value_domain(self): return True

@lru_cache()
def _arrow_of_math(arity:int) -> SophieType:
	return _arrow_of(literal_number, arity)

def _arrow_of(typ:SophieType, arity:int) -> SophieType:
	assert arity > 0
	return Arrow(ProductType((typ,) * arity), typ)

def _built_in_type(name:str):
	typ = PrimitiveType(name)
	entry = SymbolTableEntry(KIND_TYPE, typ, typ)
	root_namespace[name] = entry
	return entry.typ


root_namespace = NameSpace(place=None)
literal_number = _built_in_type("number")
literal_string = _built_in_type("string")
literal_flag = _built_in_type("flag")
ops = {}

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
	
	variable = TypeVariable("_")
	pair_of_same = ProductType((variable, variable))
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
	def value(name:str, dfn, typ:SophieType):
		root_namespace[name] = SymbolTableEntry(KIND_VALUE, dfn, typ)
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

