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
from . import syntax, primitive, algebra, ontology

LIST : algebra.Nominal

def type_module(module: syntax.Module, report):
	TypeBuilder(module, report.on_error("Building Types"))
	if not report.issues:
		Experiment(module, report.on_error("Checking Types"))
	pass


class TypeBuilder(Visitor):
	def __init__(self, module:syntax.Module, on_error):
		self.on_error = on_error
		for td in module.types:
			entry = td.name.entry
			if isinstance(td.body, syntax.RecordSpec):
				entry.typ = algebra.Nominal(entry, td.quantifiers)
			elif isinstance(td.body, syntax.VariantSpec):
				entry.typ = algebra.Nominal(entry, td.quantifiers)
				for alt in td.body.alternatives:
					if alt.body is None or isinstance(alt.body, syntax.RecordSpec):
						alt.name.entry.typ = entry.typ  # Cheap hack for now: All the cases are the same type.
					else:
						assert isinstance(alt.body, (syntax.ArrowSpec, syntax.TypeCall))
						raise RuntimeError(alt)
			elif isinstance(td.body, (syntax.ArrowSpec, syntax.TypeCall)):
				entry.typ = self.visit(td.body)
			else:
				raise RuntimeError(td)
		for td in module.types:
			if isinstance(td.body, syntax.VariantSpec): self._patch_variant(td.body)
			elif isinstance(td.body, syntax.RecordSpec): self._patch_record(td.body)
		for fn in module.functions:
			self.visit_Function(fn)

	def _patch_variant(self, vs:syntax.VariantSpec):
		for alt in vs.alternatives:
			assert alt.name.entry.dfn is alt, (alt.name.entry.dfn, alt)
			if isinstance(alt.body, syntax.RecordSpec):
				self._patch_record(alt.body)

	def _patch_record(self, rs:syntax.RecordSpec):
		product = []
		for f in rs.fields:
			typ = self.visit(f.type_expr)
			f.name.entry.typ = typ
			product.append(typ)
		rs.product_type = algebra.Product(tuple(product))

	def visit_ArrowSpec(self, spec: syntax.ArrowSpec):
		arg = algebra.Product(tuple(self.visit(a) for a in spec.lhs))
		res = self.visit(spec.rhs)
		return algebra.Arrow(arg, res)

	def visit_TypeCall(self, tc:syntax.TypeCall):
		entry = tc.name.entry
		inner = entry.typ
		args = [self.visit(a) for a in tc.arguments]
		formals = entry.dfn.quantifiers
		if len(args) != len(formals): self.on_error([tc], "Got %d type-arguments; expected %d"%(len(args), len(formals)))
		mapping = {Q: self.visit(arg) for Q, arg in zip(formals, tc.arguments)}
		return inner.rewrite(mapping)
	
	def visit_Function(self, fn: syntax.Function):
		typ = self.visit(fn.expr_type) if fn.expr_type else algebra.TypeVariable()
		if fn.params:
			arg = algebra.Product(tuple(self.visit(p) for p in fn.params))
			typ = algebra.Arrow(arg, typ)
		fn.name.entry.typ = typ
		for sub_fn in fn.sub_fns.values():
			self.visit_Function(sub_fn)
		pass
	
	def visit_FormalParameter(self, fp: syntax.FormalParameter):
		it = algebra.TypeVariable() if fp.type_expr is None else self.visit(fp.type_expr)
		fp.name.entry.typ = it
		return it

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
		goal = algebra.Arrow(arg, res)
		try:
			gamma = algebra.unify(fn_type, goal)
		except algebra.Incompatible as e:
			a,b = e.args
			self.on_error([expr], "This looks inconsistent: %s / %s  :::  %s / %s"%(fn_type, goal, a,b))
			return res
		else:
			return res.rewrite(gamma)

	def visit_Call(self, expr: syntax.Call):
		fn_type = self.visit(expr.fn_exp)
		return self._call_site(expr, fn_type, expr.args)

	def visit_BinExp(self, expr: syntax.BinExp):
		return self._call_site(expr, OPS[expr.glyph], (expr.lhs, expr.rhs))

	def visit_UnaryExp(self, expr: syntax.UnaryExp):
		return self._call_site(expr, OPS[expr.glyph], (expr.arg, ))

	def visit_Literal(self, expr: syntax.Literal):
		if isinstance(expr.value, str):
			return primitive.literal_string
		if isinstance(expr.value, bool):
			return primitive.literal_flag
		if isinstance(expr.value, (int, float)):
			return primitive.literal_number
		raise TypeError(expr.value)

	def visit_Lookup(self, expr: syntax.Lookup):
		"""
		This function is where let-polymorphism comes from.
		We need to look up the type (and definition) of the symbol,
		and compose a type which represents the function of that
		name as used in that place.
		
		If the name refers to a normal function,
		then rewrite only the variables that are free in its
		"""
		entry = expr.name.entry
		if isinstance(entry.dfn, syntax.Function):
			return entry.typ.fresh({})
		if isinstance(entry.dfn, syntax.FormalParameter):
			return entry.typ
		if isinstance(entry.dfn, (primitive.NativeFunction, primitive.NativeValue)):
			return entry.typ
		if isinstance(entry.dfn, (syntax.TypeDecl, syntax.SubType)):
			body = entry.dfn.body
			if isinstance(body, syntax.RecordSpec):
				return algebra.Arrow(body.product_type, entry.typ).fresh({})
		raise RuntimeError(entry)

	def visit_Function(self, fn: syntax.Function):
		#inner = dict(gamma)
		# Do something with arguments, then inner functions, then body expr, then update.
		# And note whether anything changed, which will control a loop outside.
		pass
	
	def visit_ExplicitList(self, expr: syntax.ExplicitList):
		t0 = algebra.TypeVariable()
		for x in expr.elts:
			t1 = self.visit(x)
			gamma = algebra.unify(t1, t0)
			t0 = t0.rewrite(gamma)
		return algebra.Nominal(LIST.semantic, [t0])
