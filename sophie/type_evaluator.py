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

from . import ontology, syntax, primitive, diagnostics
from .resolution import DependencyPass
from .calculus import (
	ENV, SophieType, TypeVisitor,
	OpaqueType, ProductType, ArrowType, TypeVariable,
	RecordType, SumType, SubType, TaggedRecord, EnumType,
	UDFType,
	BOTTOM, ERROR,
)

# A couple useful keys for what's fast becoming an activation record:
STATIC_LINK = "STATIC_LINK"
CODE_SOURCE = "CODE_SOURCE"

_literal_type_map : dict[type, OpaqueType] = {
	bool: primitive.literal_flag,
	str: primitive.literal_string,
	int: primitive.literal_number,
	float: primitive.literal_number,
}

OPS = {glyph:typ for glyph, (op, typ) in primitive.ops.items()}

class ManifestBuilder(Visitor):
	"""Converts the syntax of manifest types into corresponding type-calculus objects."""
	_bind : dict[syntax.TypeParameter:SophieType]
	
	def __init__(self, tps:Sequence[syntax.TypeParameter], type_args: list[SophieType]):
		self._bind = dict(zip(tps, type_args))
		
	def _make_product(self, formals:Iterable[syntax.ARGUMENT_TYPE]) -> ProductType:
		return ProductType(map(self.visit, formals)).exemplar()
		
	def visit_RecordSpec(self, rs:syntax.RecordSpec) -> ProductType:
		# This is sort of a handy special case: Things use it to build constructor arrows.
		return self._make_product(field.type_expr for field in rs.fields)
	
	def visit_TypeCall(self, tc:syntax.TypeCall) -> SophieType:
		dfn = tc.ref.dfn
		if isinstance(dfn, syntax.TypeParameter):
			return self._bind[dfn]
		if isinstance(dfn, syntax.Opaque):
			return OpaqueType(dfn).exemplar()
		args = [self.visit(a) for a in tc.arguments]
		if isinstance(dfn, syntax.Record):
			return RecordType(dfn, args).exemplar()
		if isinstance(dfn, syntax.Variant):
			return SumType(dfn, args).exemplar()
		if isinstance(dfn, syntax.TypeAlias):
			return ManifestBuilder(dfn.parameters,args).visit(dfn.body)
		raise NotImplementedError(type(dfn))
	
	def visit_ArrowSpec(self, spec:syntax.ArrowSpec):
		return ArrowType(self._make_product(spec.lhs), self.visit(spec.rhs))

class Rewriter(TypeVisitor):
	def __init__(self, gamma:dict):
		self._gamma = gamma
	def on_opaque(self, o: OpaqueType):
		return o
	def on_tag_record(self, t: TaggedRecord):
		return TaggedRecord(t.st, [a.visit(self) for a in t.type_args])
	def on_record(self, r: RecordType):
		return RecordType(r.symbol, [a.visit(self) for a in r.type_args])
	def on_variable(self, v: TypeVariable):
		return self._gamma.get(v, BOTTOM)

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
	
	def bind(self, formal: SophieType, actual: SophieType):
		if actual is BOTTOM:
			return
		else:
			self.visit(formal, actual)
	
	def visit_TypeVariable(self, formal: TypeVariable, actual: SophieType):
		if formal in self.gamma:
			union_finder = UnionFinder(self.gamma[formal])
			union_finder.unify_with(actual)
			if union_finder.died:
				self.fail()
			else:
				self.gamma[formal] = union_finder.result()
		else:
			self.gamma[formal] = actual
	
	def parallel(self, formal: Sequence[SophieType], actual: Sequence[SophieType]):
		assert len(formal) == len(actual)
		return [self.bind(f, a) for f, a in zip(formal, actual)]
	
	def visit_ProductType(self, formal: ProductType, actual: SophieType):
		if not isinstance(actual, ProductType):
			return self.fail()
		if formal.number == actual.number:
			return
		if len(formal.fields) != len(actual.fields):
			return self.fail()
		self.parallel(formal.fields, actual.fields)
		
	def visit_OpaqueType(self, formal: OpaqueType, actual: SophieType):
		if formal.number == actual.number:
			return
		else:
			self.fail()
	
	def visit_SumType(self, formal: SumType, actual: SophieType):
		if formal.number == actual.number:
			return
		elif isinstance(actual, SumType):
			if formal.variant is actual.variant:
				self.parallel(formal.type_args, actual.type_args)
			else:
				self.fail()
		elif isinstance(actual, TaggedRecord):
			if formal.variant is actual.st.variant:
				self.parallel(formal.type_args, actual.type_args)
			else:
				self.fail()
		elif isinstance(actual, EnumType):
			if formal.variant is actual.st.variant:
				pass
			else:
				self.fail()
		else:
			raise NotImplementedError(actual)
	
	def visit_RecordType(self, formal: RecordType, actual: SophieType):
		if isinstance(actual, RecordType) and formal.symbol is actual.symbol:
			self.parallel(formal.type_args, actual.type_args)
		else:
			self.fail()

