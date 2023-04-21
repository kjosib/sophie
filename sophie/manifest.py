"""
Things related to the manifest portion of the type information.

"""
import inspect
from boozetools.support.foundation import Visitor
from . import syntax, ontology
from .hot.concrete import ConcreteTypeVisitor, TypeVariable, Nominal, Arrow, Product

def type_module(module: syntax.Module, report):
	TypeBuilder(module, report.on_error("Building Types"))
	if not report.issues:
		for mx in module.all_match_expressions:
			check_match_expressions(mx, report.on_error("Checking Type-Case Matches"))
	pass

class Rewrite(ConcreteTypeVisitor):
	# Relatively trivial re-write to build the type of an alias during the manifest phase.
	# Also comes in handy when
	def __init__(self, mapping:dict):
		self._mapping = mapping
	def on_variable(self, v: TypeVariable):
		return self._mapping.get(v,v)
	def on_nominal(self, n: Nominal):
		return n if not n.params else Nominal(n.dfn, [p.visit(self) for p in n.params])
	def on_arrow(self, a: Arrow):
		return Arrow(a.arg.visit(self), a.res.visit(self))
	def on_product(self, p: Product):
		return Product(tuple(f.visit(self) for f in p.fields))
	
class TypeBuilder(Visitor):
	""" Evaluate all the type-expressions into (potentially-generic) types; bind these to names / variables.  """
	def __init__(self, module:syntax.Module, on_error):
		self.on_error = on_error
		for td in module.types:
			if isinstance(td.body, syntax.RecordSpec):
				td.typ = Nominal(td, td.quantifiers)
			elif isinstance(td.body, syntax.VariantSpec):
				td.typ = Nominal(td, td.quantifiers)
				for st in td.body.subtypes:
					st.variant = td
					if st.body is None or isinstance(st.body, syntax.RecordSpec):
						st.typ = Nominal(st, td.quantifiers)
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
		for d in module.foreign:
			self.visit(d)
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
		rs.product_type = Product(tuple(product))

	def visit_ArrowSpec(self, spec: syntax.ArrowSpec):
		arg = Product(tuple(self.visit(a) for a in spec.lhs))
		res = self.visit(spec.rhs)
		return Arrow(arg, res)

	def visit_TypeCall(self, tc:syntax.TypeCall):
		inner = tc.ref.dfn.typ
		args = [self.visit(a) for a in tc.arguments]
		formals = tc.ref.dfn.quantifiers
		if len(args) != len(formals): self.on_error([tc], "Got %d type-arguments; expected %d"%(len(args), len(formals)))
		mapping = {Q: self.visit(arg) for Q, arg in zip(formals, tc.arguments)}
		return inner.visit(Rewrite(mapping))
	
	def visit_Function(self, fn: syntax.Function):
		body_typ = self.visit(fn.result_type_expr) if fn.result_type_expr else TypeVariable()
		if fn.params:
			arg = Product(tuple(self.visit(p) for p in fn.params))
			fn.typ = Arrow(arg, body_typ)
		else:
			fn.typ = body_typ
		pass
	
	def visit_FormalParameter(self, fp: syntax.FormalParameter):
		it = TypeVariable() if fp.type_expr is None else self.visit(fp.type_expr)
		fp.typ = it
		return it
	
	def visit_GenericType(self, gt:syntax.GenericType):
		return gt.dfn.typ

	def visit_ImplicitType(self, it:syntax.ImplicitType):
		return TypeVariable()

	def visit_ImportForeign(self, d:syntax.ImportForeign):
		for group in d.groups:
			typ = self.visit(group.type_expr)
			for sym in group.symbols:
				sym.typ = typ
			if isinstance(typ, Arrow):
				probe = [None]*len(typ.arg.fields)
				for sym in group.symbols:
					self._check_arity(probe, sym)
	
	def _check_arity(self, probe, sym):
		fn = sym.val
		if not callable(fn):
			self.on_error([sym.nom], "This thing is declared as a function, but the underlying Python object is not callable.")
			return
		try: signature = inspect.signature(fn)
		except ValueError: return  # There are some broken signatures among the built-ins.
		try: signature.bind(*probe)
		except TypeError:
			self.on_error([sym.nom], "This function won't accept %d (positional) parameters."%len(probe))
		
					

def check_match_expressions(mx:syntax.MatchExpr, on_error):
	non_subtypes = []
	duplicates = []
	seen = set()
	
	subtypes : list[syntax.SubTypeSpec] = []
	
	for alt in mx.alternatives:
		dfn = alt.pattern.dfn
		if isinstance(dfn, syntax.SubTypeSpec):
			subtypes.append(dfn)
			if dfn in seen:
				duplicates.append(alt.pattern)
			else:
				seen.add(dfn)
		else:
			non_subtypes.append(alt.pattern)
			
	variants = [dfn.variant for dfn in subtypes]
	mistypes = [v for v in variants if v is not variants[0]]
	
	if mistypes:
		on_error([variants[0]] + mistypes, "These do not all come from the same variant type.")
	if non_subtypes:
		on_error(non_subtypes, "This case is not a member of any variant.")
	if duplicates:
		on_error(duplicates, "This duplicates an earlier case.")
	if non_subtypes or duplicates or mistypes:
		return
	
	mx.variant = variants[0]
	seen = set()
	for alt in mx.alternatives:
		seen.add(alt.pattern.dfn)
	exhaustive = len(seen) == len(mx.variant.body.subtypes)
	if exhaustive and mx.otherwise:
		on_error([mx, mx.otherwise], "This case-construction is exhaustive; the otherwise-clause cannot run.")
	if not (exhaustive or mx.otherwise):
		on_error([mx], "This case-construction does not cover all the cases of %s and lacks an otherwise-clause." % mx.variant.nom)
	pass

		