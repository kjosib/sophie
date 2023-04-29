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
from typing import Optional, Sequence
from boozetools.support.foundation import Visitor

from .calculus import UDFType, ProductType, ArrowType, TaggedRecord, EnumType, SumType, RecordType, OpaqueType
from .. import syntax, primitive, diagnostics
from . import calculus

TYPE_MISMATCH = "These don't have compatible types."

STATIC_LINK = object()

_literal_type_map : dict[type, calculus.OpaqueType] = {
	bool: primitive.literal_flag,
	str: primitive.literal_string,
	int: primitive.literal_number,
	float: primitive.literal_number,
}

OPS = {glyph:typ for glyph, (op, typ) in primitive.ops.items()}

class ManifestBuilder(Visitor):
	"""Converts the syntax of manifest types into corresponding type-calculus objects."""
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

class Rewriter(calculus.TypeVisitor):
	def __init__(self, gamma:dict):
		self._gamma = gamma
	def on_opaque(self, o: calculus.OpaqueType):
		return o
	def on_tag_record(self, t: calculus.TaggedRecord):
		return calculus.TaggedRecord(t.st, [a.visit(self) for a in t.type_args])
	def on_record(self, r: calculus.RecordType):
		return calculus.RecordType(r.symbol, [a.visit(self) for a in r.type_args])
	def on_variable(self, v:calculus.TypeVariable):
		return self._gamma[v]

class Binder(Visitor):
	"""
	Discovers (or fails) a substitution-of-variables (in the formal)
	which make the formal accept the actual as an instance.
	"""
	def __init__(self):
		self.gamma = {}
		self.ok = True
		
	def fail(self):
		self.ok = False
	
	def visit_TypeVariable(self, formal:calculus.TypeVariable, actual):
		if formal in self.gamma:
			union_finder = UnionFinder(self.gamma[formal])
			union_finder.unify_with(actual)
			if union_finder.died:
				self.fail()
			else:
				self.gamma[formal] = union_finder.result()
		else:
			self.gamma[formal] = actual
	
	def parallel(self, formal: Sequence[calculus.SophieType], actual: Sequence[calculus.SophieType]):
		assert len(formal) == len(actual)
		return [self.visit(f, a) for f, a in zip(formal, actual)]
	
	def visit_ProductType(self, formal:calculus.ProductType, actual):
		if not isinstance(actual, calculus.ProductType):
			return self.fail()
		if formal.number == actual.number:
			return
		if len(formal.fields) != len(actual.fields):
			return self.fail()
		self.parallel(formal.fields, actual.fields)
		
	def visit_OpaqueType(self, formal:calculus.OpaqueType, actual):
		if formal.number == actual.number:
			return
		else:
			self.fail()
	
	def visit_SumType(self, formal:calculus.SumType, actual):
		if formal.number == actual.number:
			return
		elif isinstance(actual, calculus.SumType):
			if formal.variant is actual.variant:
				self.parallel(formal.type_args, actual.type_args)
			else:
				self.fail()
		elif isinstance(actual, calculus.TaggedRecord):
			if formal.variant is actual.st.variant:
				self.parallel(formal.type_args, actual.type_args)
			else:
				self.fail()
		elif isinstance(actual, calculus.EnumType):
			if formal.variant is actual.st.variant:
				pass
			else:
				self.fail()
		else:
			raise NotImplementedError(actual)

class UnionFinder(Visitor):
	def __init__(self, prototype:calculus.SophieType):
		self._prototype = prototype
		self.died = False
	def result(self):
		return self._prototype
	def unify_with(self, that):
		self._prototype = self.do(self._prototype, that)
	
	def parallel(self, these:Sequence[calculus.SophieType], those:Sequence[calculus.SophieType]):
		assert len(these) == len(those)
		return [self.do(a, b) for a,b in zip(these, those)]
	
	def do(self, this:calculus.SophieType, that:calculus.SophieType):
		if this.number == that.number or that is calculus.BOTTOM: return this
		elif that is calculus.ERROR: return that
		else:
			typ = self.visit(this, that)
			if typ is None:
				self.died = True # Maybe highlight the specific breakage?
				return calculus.ERROR
			else:
				return typ

	@staticmethod
	def visit__Bottom(_, that:calculus.SophieType):
		return that
		
	@staticmethod
	def visit_OpaqueType(_, __):
		return None
		
	def visit_RecordType(self, this:calculus.RecordType, that:calculus.SophieType):
		if isinstance(that, calculus.RecordType) and this.symbol is that.symbol:
			return calculus.RecordType(this.symbol, self.parallel(this.type_args, that.type_args))

	def visit_TaggedRecord(self, this:calculus.TaggedRecord, that:calculus.SophieType):
		if isinstance(that, calculus.TaggedRecord):
			if this.st is that.st:
				type_args = self.parallel(this.type_args, that.type_args)
				return calculus.TaggedRecord(this.st, type_args)
			if this.st.variant is that.st.variant:
				type_args = self.parallel(this.type_args, that.type_args)
				return calculus.SumType(this.st.variant, type_args)
		elif isinstance(that, calculus.EnumType):
			if this.st.variant is that.st.variant:
				return calculus.SumType(this.st.variant, this.type_args)
		elif isinstance(that, calculus.SumType):
			if this.st.variant is that.variant:
				type_args = self.parallel(this.type_args, that.type_args)
				return calculus.SumType(that.variant, type_args)

