"""
Sort of like an evaluator, but for types.
Replaces the old type-inference pass.

The idea here is to run the type-level program before running the value-level program.
If the type-level program computes a type, then the value-level program is certainly
well-typed with that type. Otherwise, the value-level program is at serious risk of
experiencing a type-error in practice.

This module in particular represents the type-level execution mechanism.

For now, I'll take the task of the ruminant to be printing the types of the top-level expressions in each module.
Later, I can worry about a constant-folding pass.
"""

from boozetools.support.foundation import Visitor
from .. import syntax, diagnostics
from . import lift_pass, tdx
from .concrete import ConcreteTypeVisitor, TypeVariable, Nominal, Product, Arrow

STATIC_LINK = object()

_rewriter = lift_pass.RewriteIntoTypeRealm()

class DeductionEngine(Visitor):
	def __init__(self, report:diagnostics.Report, verbose:bool):
		self._stx = {}  # Symbol's Type Expression
		self._global_env = {}
		pass
	
	def visit_Module(self, module:syntax.Module):
		for fn in module.all_functions:
			self._stx[fn] = _rewriter.visit(fn)
		for expr in module.main:
			tx = _rewriter.visit(expr)
			typ = self.visit(tx, {})
			print(typ.visit(Render()))
		pass
	
	@staticmethod
	def visit_Constant(x:tdx.Constant, env:dict):
		return x.term
	
	# def visit_LookupSymbol(self, x:tdx.LookupSymbol, env:dict):
	# 	sym = x.sym
	# 	target_depth = sym.static_depth
	# 	if target_depth == 0:
	# 		static = self._global_env
	# 	else:
	# 		static = env
	# 		for _ in range(target_depth, x.source_depth):
	# 			static = static[STATIC_LINK]
	# 	if isinstance(sym, syntax.FormalParameter):
	# 		return static[sym]
	# 	if isinstance(sym, syntax.Function):
	# 		try: return static[sym]
	# 		except KeyError:
	# 			if sym.params:
	# 				static[sym] = Closure(self._stx[sym], static)
	# 				return static[sym]
	# 			else:
	# 				return self.visit(self._stx[sym], static)
	# 	print(sym)
	# 	exit(2)
	#
	# pass

class Closure:
	def __init__(self, x:tdx.TDX, static:dict):
		self.x, self.static = x, static
		
class Render(ConcreteTypeVisitor):
	""" Return a string representation of the term. """
	def __init__(self):
		self._var_names = {}
	def on_variable(self, v: TypeVariable):
		if v not in self._var_names:
			self._var_names[v] = "?%s" % _name_variable(len(self._var_names) + 1)
		return self._var_names[v]
	def on_nominal(self, n: Nominal):
		if n.params:
			brick = "[%s]"%(", ".join(p.visit(self) for p in n.params))
		else:
			brick = ""
		return n.dfn.nom.text+brick
	def on_arrow(self, a: Arrow):
		return "%s -> %s" % (a.arg.visit(self), a.res.visit(self))
	def on_product(self, p: Product):
		return "(%s)" % (", ".join(a.visit(self) for a in p.fields))
	
def _name_variable(n):
	name = ""
	while n:
		n, remainder = divmod(n-1, 26)
		name = chr(97+remainder) + name
	return name
