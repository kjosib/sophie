"""
Sort of like an evaluator, but for types.
Replaces the old type-inference pass.

The idea here is to run the type-level program before running the value-level program.
If the type-level program computes a type, then the value-level program is certainly
well-typed with that type. Otherwise, the value-level program is at serious risk of
experiencing a type-error in practice.

This module represents one straightforward type-level execution mechanism.
The type side of things can be call-by-value, which is a bit easier I think.
The tricky bit is (mutually) recursive functions.
"""
from typing import Iterable, Sequence
from boozetools.support.foundation import Visitor

from .. import ontology, syntax, primitive, diagnostics
from . import calculus
from .calculus import ENV

# A couple useful keys for what's fast becoming an activation record:
STATIC_LINK = object()
CODE_SOURCE = object()

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
		
	def _make_product(self, formals:Iterable[syntax.ARGUMENT_TYPE]) -> calculus.ProductType:
		return calculus.ProductType(map(self.visit, formals)).exemplar()
		
	def visit_RecordSpec(self, rs:syntax.RecordSpec) -> calculus.ProductType:
		# This is sort of a handy special case: Things use it to build constructor arrows.
		return self._make_product(field.type_expr for field in rs.fields)
	
	def visit_TypeCall(self, tc:syntax.TypeCall) -> calculus.SophieType:
		dfn = tc.ref.dfn
		if isinstance(dfn, syntax.TypeParameter):
			return self._bind[dfn]
		if isinstance(dfn, syntax.Opaque):
			return calculus.OpaqueType(dfn).exemplar()
		args = [self.visit(a) for a in tc.arguments]
		if isinstance(dfn, syntax.Record):
			return calculus.RecordType(dfn, args).exemplar()
		if isinstance(dfn, syntax.Variant):
			return calculus.SumType(dfn, args).exemplar()
		if isinstance(dfn, syntax.TypeAlias):
			return ManifestBuilder(dfn.parameters,args).visit(dfn.body)
		raise NotImplementedError(type(dfn))
	
	def visit_ArrowSpec(self, spec:syntax.ArrowSpec):
		return calculus.ArrowType(self._make_product(spec.lhs), self.visit(spec.rhs))

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
		return self._gamma.get(v, calculus.BOTTOM)

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
	
	def bind(self, formal:calculus.SophieType, actual:calculus.SophieType):
		if actual is calculus.BOTTOM:
			return
		else:
			self.visit(formal, actual)
	
	def visit_TypeVariable(self, formal:calculus.TypeVariable, actual:calculus.SophieType):
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
		return [self.bind(f, a) for f, a in zip(formal, actual)]
	
	def visit_ProductType(self, formal:calculus.ProductType, actual:calculus.SophieType):
		if not isinstance(actual, calculus.ProductType):
			return self.fail()
		if formal.number == actual.number:
			return
		if len(formal.fields) != len(actual.fields):
			return self.fail()
		self.parallel(formal.fields, actual.fields)
		
	def visit_OpaqueType(self, formal:calculus.OpaqueType, actual:calculus.SophieType):
		if formal.number == actual.number:
			return
		else:
			self.fail()
	
	def visit_SumType(self, formal:calculus.SumType, actual:calculus.SophieType):
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
	
	def visit_RecordType(self, formal:calculus.RecordType, actual:calculus.SophieType):
		if isinstance(actual, calculus.RecordType) and formal.symbol is actual.symbol:
			self.parallel(formal.type_args, actual.type_args)
		else:
			self.fail()

