"""
Sort of like an evaluator, but for types.
Replaces the old type-inference pass.

The idea here is to run the type-level program before running the value-level program.
If the type-level program computes a type, then the value-level program is certainly
well-typed with that type. Otherwise, the value-level program is at serious risk of
experiencing a type-error in practice.

This module in particular represents the type-level execution mechanism.
The type side of things can be call-by-value, which is a bit easier I think.

For now, the ruminant's task is to print the types of the top-level expressions in each module.
Later, I can worry about a constant-folding pass.
"""

from boozetools.support.foundation import Visitor
from .. import syntax, diagnostics
from . import lift_pass, tdx
from .concrete import ConcreteTypeVisitor, TypeVariable, Nominal, Product, Arrow

STATIC_LINK = object()

_rewriter = lift_pass.RewriteIntoTypeRealm()

class Closure:
	def __init__(self, static_link: dict, udf: syntax.Function):
		self.udf = udf
		self._static_link = static_link
	
	def _name(self): return self.udf.nom.text
	
	def bind(self, arg_typ:Product) -> dict:
		assert isinstance(arg_typ, Product)
		args = arg_typ.fields
		arity = len(self.udf.params)
		if arity != len(args):
			raise TypeError("Procedure %s expected %d args, got %d."%(self._name(), arity, len(args)))
		inner_env = {STATIC_LINK:self._static_link}
		for formal, actual in zip(self.udf.params, args):
			inner_env[formal] = actual
		return inner_env
	
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
	
	def visit_Apply(self, a:tdx.Apply, env:dict):
		op_typ = self.visit(a.operation, env)
		arg_typ = self.visit(a.argument, env)
		if isinstance(op_typ, Arrow):
			return apply_arrow(op_typ, arg_typ)
		elif isinstance(op_typ, Closure):
			return self.perform(op_typ.udf, op_typ.bind(arg_typ))
		assert False, (op_typ, arg_typ)
	
	def perform(self, sym:syntax.Symbol, env:dict):
		return self.visit(self._stx[sym], env)
	
	def visit_ProductType(self, p:tdx.ProductType, env:dict):
		return Product(self.visit(x, env) for x in p.args)
	
	def visit_GlobalSymbol(self, gs:tdx.GlobalSymbol, env:dict):
		""" Could be looking up a global function, a record-type, or something wrongly-typed. """
		if isinstance(gs.sym, syntax.Function):
			if gs.sym.params:
				return Closure(self._global_env, gs.sym)
			else:
				return self.perform(gs.sym, self._global_env)
		else:
			assert False, gs
	
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
