"""
This is currently just some messing around. 

Probably assign every module a name consisting of minimal distinctive prefix.
Then give every function and constructor a mangled name based on its module and any surrounding scopes.
In the process, may as well work out the static depth of every function.
	- There's the textual static depth, and then there's the minimal static depth.
	- Type-checker may contribute to minimal static depth because it's based on the DependencyPass.
It will soon enough be necessary to solve an FFI for basic things.
The static-depth information will be useful for look-up operations.
	- local parameters emit an instruction with an offset from BP.
	- For outer parameters, I'm going to attempt closure capture a'la CLOX.
	- Globals can look up by name. The VM P-ASM may eventually precompute the hash lookup. 
	- locally-nested functions: The *code* is a global; the *closure* presumably becomes a local variable.
	- peers and uncles presumably equate to non-local (outer) variables.

"""

from boozetools.support.foundation import Visitor
from . import syntax
from .resolution import RoadMap

INSTRUCTION_FOR = {
	'PowerOf': 'POW',
	'Mul': 'MUL',
	'FloatDiv': 'DIV',
	'IntDiv': 'IDIV',
	'FloatMod': 'MOD',
	'IntMod': 'IMOD',
	'Add': 'ADD',
	'Sub': 'SUB',
	'EQ': 'EQ',
	'NE': 'EQ NOT',
	'LT': 'LT',
	'LE': 'GT NOT',
	'GT': 'GT',
	'GE': 'LT NOT',
	True: 'TRUE',
	False: 'FALSE',
	"Negative" : "NEG",
	"LogicalNot" : "NOT",
}

def emit(x): print(x, end=" ")
def nl(): print()
def quote(x):
	assert '"' not in x
	return '"'+x+'"'

class Translation(Visitor):
	def visit_RoadMap(self, roadmap:RoadMap):
		print("It doesn't do much just yet...")
		for module in roadmap.each_module:
			self.visit(module)
	
	def visit_Module(self, module:syntax.Module):
		for fn in module.outer_functions:
			emit("{")
			emit(len(fn.params))
			emit(quote(fn.nom.text))
			self.visit(fn.expr)
			emit("}")
			nl()
		for expr in module.main:
			self.visit(expr)
			emit("DISPLAY")
			nl()

	def visit_Lookup(self, lu:syntax.Lookup):
		self.visit(lu.ref)

	@staticmethod
	def visit_PlainReference(ref:syntax.PlainReference):
		# Depends greatly on the nature and scope of the definition.
		# Is it local? Global? Local? Closed-over? Imported? Preamble? Primitive? Foreign?
		# For the moment, pretend it's a simpler problem.
		# Probably eventually attribute a fully-qualified name to every symbol.
		# Maybe module-references are done indirectly and there's a set of debugging-symbols to match?
		# For local params, emit LOCAL instructions correctly.
		# For outer params, presumably emit UPLEVEL instructions per some clever algorithm.
		emit("GLOBAL")
		emit(quote(ref.nom.text))
		
	def visit_BinExp(self, it: syntax.BinExp):
		self.visit(it.lhs)
		self.visit(it.rhs)
		emit(INSTRUCTION_FOR[it.glyph])
	
	def visit_UnaryExp(self, ux:syntax.UnaryExp):
		self.visit(ux.arg)
		emit(INSTRUCTION_FOR[ux.glyph])

	@staticmethod
	def visit_Literal(l:syntax.Literal):
		emit("CONST")
		if isinstance(l.value, str):
			emit(quote(l.value))
		elif isinstance(l.value, (int, float)):
			emit(l.value)
		elif isinstance(l.value, bool):
			emit(INSTRUCTION_FOR[l.value])
		else:
			assert False

	def visit_Call(self, call:syntax.Call):
		# Order of operations here is meaningless because it must be pure.
		# Sort of.
		for arg in call.args:
			self.visit(arg)
		self.visit(call.fn_exp)
		emit("CALL")