ENV = dict[syntax.Symbol, Optional[calculus.SophieType]]


class DeductionEngine(Visitor):
	_global_env : ENV
	def __init__(self, report:diagnostics.Report, verbose:bool):
		self._on_error = report.on_error("Checking Types")
		self._verbose = verbose
		self._global_env = {
			ot.symbol: ot
			for ot in _literal_type_map.values()
		}
	
	def visit_Module(self, module:syntax.Module):
		for td in module.types: self.visit(td)
		for fi in module.foreign: self.visit(fi)
		for fn in module.outer_functions:
			self._global_env[fn] = calculus.TopLevelFunctionType(fn)
		for expr in module.main:
			result = self.visit(expr, self._global_env)
			if self._verbose:
				print(result.visit(Render()))
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
				
	def visit_TypeAlias(self, a: syntax.TypeAlias):
		if isinstance(a.body, syntax.TypeCall):
			dfn = a.body.ref.dfn
			body_type = self._global_env[dfn]
			if body_type is None:
				self._global_env[a] = None
				return
			elif isinstance(body_type, calculus.OpaqueType):
				self._global_env[a] = body_type
			elif isinstance(body_type, calculus.SumType):
				raise NotImplementedError
			else:
				raise NotImplementedError(type(body_type))
		else:
			assert isinstance(a.body, syntax.ArrowSpec)
			self._global_env[a] = None
	
	def visit_ImportForeign(self, d:syntax.ImportForeign):
		for group in d.groups:
			type_args = [calculus.TypeVariable() for _ in group.type_params]
			typ = ManifestBuilder(group.type_params, type_args).visit(group.type_expr)
			for sym in group.symbols:
				self._global_env[sym] = typ
	
	@staticmethod
	def visit_Literal(expr: syntax.Literal, env:ENV) -> calculus.SophieType:
		return _literal_type_map[type(expr.value)]

	def _call_site(self, fn_type, args, env:ENV) -> calculus.SophieType:
		def perform(fn:syntax.UserDefinedFunction, static_link:Optional[ENV]):
			formals = fn.params
			if len(formals) != len(arg_types):
				self._on_error(args, "The called function wants %d arguments, but got %d instead"%(len(formals), len(args)))
				return calculus.ERROR
			inner = dict(zip(fn_type.fn.params, arg_types))
			inner[STATIC_LINK] = static_link
			for sub in fn_type.fn.where:
				inner[sub] = calculus.NestedFunctionType(sub, inner)
			return self.visit(fn_type.fn.expr, inner)

		
		arg_types = [self.visit(a, env) for a in args]
		
		if any(t is calculus.ERROR for t in arg_types):
			return calculus.ERROR
		
		if isinstance(fn_type, calculus.ArrowType):
			# 1. Try to bind the actual argument to the formal argument,
			#    collecting variables along the way.
			binder = Binder()
			binder.visit(fn_type.arg, calculus.ProductType(arg_types))
			# 2. Return the arrow's result-type rewritten using the bindings thus found.
			if binder.ok:
				return fn_type.res.visit(Rewriter(binder.gamma))
			else:
				self._on_error(args, "These don't fit here. Also, you deserve a better error message.")
				return calculus.ERROR
		
		if isinstance(fn_type, calculus.TopLevelFunctionType):
			return perform(fn_type.fn, None)
		if isinstance(fn_type, calculus.NestedFunctionType):
			return perform(fn_type.fn, fn_type.static_env)
		
		raise NotImplementedError(type(fn_type))
	
	def visit_Call(self, site: syntax.Call, env: ENV) -> calculus.SophieType:
		fn_type = self.visit(site.fn_exp, env)
		if fn_type is calculus.ERROR: return calculus.ERROR
		return self._call_site(fn_type, site.args, env)
	
	def visit_BinExp(self, expr:syntax.BinExp, env:ENV) -> calculus.SophieType:
		return self._call_site(OPS[expr.glyph], (expr.lhs, expr.rhs), env)
	
	def visit_UnaryExp(self, expr: syntax.UnaryExp, env:ENV) -> calculus.SophieType:
		return self._call_site(OPS[expr.glyph], (expr.arg,), env)
		
	def visit_Lookup(self, lu:syntax.Lookup, env:ENV) -> calculus.SophieType:
		target = lu.ref.dfn
		if target.static_depth == 0:
			env = self._global_env
		else:
			for _ in range(lu.source_depth - target.static_depth):
				env = env[STATIC_LINK]
		typ = env[target]
		if isinstance(typ, calculus.UDFType) and not typ.fn.params:
			return self.visit(typ.fn.expr, env)
		else:
			return typ
		
	def visit_ExplicitList(self, el:syntax.ExplicitList, env:ENV) -> calculus.SumType:
		# Since there's guaranteed to be at least one value,
		# we should be able to glean a concrete type from it.
		# Having that, we should be able to get a union over them all.
		union_find = UnionFinder(calculus.BOTTOM)
		for e in el.elts:
			union_find.unify_with(self.visit(e, env))
			if union_find.died:
				self._on_error([el.elts[0], e],TYPE_MISMATCH)
				return calculus.ERROR
		element_type = union_find.result()
		return calculus.SumType(primitive.LIST, (element_type,))

	def visit_Cond(self, cond:syntax.Cond, env:ENV) -> calculus.SophieType:
		if_part_type = self.visit(cond.if_part, env)
		if if_part_type != primitive.literal_flag:
			self._on_error([cond.if_part], "The if-part doesn't make a flag, but "+if_part_type.visit(Render()))
			return calculus.ERROR
		union_find = UnionFinder(self.visit(cond.then_part, env))
		union_find.unify_with(self.visit(cond.else_part, env))
		if union_find.died:
			self._on_error([cond.then_part, cond.else_part], TYPE_MISMATCH)
			return calculus.ERROR
		return union_find.result()
	
	def visit_MatchExpr(self, mx:syntax.MatchExpr, env:ENV) -> calculus.SophieType:
		subject_type = self.visit(mx.subject.expr, env)
		if subject_type is calculus.ERROR: return calculus.ERROR
		assert isinstance(mx.variant, syntax.Variant)
		if (
				(isinstance(subject_type, calculus.SumType) and subject_type.variant is mx.variant) or
				(isinstance(subject_type, calculus.SubType) and subject_type.st.variant is mx.variant)
		):
			env[mx.subject] = subject_type
			union_find = UnionFinder(calculus.BOTTOM)
			for alt in mx.alternatives:
				union_find.unify_with(self.visit(alt.sub_expr, env))
				if union_find.died:
					self._on_error([alt.sub_expr],TYPE_MISMATCH)
					return calculus.ERROR
			return union_find.result()
		else:
			self._on_error([mx.subject], subject_type.visit(Render())+" does not work here.")
			return calculus.ERROR

