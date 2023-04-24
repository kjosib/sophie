"""
Sort of like an evaluator, but for types.
Replaces the old type-inference pass.

The idea here is to run the type-level program before running the value-level program.
If the type-level program computes a type, then the value-level program is certainly
well-typed with that type. Otherwise, the value-level program is at serious risk of
experiencing a type-error in practice.

This module represents one oversimplified type-level execution mechanism.
The type side of things can be call-by-value, which is a bit easier I think.
"""
from typing import Sequence
from boozetools.support.foundation import Visitor
from .. import syntax, primitive, diagnostics
from . import calculus

STATIC_LINK = object()

_literal_type_map : dict[type, calculus.SophieType] = {
	bool: primitive.literal_flag,
	str: primitive.literal_string,
	int: primitive.literal_number,
	float: primitive.literal_number,
}

OPS = {glyph:typ for glyph, (op, typ) in primitive.ops.items()}

class ManifestBuilder(Visitor):
	_bind : dict[syntax.TypeParameter:calculus.SophieType]
	
	def __init__(self, tps:Sequence[syntax.TypeParameter], type_args: list[calculus.SophieType]):
		self._bind = dict(zip(tps, type_args))
		
	def visit_RecordSpec(self, rs:syntax.RecordSpec) -> calculus.ProductType:
		return calculus.ProductType(self.visit(field.type_expr) for field in rs.fields)
	
	def visit_TypeCall(self, tc:syntax.TypeCall) -> calculus.SophieType:
		dfn = tc.ref.dfn
		if isinstance(dfn, syntax.TypeParameter):
			return self._bind[dfn]
		if isinstance(dfn, syntax.Opaque):
			return calculus.OpaqueType(dfn)
		args = [self.visit(a) for a in tc.arguments]
		if isinstance(dfn, syntax.Record):
			return calculus.RecordType(dfn, args)
		if isinstance(dfn, syntax.Variant):
			return calculus.SumType(dfn, args)
		if isinstance(dfn, syntax.TypeAlias):
			return ManifestBuilder(dfn.parameters,args).visit(dfn.body)
		raise NotImplementedError(type(dfn))
	
	def visit_ArrowSpec(self, spec:syntax.ArrowSpec):
		return calculus.ArrowType(calculus.ProductType(map(self.visit, spec.lhs)), self.visit(spec.rhs))

# class Closure:
# 	def __init__(self, static_link: dict, udf: syntax.Function):
# 		self.udf = udf
# 		self._static_link = static_link
#
# 	def _name(self): return self.udf.nom.text
#
# 	def bind(self, arg_typ:Product) -> dict:
# 		assert isinstance(arg_typ, Product)
# 		args = arg_typ.fields
# 		arity = len(self.udf.params)
# 		if arity != len(args):
# 			raise TypeError("Procedure %s expected %d args, got %d."%(self._name(), arity, len(args)))
# 		inner_env = {STATIC_LINK:self._static_link}
# 		for formal, actual in zip(self.udf.params, args):
# 			inner_env[formal] = actual
# 		return inner_env
	
