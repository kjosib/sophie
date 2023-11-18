"""
Build the primitive namespace.
Also, some bits used for operator syntax
and the primitive literal types
"""

from .ontology import NS, Nom
from . import calculus, syntax

root_namespace = NS(place=None)
OP_TYPE = {}

def _built_in_type(name:str) -> calculus.OpaqueType:
	symbol = syntax.Opaque(Nom(name, None), ())
	term = calculus.OpaqueType(symbol)
	root_namespace[name] = symbol
	return term

def _arrow_of(typ: calculus.SophieType, arity:int) -> calculus.ArrowType:
	assert arity > 0
	product = calculus.ProductType((typ,) * arity).exemplar()
	return calculus.ArrowType(product, typ).exemplar()

literal_number = _built_in_type("number")
literal_string = _built_in_type("string")
literal_flag = _built_in_type("flag")
literal_act = _built_in_type("act")
literal_msg = _built_in_type("message")
logical_shortcut = _arrow_of(literal_flag, 2)

def _init():
	def overload(glyph, arity):
		symbol = syntax.Overload(Nom(glyph, None), arity)
		OP_TYPE[glyph] = calculus.AdHocType(symbol)
		
	def relop_type(case):
		pair = calculus.ProductType((case, case)).exemplar()
		return calculus.ArrowType(pair, literal_flag).exemplar()
	
	math_op = _arrow_of(literal_number, 2)
	
	for op in '^ * / % DIV MOD + -'.split():
		overload(op, 2)
		OP_TYPE[op].cases.append(math_op)
	
	numeric = relop_type(literal_number)
	stringy = relop_type(literal_string)
	flagged = relop_type(literal_flag)
	
	def eq(op):
		rel(op)
		OP_TYPE[op].cases.append(flagged)
	
	def rel(op):
		overload(op, 2)
		OP_TYPE[op].cases.append(numeric)
		OP_TYPE[op].cases.append(stringy)

	eq("==")
	eq("!=")
	rel("<=")
	rel("<")
	rel(">=")
	rel(">")
	
	overload("Negative", 1)
	OP_TYPE["Negative"].cases.append(_arrow_of(literal_number, 1))
	
	OP_TYPE["LogicalNot"] = _arrow_of(literal_flag, 1)
	
	
_init()