class UnionFinder(Visitor):
	def __init__(self, prototype: SophieType):
		self._prototype = prototype
		self.died = False
	def result(self):
		return self._prototype
	def unify_with(self, that):
		if self._prototype is not ERROR:
			union = self.do(self._prototype, that)
			if union is ERROR and that is not ERROR:
				print("Failed to unify:")
				print(self._prototype)
				print(that)
			self._prototype = union
	
	def parallel(self, these:Sequence[SophieType], those:Sequence[SophieType]):
		assert len(these) == len(those)
		return [self.do(a, b) for a,b in zip(these, those)]
	
	def do(self, this: SophieType, that: SophieType):
		if this.number == that.number or that is BOTTOM: return this
		elif that is ERROR: return that
		else:
			typ = self.visit(this, that)
			if typ is None:
				self.died = True # Maybe highlight the specific breakage?
				return ERROR
			else:
				return typ

	@staticmethod
	def visit__Bottom(_, that: SophieType):
		return that
		
	@staticmethod
	def visit_OpaqueType(_, __):
		return None
		
	def visit_RecordType(self, this: RecordType, that: SophieType):
		if isinstance(that, RecordType) and this.symbol is that.symbol:
			return RecordType(this.symbol, self.parallel(this.type_args, that.type_args))
	
	def visit_SumType(self, this: SumType, that: SophieType):
		if isinstance(that, SumType):
			if this.variant is that.variant:
				type_args = self.parallel(this.type_args, that.type_args)
				return SumType(this.variant, type_args)
		elif isinstance(that, TaggedRecord):
			if this.variant is that.st.variant:
				type_args = self.parallel(this.type_args, that.type_args)
				return SumType(this.variant, type_args)
		elif isinstance(that, EnumType):
			if this.variant is that.st.variant:
				return this
			
	def visit_TaggedRecord(self, this: TaggedRecord, that: SophieType):
		if isinstance(that, TaggedRecord):
			if this.st is that.st:
				type_args = self.parallel(this.type_args, that.type_args)
				return TaggedRecord(this.st, type_args)
			if this.st.variant is that.st.variant:
				type_args = self.parallel(this.type_args, that.type_args)
				return SumType(this.st.variant, type_args)
		elif isinstance(that, EnumType):
			if this.st.variant is that.st.variant:
				return SumType(this.st.variant, this.type_args)
		elif isinstance(that, SumType):
			return self.visit_SumType(that, this)
		
	def visit_EnumType(self, this: EnumType, that: SophieType):
		if isinstance(that, SumType):
			return self.visit_SumType(that, this)
		elif isinstance(that, TaggedRecord):
			return self.visit_TaggedRecord(that, this)
		elif isinstance(that, EnumType):
			if this.st.variant is that.st.variant:
				type_args = tuple(BOTTOM for _ in this.st.variant.parameters)
				return SumType(this.st.variant, type_args)

	
	@staticmethod
	def visit__Error(this: ERROR, that: SophieType):
		return this

