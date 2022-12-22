"""
Things related to the manifest portion of the type information.

"""
from boozetools.support.foundation import Visitor
from . import syntax, algebra, ontology


def type_module(module: syntax.Module, report):
	TypeBuilder(module, report.on_error("Building Types"))
	if not report.issues:
		check_match_expressions(module, report.on_error("Checking Type-Case Matches"))
	pass


class TypeBuilder(Visitor):
	""" Evaluate all the type-expressions into (potentially-generic) types; bind these to names / variables.  """
	def __init__(self, module:syntax.Module, on_error):
		self.on_error = on_error
		for td in module.types:
			if isinstance(td.body, syntax.RecordSpec):
				td.typ = algebra.Nominal(td, td.quantifiers)
			elif isinstance(td.body, syntax.VariantSpec):
				td.typ = algebra.Nominal(td, td.quantifiers)
				for st in td.body.subtypes:
					st.variant = td
					if st.body is None or isinstance(st.body, syntax.RecordSpec):
						st.typ = algebra.Nominal(st, td.quantifiers)
					else:
						assert isinstance(st.body, (syntax.ArrowSpec, syntax.TypeCall))
						raise RuntimeError(st)
			elif isinstance(td.body, (syntax.ArrowSpec, syntax.TypeCall)):
				td.typ = self.visit(td.body)
			else:
				raise RuntimeError(td)
		for td in module.types:
			if isinstance(td.body, syntax.VariantSpec): self._patch_variant(td.body)
			elif isinstance(td.body, syntax.RecordSpec): self._patch_record(td.body)
		for fn in module.all_functions:
			self.visit_Function(fn)

	def _patch_variant(self, vs:syntax.VariantSpec):
		for st in vs.subtypes:
			if isinstance(st.body, syntax.RecordSpec):
				self._patch_record(st.body)
			elif st.body is not None:
				st.typ = self.visit(st.body)

	def _patch_record(self, rs:syntax.RecordSpec):
		product = []
		for f in rs.fields:
			typ = self.visit(f.type_expr)
			f.typ = typ
			product.append(typ)
		rs.product_type = algebra.Product(tuple(product))

	def visit_ArrowSpec(self, spec: syntax.ArrowSpec):
		arg = algebra.Product(tuple(self.visit(a) for a in spec.lhs))
		res = self.visit(spec.rhs)
		return algebra.Arrow(arg, res)

	def visit_TypeCall(self, tc:syntax.TypeCall):
		inner = tc.ref.dfn.typ
		args = [self.visit(a) for a in tc.arguments]
		formals = tc.ref.dfn.quantifiers
		if len(args) != len(formals): self.on_error([tc], "Got %d type-arguments; expected %d"%(len(args), len(formals)))
		mapping = {Q: self.visit(arg) for Q, arg in zip(formals, tc.arguments)}
		return inner.rewrite(mapping)
	
	def visit_Function(self, fn: syntax.Function):
		typ = self.visit(fn.result_type_expr) if fn.result_type_expr else algebra.TypeVariable()
		if fn.params:
			arg = algebra.Product(tuple(self.visit(p) for p in fn.params))
			typ = algebra.Arrow(arg, typ)
		fn.typ = typ
		pass
	
	def visit_FormalParameter(self, fp: syntax.FormalParameter):
		it = algebra.TypeVariable() if fp.type_expr is None else self.visit(fp.type_expr)
		fp.typ = it
		return it
	
def check_match_expressions(module:syntax.Module, on_error):
	for mx in module.all_match_expressions:
		patterns : list[ontology.Nom] = [alt.pattern for alt in mx.alternatives]
		bogons = [p for p in patterns if type(p.dfn) is not syntax.SubTypeSpec]
		if bogons:
			on_error(bogons, "This is not a subtype.")
			return
		first = mx.alternatives[0]
		variant : syntax.TypeDecl = first.pattern.dfn.variant
		for alt in mx.alternatives:
			if alt.pattern.dfn.variant is not variant:
				bogons.append(alt.pattern)
		if bogons:
			bogons.insert(0, first.pattern)
			on_error(bogons, "These do not all come from the same variant type.")
			return
		local_mapping = {Q:algebra.TypeVariable() for Q in variant.quantifiers}
		mx.input_type = variant.typ.rewrite(local_mapping)
		seen = set()
		for alt in mx.alternatives:
			subtype = alt.pattern.dfn
			seen.add(subtype)
			assert isinstance(subtype, syntax.SubTypeSpec)
			alt.proxy.typ = subtype.typ.rewrite(local_mapping)
		exhaustive = len(seen) == len(variant.body.subtypes)
		if exhaustive and mx.otherwise:
			on_error([mx, mx.otherwise], "This case-construction is exhaustive; the otherwise-clause cannot run.")
		if not (exhaustive or mx.otherwise):
			on_error([mx], "This case-construction does not cover all the cases of %s and lacks an otherwise-clause."%(variant.nom))
		pass

		