class UnionFinder(Visitor):
	def __init__(self, prototype:calculus.SophieType):
		self._prototype = prototype
		self.died = False
	def result(self):
		return self._prototype
	def unify_with(self, that):
		if self._prototype is not calculus.ERROR:
			union = self.do(self._prototype, that)
			if union is calculus.ERROR and that is not calculus.ERROR:
				print("Failed to unify:")
				print(self._prototype)
				print(that)
			self._prototype = union
	
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
	
	def visit_SumType(self, this:calculus.SumType, that:calculus.SophieType):
		if isinstance(that, calculus.SumType):
			if this.variant is that.variant:
				type_args = self.parallel(this.type_args, that.type_args)
				return calculus.SumType(this.variant, type_args)
		elif isinstance(that, calculus.TaggedRecord):
			if this.variant is that.st.variant:
				type_args = self.parallel(this.type_args, that.type_args)
				return calculus.SumType(this.variant, type_args)
		elif isinstance(that, calculus.EnumType):
			if this.variant is that.st.variant:
				return this
			
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
			return self.visit_SumType(that, this)
		
	def visit_EnumType(self, this:calculus.EnumType, that:calculus.SophieType):
		if isinstance(that, calculus.SumType):
			return self.visit_SumType(that, this)
		elif isinstance(that, calculus.TaggedRecord):
			return self.visit_TaggedRecord(that, this)
		elif isinstance(that, calculus.EnumType):
			if this.st.variant is that.st.variant:
				type_args = tuple(calculus.BOTTOM for _ in this.st.variant.parameters)
				return calculus.SumType(this.st.variant, type_args)

	
	@staticmethod
	def visit__Error(this:calculus.ERROR, that:calculus.SophieType):
		return this