class Render(calculus.TypeVisitor):
	""" Return a string representation of the term. """
	def __init__(self):
		self._var_names = {}
	def on_variable(self, v: calculus.TypeVariable):
		if v not in self._var_names:
			self._var_names[v] = "?%s" % _name_variable(len(self._var_names) + 1)
		return self._var_names[v]
	def on_opaque(self, o: calculus.OpaqueType):
		return o.symbol.nom.text
	def _generic(self, params:tuple[calculus.SophieType]):
		return "[%s]"%(",".join(t.visit(self) for t in params))
	def on_record(self, r: calculus.RecordType):
		return r.symbol.nom.text+self._generic(r.type_args)
	def on_sum(self, n: calculus.SumType):
		return n.variant.nom.text+self._generic(n.type_args)
	def on_tag_enum(self, e: calculus.EnumType):
		return e.st.nom.text
	def on_tag_record(self, t: calculus.TaggedRecord):
		return t.st.nom.text+self._generic(t.type_args)
	def on_arrow(self, a: calculus.ArrowType):
		return a.arg.visit(self)+"->"+a.res.visit(self)
	def on_product(self, p: calculus.ProductType):
		return "(%s)"%(",".join(t.visit(self) for t in p.fields))
	def on_udf(self, f: calculus.UDFType):
		return "<%s>"%f.fn.nom.text
	def on_bottom(self):
		return "?"
	def on_error_type(self):
		return "-/-"

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
