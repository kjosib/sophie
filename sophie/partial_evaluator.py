"""
The partial evaluator should roughly parallel a ordinary evaluator.
The differences are two-fold:
	One, the obvious, is that we're working with types-not-values.
	Two, more subtle, is that we need to work backwards to find solutions.
The first is sufficient for a manifest-typed language.
	It's relatively easy to visualize and implement.
	Information flows leaves-to-roots, with occasional checks of validity.
The second is necessary for inference.
	Information must also flow from roots to leaves.
	It seems efficient to orchestrate this flow as parameters to a recursion.
"""
from boozetools.support.foundation import Visitor
from . import syntax, primitive, algebra


def type_module(module: syntax.Module, report):
	if not report.issues:
		DefineNamedTypes(module, report.on_error("Defining Types"))
	if not report.issues:
		Experiment(module, report.on_error("Checking Types"))
	pass


class DefineNamedTypes(Visitor):
	"""
	After this pass:
		1. All the typedef symbols have an algebraic type.
		2. These types are properly inter-connected by reference.
	"""
	def __init__(self, module, on_error):
		self.on_error = on_error
		for td in module.types:
			self.visit(td)
		pass
	
	def visit_TypeDecl(self, td:syntax.TypeDecl):
		typ = self.visit(td.body)
		entry = td.name.entry
		assert typ.free.issubset(entry.quantifiers)
		entry.typ = typ
		if isinstance(typ, algebra.Apply):
			entry.echelon = 1 + typ.symbol.echelon
		else:
			entry.echelon = 0
	
	def visit_VariantSpec(self, vs:syntax.VariantSpec):
		members = {}
		for alt in vs.alternatives:
			key = alt.key()
			if alt.type_expr is None:
				body = algebra.the_unit
			else:
				body = self.visit(alt.type_expr)
			tag = algebra.Tagged(vs, key, body)
			alt.name.entry.typ = members[key] = tag
		return algebra.Sum(vs, members)
	
	def visit_RecordSpec(self, rs:syntax.RecordSpec):
		product = algebra.Product(tuple(
			self.visit(f.type_expr)
			for f in rs.fields
		))
		index = {f.name.text:i for i,f in enumerate(rs.fields)}
		return algebra.Record(rs, index, product)
	
	def visit_TypeCall(self, tc:syntax.TypeCall):
		symbol = tc.name.entry
		mapping = {Q:self.visit(arg) for Q,arg in zip(symbol.quantifiers, tc.arguments)}
		return algebra.Apply(symbol, mapping)
		
		

OPS = {glyph:typ for glyph, (op, typ) in primitive.ops.items()}

class Experiment(Visitor):
	"""
	By this point, all type-definition bodies and type-expressions are well-founded.
	This thing's job is to start pushing type-correctness on the function-definitions and value-expressions.
	"""
	def __init__(self, module, on_error):
		self.on_error = on_error
		self.globals = module.namespace
		for fn in module.functions:
			self.visit(fn)
		for expr in module.main:
			self.visit(expr)

	def _call_site(self, expr, fn_type, arg_exprs):
		arg = algebra.Product(tuple(self.visit(a) for a in arg_exprs))
		res = algebra.TypeVariable()
		try:
			gamma = algebra.unify(fn_type, algebra.Arrow(arg, res))
		except algebra.Incompatible as e:
			self.on_error([expr], "Type error messages will get better soon(ish).")
			return res
		else:
			return res.rewrite(gamma)

	def visit_Call(self, expr: syntax.Call):
		fn_type = self.visit(expr.fn_exp)
		return self._call_site(expr, fn_type, expr.args)

	def visit_BinExp(self, expr: syntax.BinExp):
		return self._call_site(expr, OPS[expr.glyph], (expr.lhs, expr.rhs))

	def visit_Literal(self, expr: syntax.Literal):
		if isinstance(expr.value, str):
			return primitive.literal_string
		if isinstance(expr.value, bool):
			return primitive.literal_flag
		if isinstance(expr.value, (int, float)):
			return primitive.literal_number
		raise TypeError(expr.value)

	def visit_Lookup(self, expr: syntax.Lookup):
		entry = expr.name.entry
		typ = entry.typ
		if isinstance(typ, algebra.Term):
			gamma = {}
			typ.instantiate(gamma)
			return typ.rewrite(gamma)
		raise RuntimeError(entry)

	def visit_Function(self, fn: syntax.Function):
		#inner = dict(gamma)
		# Do something with arguments, then inner functions, then body expr, then update.
		# And note whether anything changed, which will control a loop outside.
		pass