class DeductionEngine(Visitor):
	def __init__(self, report:diagnostics.Report):
		self._on_error = report.on_error("Checking Types")
		self._global_env = {t:None for t in _literal_type_map.values()}
		pass
	
	def visit_Module(self, module:syntax.Module):
		for td in module.types: self.visit(td)
		for fi in module.foreign: self.visit(fi)
		for fn in module.outer_functions:
			self._global_env[fn] = calculus.TopLevelFunctionType(fn)
		for expr in module.main:
			self.visit(expr, self._global_env)
		pass
	
	def visit_Record(self, r: syntax.Record):
		type_args = [calculus.TypeVariable() for _ in r.parameters]
		arg = ManifestBuilder(r.parameters, type_args).visit(r.spec)
		res = calculus.RecordType(r, type_args)
		self._global_env[r] = calculus.ArrowType(arg, res)
	
	def visit_Variant(self, v: syntax.Variant):
		self._global_env[v] = None
		type_args = [calculus.TypeVariable() for _ in v.parameters]
		builder = ManifestBuilder(v.parameters, type_args)
		for st in v.subtypes:
			if st.body is None:
				self._global_env[st] = calculus.EnumType(st)
			elif isinstance(st.body, syntax.RecordSpec):
				arg = builder.visit(st.body)
				res = calculus.TaggedRecord(st, type_args)
				self._global_env[st] = calculus.ArrowType(arg, res)
	
	def visit_ImportForeign(self, d:syntax.ImportForeign):
		for group in d.groups:
			type_args = [calculus.TypeVariable() for _ in group.type_params]
			typ = ManifestBuilder(group.type_params, type_args).visit(group.type_expr)
			for sym in group.symbols:
				self._global_env[sym] = typ
	
	@staticmethod
	def visit_Literal(expr: syntax.Literal, env:dict) -> calculus.SophieType:
		return _literal_type_map[type(expr.value)]

	def _call_site(self, fn_type, args, env:dict) -> calculus.SophieType:
		arg_types = [self.visit(a, env) for a in args]
		
		if any(t is calculus.ERROR for t in arg_types):
			return calculus.ERROR
		
		if isinstance(fn_type, calculus.ArrowType):
			product = calculus.ProductType(arg_types)
			raise NotImplementedError(type(fn_type))
		
		if isinstance(fn_type, calculus.TopLevelFunctionType):
			formals = fn_type.fn.params
			if len(formals) != len(arg_types):
				self._on_error(args, "The called function wants %d arguments, but got %d instead"%(len(formals), len(args)))
				return calculus.ERROR
			inner = dict(zip(fn_type.fn.params, arg_types))
			for sub in fn_type.fn.where:
				inner[sub] = calculus.NestedFunctionType(sub, inner)
			return self.visit(fn_type.fn.expr, inner)
		
		if isinstance(fn_type, calculus.NestedFunctionType):
			raise NotImplementedError(type(fn_type))
		
		raise NotImplementedError(type(fn_type))
	
	def visit_Call(self, site: syntax.Call, env: dict) -> calculus.SophieType:
		fn_type = self.visit(site.fn_exp, env)
		if fn_type is calculus.ERROR: return calculus.ERROR
		return self._call_site(fn_type, site.args, env)
	
	def visit_BinExp(self, expr:syntax.BinExp, env:dict) -> calculus.SophieType:
		return self._call_site(OPS[expr.glyph], (expr.lhs, expr.rhs), env)
		
	def visit_Lookup(self, lu:syntax.Lookup, env:dict):
		target = lu.ref.dfn
		if target.static_depth == 0:
			return self._global_env[target]
		else:
			for _ in range(lu.source_depth - target.static_depth):
				env = env[STATIC_LINK]
			return env[target]

		
# class Render(TypeVisitor):
# 	""" Return a string representation of the term. """
# 	def __init__(self):
# 		self._var_names = {}
# 	def on_variable(self, v: TypeVariable):
# 		if v not in self._var_names:
# 			self._var_names[v] = "?%s" % _name_variable(len(self._var_names) + 1)
# 		return self._var_names[v]
# 	def on_nominal(self, n: Nominal):
# 		if n.params:
# 			brick = "[%s]"%(", ".join(p.visit(self) for p in n.params))
# 		else:
# 			brick = ""
# 		return n.dfn.nom.text+brick
# 	def on_arrow(self, a: Arrow):
# 		return "%s -> %s" % (a.arg.visit(self), a.res.visit(self))
# 	def on_product(self, p: Product):
# 		return "(%s)" % (", ".join(a.visit(self) for a in p.fields))
	
def _name_variable(n):
	name = ""
	while n:
		n, remainder = divmod(n-1, 26)
		name = chr(97+remainder) + name
	return name