class DeductionEngine(Visitor):
	def __init__(self, report:diagnostics.Report, verbose:bool):
		self._report = report  # .on_error("Checking Types")
		self._verbose = verbose
		self._types = { ot.symbol: ot for ot in _literal_type_map.values() }
		self._constructors : dict[syntax.Symbol, calculus.SophieType] = {}
		self._ffi = {}
		self._memo = {}
		self._recursion = {}
		self._source_path = {}
	
	def visit_Module(self, module:syntax.Module, source_path):
		for td in module.types: self.visit(td)
		for fi in module.foreign: self.visit(fi)
		for fn in module.all_functions: self._source_path[fn] = source_path
		env = {CODE_SOURCE:source_path}
		for expr in module.main:
			result = self.visit(expr, env)
			if self._verbose:
				print(result)
		pass
	
	def visit_Record(self, r: syntax.Record):
		type_args = [calculus.TypeVariable() for _ in r.parameters]
		self._types[r] = calculus.RecordType(r, type_args)
		arg = ManifestBuilder(r.parameters, type_args).visit(r.spec)
		self._constructors[r] = calculus.ArrowType(arg, self._types[r])
	
	def visit_Variant(self, v: syntax.Variant):
		type_args = [calculus.TypeVariable() for _ in v.parameters]
		self._types[v] = calculus.SumType(v, type_args)
		builder = ManifestBuilder(v.parameters, type_args)
		for st in v.subtypes:
			if st.body is None:
				self._constructors[st] = calculus.EnumType(st)
			elif isinstance(st.body, syntax.RecordSpec):
				arg = builder.visit(st.body)
				res = calculus.TaggedRecord(st, type_args)
				self._constructors[st] = calculus.ArrowType(arg, res)
				
	def visit_TypeAlias(self, a: syntax.TypeAlias):
		type_args = [calculus.TypeVariable() for _ in a.parameters]
		self._types[a] = it = ManifestBuilder(a.parameters, type_args).visit(a.body)
		if isinstance(it, calculus.RecordType):
			formals = self._types[it.symbol].type_args
			original = self._constructors[it.symbol]
			gamma = dict(zip(formals, it.type_args))
			self._constructors[a] = original.visit(Rewriter(gamma))
	
	def visit_ImportForeign(self, d:syntax.ImportForeign):
		for group in d.groups:
			type_args = [calculus.TypeVariable() for _ in group.type_params]
			typ = ManifestBuilder(group.type_params, type_args).visit(group.type_expr)
			for sym in group.symbols:
				self._ffi[sym] = typ
	
	@staticmethod
	def visit_Literal(expr: syntax.Literal, env:ENV) -> calculus.SophieType:
		return _literal_type_map[type(expr.value)]
	
	def _apply(self, fn:syntax.UserDefinedFunction, env:ENV) -> calculus.SophieType:
		# The part where memoization must happen.
		mk = _memo_key(fn, env)
		if mk in self._memo:
			return self._memo[mk]
		elif mk in self._recursion:
			self._recursion[mk] = True
			return calculus.BOTTOM
		else:
			self._recursion[mk] = False
			self._memo[mk] = self.visit(fn.expr, env)
			if self._recursion.pop(mk):
				prior = calculus.BOTTOM
				while prior != self._memo[mk]:
					prior = self._memo[mk]
					self._memo[mk] = self.visit(fn.expr, env)
		return self._memo[mk]
	
	def _call_site(self, fn_type, args:Sequence[ontology.Expr], env:ENV) -> calculus.SophieType:
		arg_types = [self.visit(a, env) for a in args]
		if any(t is calculus.ERROR for t in arg_types):
			return calculus.ERROR
		
		if isinstance(fn_type, calculus.ArrowType):
			assert isinstance(fn_type.arg, calculus.ProductType)  # Maybe not forever, but now.
			arity = len(fn_type.arg.fields)
			if arity != len(args):
				self._report.wrong_arity(env[CODE_SOURCE], arity, args)
				return calculus.ERROR
			
			binder = Binder()
			for expr, need, got in zip(args, fn_type.arg.fields, arg_types):
				binder.bind(need, got)
				if not binder.ok:
					self._report.bad_type(env[CODE_SOURCE], expr, need, got)
					return calculus.ERROR

			# 2. Return the arrow's result-type rewritten using the bindings thus found.
			return fn_type.res.visit(Rewriter(binder.gamma))
		
		elif isinstance(fn_type, calculus.UDFType):
			formals = fn_type.fn.params
			if len(formals) != len(args):
				self._report.wrong_arity(env[CODE_SOURCE], len(formals), args)
				return calculus.ERROR
			inner: ENV = dict(zip(formals, arg_types))
			inner[STATIC_LINK] = fn_type.static_env
			inner[CODE_SOURCE] = self._source_path[fn_type.fn]
			return self._apply(fn_type.fn, inner)
		
		raise NotImplementedError(type(fn_type))
	
	def visit_Call(self, site: syntax.Call, env: ENV) -> calculus.SophieType:
		fn_type = self.visit(site.fn_exp, env)
		if fn_type is calculus.ERROR: return calculus.ERROR
		return self._call_site(fn_type, site.args, env)
	
	def visit_BinExp(self, expr:syntax.BinExp, env:ENV) -> calculus.SophieType:
		return self._call_site(OPS[expr.glyph], (expr.lhs, expr.rhs), env)
	
	def visit_ShortCutExp(self, expr:syntax.ShortCutExp, env:ENV) -> calculus.SophieType:
		return self._call_site(OPS[expr.glyph], (expr.lhs, expr.rhs), env)
	
	def visit_UnaryExp(self, expr: syntax.UnaryExp, env:ENV) -> calculus.SophieType:
		return self._call_site(OPS[expr.glyph], (expr.arg,), env)
		
	def visit_Lookup(self, lu:syntax.Lookup, env:ENV) -> calculus.SophieType:
		target = lu.ref.dfn
		if isinstance(target, (syntax.TypeDeclaration, syntax.SubTypeSpec)):
			return self._constructors[target]  # Must succeed because of resolution.check_constructors
		if isinstance(target, syntax.FFI_Alias):
			return self._ffi[target]
		
		static_env = _chase(lu.source_depth, target, env)
		if isinstance(target, syntax.UserDefinedFunction):
			if target.params:
				return calculus.UDFType(target, static_env).exemplar()
			else:
				return self._apply(target, static_env)
		else:
			assert isinstance(target, (syntax.FormalParameter, syntax.Subject))
			return static_env[target]
		
	def visit_ExplicitList(self, el:syntax.ExplicitList, env:ENV) -> calculus.SumType:
		# Since there's guaranteed to be at least one value,
		# we should be able to glean a concrete type from it.
		# Having that, we should be able to get a union over them all.
		union_find = UnionFinder(calculus.BOTTOM)
		for e in el.elts:
			union_find.unify_with(self.visit(e, env))
			if union_find.died:
				self._report.type_mismatch(env[CODE_SOURCE], el.elts[0], e)
				return calculus.ERROR
		element_type = union_find.result()
		return calculus.SumType(primitive.LIST, (element_type,))

	def visit_Cond(self, cond:syntax.Cond, env:ENV) -> calculus.SophieType:
		if_part_type = self.visit(cond.if_part, env)
		if if_part_type is calculus.ERROR: return calculus.ERROR
		if if_part_type != primitive.literal_flag:
			self._report.bad_type(env[CODE_SOURCE], cond.if_part, primitive.literal_flag, if_part_type)
			return calculus.ERROR
		union_find = UnionFinder(self.visit(cond.then_part, env))
		union_find.unify_with(self.visit(cond.else_part, env))
		if union_find.died:
			self._report.type_mismatch(env[CODE_SOURCE], cond.then_part, cond.else_part)
			return calculus.ERROR
		return union_find.result()
	
	def visit_MatchExpr(self, mx:syntax.MatchExpr, env:ENV) -> calculus.SophieType:
		def try_everything(type_args:Sequence[calculus.SophieType]):
			union_find = UnionFinder(calculus.BOTTOM)
			for alt in mx.alternatives:
				env[mx.subject] = _hypothesis(alt.pattern.dfn, type_args)
				union_find.unify_with(self.visit(alt.sub_expr, env))
				if union_find.died:
					self._report.type_mismatch(env[CODE_SOURCE], mx.alternatives[0].sub_expr, alt.sub_expr)
					return calculus.ERROR
			return union_find.result()

		subject_type = self.visit(mx.subject.expr, env)
		if subject_type is calculus.ERROR: return calculus.ERROR
		assert isinstance(mx.variant, syntax.Variant)
		if isinstance(subject_type, calculus.SumType) and subject_type.variant is mx.variant:
			return try_everything(subject_type.type_args)
		elif subject_type is calculus.BOTTOM:
			return try_everything([calculus.BOTTOM]*len(mx.variant.parameters))
		elif isinstance(subject_type, calculus.SubType) and subject_type.st.variant is mx.variant:
			branch = mx.dispatch.get(subject_type.st.nom.text, mx.otherwise)
			env[mx.subject] = subject_type
			return self.visit(branch, env)
		else:
			self._report.bad_type(env[CODE_SOURCE], mx.subject.expr, mx.variant, subject_type)
			return calculus.ERROR

	def visit_FieldReference(self, fr:syntax.FieldReference, env:ENV) -> calculus.SophieType:
		lhs_type = self.visit(fr.lhs, env)
		if isinstance(lhs_type, calculus.RecordType):
			spec = lhs_type.symbol.spec
			parameters = lhs_type.symbol.parameters
		elif isinstance(lhs_type, calculus.TaggedRecord):
			spec = lhs_type.st.body
			parameters = lhs_type.st.variant.parameters
		elif lhs_type is calculus.BOTTOM:
			return calculus.BOTTOM
		else:
			self._report.type_has_no_fields(env[CODE_SOURCE], fr, lhs_type)
			return calculus.ERROR
		try:
			field_spec = spec.field_space[fr.field_name.text]
		except KeyError:
			self._report.record_lacks_field(env[CODE_SOURCE], fr, lhs_type)
			return calculus.ERROR
		assert isinstance(field_spec, syntax.FormalParameter), field_spec
		return ManifestBuilder(parameters, lhs_type.type_args).visit(field_spec.type_expr)

def _hypothesis(st:ontology.Symbol, type_args:Sequence[calculus.SophieType]) -> calculus.SubType:
	assert isinstance(st, syntax.SubTypeSpec)
	body = st.body
	if body is None:
		return calculus.EnumType(st)
	if isinstance(body, syntax.RecordSpec):
		return calculus.TaggedRecord(st, type_args)

def _chase(source_depth:int, target:ontology.Symbol, env:ENV):
	for _ in range(source_depth - target.static_depth):
		env = env[STATIC_LINK]
	return env

def _memo_key(fn:syntax.UserDefinedFunction, env:ENV):
	# The given environment contains the function's formal parameters.
	# It is thus one step deeper than the function's own static depth.
	source_depth = fn.static_depth + 1
	# This next step is unsound, but it's a temporary hack until I write a proper analysis pass:
	memo_symbols = fn.params
	# Now to the business at hand:
	memo_types = tuple(_chase(source_depth, p, env)[p].number for p in memo_symbols)
	return fn, memo_types