class DeductionEngine(Visitor):
	def __init__(self, report:diagnostics.Report, verbose:bool):
		self._report = report  # .on_error("Checking Types")
		self._verbose = verbose
		self._types = { ot.symbol: ot for ot in _literal_type_map.values() }
		self._constructors : dict[syntax.Symbol, SophieType] = {}
		self._ffi = {}
		self._memo = {}
		self._recursion = {}
		self._source_path = {}
		self._deps_pass = DependencyPass()
	
	def visit_Module(self, module:syntax.Module, source_path):
		self._deps_pass.visit(module)
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
		type_args = [TypeVariable() for _ in r.parameters]
		self._types[r] = RecordType(r, type_args)
		arg = ManifestBuilder(r.parameters, type_args).visit(r.spec)
		self._constructors[r] = ArrowType(arg, self._types[r])
	
	def visit_Variant(self, v: syntax.Variant):
		type_args = [TypeVariable() for _ in v.parameters]
		self._types[v] = SumType(v, type_args)
		builder = ManifestBuilder(v.parameters, type_args)
		for st in v.subtypes:
			if st.body is None:
				self._constructors[st] = EnumType(st)
			elif isinstance(st.body, syntax.RecordSpec):
				arg = builder.visit(st.body)
				res = TaggedRecord(st, type_args)
				self._constructors[st] = ArrowType(arg, res)
				
	def visit_TypeAlias(self, a: syntax.TypeAlias):
		type_args = [TypeVariable() for _ in a.parameters]
		self._types[a] = it = ManifestBuilder(a.parameters, type_args).visit(a.body)
		if isinstance(it, RecordType):
			formals = self._types[it.symbol].type_args
			original = self._constructors[it.symbol]
			gamma = dict(zip(formals, it.type_args))
			self._constructors[a] = original.visit(Rewriter(gamma))
	
	def visit_ImportForeign(self, d:syntax.ImportForeign):
		for group in d.groups:
			type_args = [TypeVariable() for _ in group.type_params]
			typ = ManifestBuilder(group.type_params, type_args).visit(group.type_expr)
			for sym in group.symbols:
				self._ffi[sym] = typ
	
	@staticmethod
	def visit_Literal(expr: syntax.Literal, env:ENV) -> SophieType:
		return _literal_type_map[type(expr.value)]
	
	def _apply(self, fn:syntax.UserDefinedFunction, env:ENV) -> SophieType:
		# The part where memoization must happen.
		memo_symbols = self._deps_pass.depends[fn]
		source_depth = fn.static_depth + bool(fn.params)  # By construction, this is the depth of the given env, above.
		memo_types = tuple(_chase(source_depth, p, env)[p].number for p in memo_symbols)
		memo_key = fn, memo_types
		if memo_key in self._memo:
			return self._memo[memo_key]
		elif memo_key in self._recursion:
			self._recursion[memo_key] = True
			return BOTTOM
		else:
			self._recursion[memo_key] = False
			self._memo[memo_key] = self.visit(fn.expr, env)
			if self._recursion.pop(memo_key):
				prior = BOTTOM
				while prior != self._memo[memo_key]:
					prior = self._memo[memo_key]
					self._memo[memo_key] = self.visit(fn.expr, env)
				if prior is BOTTOM:
					self._report.ill_founded_function(env[CODE_SOURCE], fn)
					
		return self._memo[memo_key]
	
	def _call_site(self, fn_type, args:Sequence[ontology.Expr], env:ENV) -> SophieType:
		arg_types = [self.visit(a, env) for a in args]
		if any(t is ERROR for t in arg_types):
			return ERROR
		
		if isinstance(fn_type, ArrowType):
			assert isinstance(fn_type.arg, ProductType)  # Maybe not forever, but now.
			arity = len(fn_type.arg.fields)
			if arity != len(args):
				self._report.wrong_arity(env[CODE_SOURCE], arity, args)
				return ERROR
			
			binder = Binder()
			for expr, need, got in zip(args, fn_type.arg.fields, arg_types):
				binder.bind(need, got)
				if not binder.ok:
					self._report.bad_type(env[CODE_SOURCE], expr, need, got)
					return ERROR

			# 2. Return the arrow's result-type rewritten using the bindings thus found.
			return fn_type.res.visit(Rewriter(binder.gamma))
		
		elif isinstance(fn_type, UDFType):
			formals = fn_type.fn.params
			if len(formals) != len(args):
				self._report.wrong_arity(env[CODE_SOURCE], len(formals), args)
				return ERROR
			inner: ENV = dict(zip(formals, arg_types))
			inner[STATIC_LINK] = fn_type.static_env
			inner[CODE_SOURCE] = self._source_path[fn_type.fn]
			return self._apply(fn_type.fn, inner)
		
		raise NotImplementedError(type(fn_type))
	
	def visit_Call(self, site: syntax.Call, env: ENV) -> SophieType:
		fn_type = self.visit(site.fn_exp, env)
		if fn_type is ERROR: return ERROR
		return self._call_site(fn_type, site.args, env)
	
	def visit_BinExp(self, expr:syntax.BinExp, env:ENV) -> SophieType:
		return self._call_site(OPS[expr.glyph], (expr.lhs, expr.rhs), env)
	
	def visit_ShortCutExp(self, expr:syntax.ShortCutExp, env:ENV) -> SophieType:
		return self._call_site(OPS[expr.glyph], (expr.lhs, expr.rhs), env)
	
	def visit_UnaryExp(self, expr: syntax.UnaryExp, env:ENV) -> SophieType:
		return self._call_site(OPS[expr.glyph], (expr.arg,), env)
		
	def visit_Lookup(self, lu:syntax.Lookup, env:ENV) -> SophieType:
		target = lu.ref.dfn
		if isinstance(target, (syntax.TypeDeclaration, syntax.SubTypeSpec)):
			return self._constructors[target]  # Must succeed because of resolution.check_constructors
		if isinstance(target, syntax.FFI_Alias):
			return self._ffi[target]
		
		static_env = _chase(lu.source_depth, target, env)
		if isinstance(target, syntax.UserDefinedFunction):
			if target.params:
				return UDFType(target, static_env).exemplar()
			else:
				return self._apply(target, static_env)
		else:
			assert isinstance(target, (syntax.FormalParameter, syntax.Subject))
			return static_env[target]
		
	def visit_ExplicitList(self, el:syntax.ExplicitList, env:ENV) -> SumType:
		# Since there's guaranteed to be at least one value,
		# we should be able to glean a concrete type from it.
		# Having that, we should be able to get a union over them all.
		union_find = UnionFinder(BOTTOM)
		for e in el.elts:
			union_find.unify_with(self.visit(e, env))
			if union_find.died:
				self._report.type_mismatch(env[CODE_SOURCE], el.elts[0], e)
				return ERROR
		element_type = union_find.result()
		return SumType(primitive.LIST, (element_type,))

	def visit_Cond(self, cond:syntax.Cond, env:ENV) -> SophieType:
		if_part_type = self.visit(cond.if_part, env)
		if if_part_type is ERROR: return ERROR
		if if_part_type != primitive.literal_flag:
			self._report.bad_type(env[CODE_SOURCE], cond.if_part, primitive.literal_flag, if_part_type)
			return ERROR
		union_find = UnionFinder(self.visit(cond.then_part, env))
		union_find.unify_with(self.visit(cond.else_part, env))
		if union_find.died:
			self._report.type_mismatch(env[CODE_SOURCE], cond.then_part, cond.else_part)
			return ERROR
		return union_find.result()
	
	def visit_MatchExpr(self, mx:syntax.MatchExpr, env:ENV) -> SophieType:
		def try_everything(type_args:Sequence[SophieType]):
			union_find = UnionFinder(BOTTOM)
			for alt in mx.alternatives:
				env[mx.subject] = _hypothesis(alt.pattern.dfn, type_args)
				union_find.unify_with(self.visit(alt.sub_expr, env))
				if union_find.died:
					self._report.type_mismatch(env[CODE_SOURCE], mx.alternatives[0].sub_expr, alt.sub_expr)
					return ERROR
			return union_find.result()

		subject_type = self.visit(mx.subject.expr, env)
		if subject_type is ERROR: return ERROR
		assert isinstance(mx.variant, syntax.Variant)
		if isinstance(subject_type, SumType) and subject_type.variant is mx.variant:
			return try_everything(subject_type.type_args)
		elif subject_type is BOTTOM:
			return try_everything([BOTTOM] * len(mx.variant.parameters))
		elif isinstance(subject_type, SubType) and subject_type.st.variant is mx.variant:
			branch = mx.dispatch.get(subject_type.st.nom.text, mx.otherwise)
			env[mx.subject] = subject_type
			return self.visit(branch, env)
		else:
			self._report.bad_type(env[CODE_SOURCE], mx.subject.expr, mx.variant, subject_type)
			return ERROR

	def visit_FieldReference(self, fr:syntax.FieldReference, env:ENV) -> SophieType:
		lhs_type = self.visit(fr.lhs, env)
		if isinstance(lhs_type, RecordType):
			spec = lhs_type.symbol.spec
			parameters = lhs_type.symbol.parameters
		elif isinstance(lhs_type, TaggedRecord):
			spec = lhs_type.st.body
			parameters = lhs_type.st.variant.parameters
		elif lhs_type is BOTTOM:
			return BOTTOM
		else:
			self._report.type_has_no_fields(env[CODE_SOURCE], fr, lhs_type)
			return ERROR
		try:
			field_spec = spec.field_space[fr.field_name.text]
		except KeyError:
			self._report.record_lacks_field(env[CODE_SOURCE], fr, lhs_type)
			return ERROR
		assert isinstance(field_spec, syntax.FormalParameter), field_spec
		return ManifestBuilder(parameters, lhs_type.type_args).visit(field_spec.type_expr)

def _hypothesis(st:ontology.Symbol, type_args:Sequence[SophieType]) -> SubType:
	assert isinstance(st, syntax.SubTypeSpec)
	body = st.body
	if body is None:
		return EnumType(st)
	if isinstance(body, syntax.RecordSpec):
		return TaggedRecord(st, type_args)

def _chase(source_depth:int, target:ontology.Symbol, env:ENV):
	for _ in range(source_depth - target.static_depth):
		env = env[STATIC_LINK]
	return env
