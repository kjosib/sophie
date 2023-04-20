"""
Bits that convert a value-domain program into a type-domain program form-by-form.
"""

from boozetools.support.foundation import Visitor
from .. import syntax, primitive
from . import tdx

FLAG = tdx.Constant(primitive.literal_flag)
NUMBER = tdx.Constant(primitive.literal_number)
_literal_type_map = {
	str : tdx.Constant(primitive.literal_string),
	bool : FLAG,
	int : NUMBER,
	float : NUMBER,
}

OPS = {glyph:tdx.Constant(typ) for glyph, (op, typ) in primitive.ops.items()}


class RewriteIntoTypeRealm(Visitor):
	"""
	The first step in abstract interpretation is to map the concrete code into an
	abstracted version of itself that specifically focuses on the topic of type safety.
	This class represents that translation
	"""
	
	def visit_Function(self, fn:syntax.Function) -> tdx.TDX:
		if fn.params:
			pass
		else:
			return self.visit(fn.expr)
	
	@staticmethod
	def visit_Literal(expr: syntax.Literal) -> tdx.TDX:
		return _literal_type_map[type(expr.value)]
	
	@staticmethod
	def visit_Lookup(expr: syntax.Lookup) -> tdx.TDX:
		target = expr.ref.dfn
		if target.static_depth == 0:
			return tdx.GlobalSymbol(target)
		else:
			return tdx.StackSymbol(target, expr.source_depth-target.static_depth)
	
	def visit_FieldReference(self, fr: syntax.FieldReference) -> tdx.TDX:
		return tdx.FieldType(self.visit(fr.lhs), fr.field_name)
	
	def visit_Cond(self, cond: syntax.Cond) -> tdx.TDX:
		if_part = self.visit(cond.if_part)
		branches = [self.visit(x) for x in (cond.then_part, cond.else_part)]
		return tdx.Apply(if_part, tdx.Operator(FLAG, tdx.Union(branches)))
	
	def visit_MatchExpr(self, mx: syntax.MatchExpr) -> tdx.TDX:
		# Return the application of an operator (i.e. concrete-arrow) that takes the expected subject-type
		# and answers with the union of the (types of the) branches.
		
		# Technique: The match expression itself adds a symbol to the scope
		subject = tdx.LookupSymbol(mx.subject_dfn)
		patterns = [tdx.LookupSymbol(alt.pattern.dfn, 0) for alt in mx.alternatives]
		branches = {alt.pattern.dfn:self.visit(alt.sub_expr) for alt in mx.alternatives}
		if mx.otherwise is not None:
			branches.append(self.visit(mx.otherwise))
		return tdx.Apply(subject, tdx.Operator(tdx.Union(patterns), tdx.Union(branches)))
	
	def _call_site(self, fn_type, arg_exprs) -> tdx.TDX:
		arg_product = tdx.ProductType(tuple(self.visit(a) for a in arg_exprs))
		return tdx.Apply(arg_product, fn_type)
	
	def visit_Call(self, expr: syntax.Call) -> tdx.TDX:
		return self._call_site(self.visit(expr.fn_exp), expr.args)
	
	def visit_BinExp(self, expr: syntax.BinExp) -> tdx.TDX:
		return self._call_site(OPS[expr.glyph], (expr.lhs, expr.rhs))
	visit_ShortCutExp = visit_BinExp
	
	def visit_UnaryExp(self, expr: syntax.UnaryExp) -> tdx.TDX:
		return self._call_site(OPS[expr.glyph], (expr.arg,))
	
	def visit_ExplicitList(self, expr: syntax.ExplicitList) -> tdx.TDX:
		param = tdx.Union([self.visit(x) for x in expr.elts])
		return tdx.Syntactic(primitive.LIST, [param])
