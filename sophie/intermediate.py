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
}

def emit(x): print(x, end=" ")
def nl(): print()

class Translation(Visitor):
	def visit_RoadMap(self, roadmap:RoadMap):
		print("It doesn't do much just yet...")
		for module in roadmap.each_module:
			self.visit(module)
	
	def visit_Module(self, module:syntax.Module):
		for expr in module.main:
			self.visit(expr)
			emit("DISPLAY")
			nl()

	def visit_Lookup(self, lu:syntax.Lookup):
		self.visit(lu.ref)

	@staticmethod
	def visit_PlainReference(ref:syntax.PlainReference):
		emit(ref.nom.text)
		
	def visit_BinExp(self, it: syntax.BinExp):
		self.visit(it.lhs)
		self.visit(it.rhs)
		emit(INSTRUCTION_FOR[it.glyph])

	@staticmethod
	def visit_Literal(l:syntax.Literal):
		if isinstance(l.value, str):
			emit('"'+l.value+'"')
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
