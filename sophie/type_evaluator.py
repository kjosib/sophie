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
from .ontology import Symbol
from . import syntax, primitive, diagnostics
from .resolution import RoadMap, TopDown
from .stacking import RootFrame, Activation
from .syntax import ValExpr
from .calculus import (
	TYPE_ENV,
	SophieType, TypeVisitor,
	OpaqueType, ProductType, ArrowType, TypeVariable,
	RecordType, SumType, SubType, TaggedRecord, EnumType,
	UDFType, InterfaceType, MessageType, UserTaskType,
	BOTTOM, ERROR, MESSAGE_READY_TO_SEND
)

class DependencyPass(TopDown):
	"""
	Solve the problem of which-all formal parameters does the value (and thus, type)
	of each user-defined function actually depend on. A simplistic answer would be to just
	use the parameters of the outermost function in a given nest. But inner functions
	might not be so generic as all that. Better precision here means smarter memoization,
	and thus faster type-checking.
	
	The nature of the algorithm is a transitive-closure / least-fixpoint operation.
	Preparation is by means of a tree-walk.
	
	Incidentally:
	Related analysis could determine the deepest non-local needed for a function,
	which could possibly allow some functions to run at a shallower static-depth
	than however they may appear in the source code. This could make the simple evaluator
	a bit faster by improving the lifetime of thunks.
	"""

	def __init__(self):
		# The interesting result:
		self.depends: dict[Symbol, set[syntax.FormalParameter]] = {}
		
		# All manner of temp data, which should be cleaned afterward:
		self._outer: dict[Symbol, set[syntax.FormalParameter]] = {}
		self._parent: dict[Symbol, Symbol] = {}
		self._outflows: dict[Symbol, set[Symbol]] = {}
		self._overflowing = set()
		
	def visit_Module(self, module: syntax.Module):
		self._walk_children(module.outer_functions, None)
		for expr in module.main:
			self.visit(expr, None)
		self._flow_dependencies()
		self._clean_up_after()

	def _prepare(self, sym:Symbol, parent):
		self._parent[sym] = parent
		self.depends[sym] = set()
		self._outer[sym] = set()
		self._outflows[sym] = set()

	def _walk_children(self, children: Sequence[syntax.UserFunction], parent):
		for child in children: self._prepare(child, parent)
		for child in children: self.visit_UserFunction(child, parent)

	def _insert(self, param:syntax.FormalParameter, env:Symbol):
		depends = self.depends[env]
		if self._is_in_scope(param, env) and param not in depends:
			depends.add(param)
			outer = self._outer[env]
			if self._is_non_local(param, env) and param not in outer:
				outer.add(param)
				self._overflowing.add(env)
	
	def _flow_dependencies(self):
		# This algorithm might not be theoretically perfect,
		# but for what it's about, it should be plenty fast.
		# And it's straightforward to understand.
		while self._overflowing:
			source = self._overflowing.pop()
			spill = self._outer[source]
			for destination in self._outflows[source]:
				for parameter in spill:
					self._insert(parameter, destination)
	
	def _clean_up_after(self):
		self._outer.clear()
		self._parent.clear()
		self._outflows.clear()
		self._overflowing.clear()

	def _is_in_scope(self, param:syntax.FormalParameter, env:Symbol):
		if env is None:
			return False
		if isinstance(env, syntax.UserFunction):
			return param in env.params or self._is_in_scope(param, self._parent[env])
		if isinstance(env, syntax.Subject):
			return self._is_in_scope(param, self._parent[env])
		assert False, type(env)

	@staticmethod
	def _is_non_local(param:syntax.FormalParameter, env:Symbol):
		if isinstance(env, syntax.UserFunction):
			return param not in env.params
		if isinstance(env, syntax.Subject):
			return True
		assert False, type(env)

	def visit_UserFunction(self, udf: syntax.UserFunction, env):
		# Params refer to themselves in this arrangement.
		# The "breadcrumb" serves to indicate the nearest enclosing symbol.
		self._parent[udf] = env
		self._walk_children(udf.where, udf)
		self.visit(udf.expr, udf)

	def visit_Lookup(self, lu: syntax.Lookup, env):
		self.visit(lu.ref, env)

	def _is_relevant(self, sym):
		return self._parent.get(sym) is not None

	def visit_PlainReference(self, ref: syntax.PlainReference, env:Symbol):
		dfn = ref.dfn
		if isinstance(dfn, syntax.FormalParameter):
			self._insert(dfn, env)
		elif self._is_relevant(dfn):
			self._outflows[dfn].add(env)
			
	def visit_QualifiedReference(self, ref:syntax.QualifiedReference, env:Symbol):
		pass

	def visit_MatchExpr(self, mx: syntax.MatchExpr, env:Symbol):
		self._prepare(mx.subject, env)
		self._outflows[mx.subject].add(env)
		self.visit(mx.subject.expr, env)
		for alt in mx.alternatives:
			self._walk_children(alt.where, mx.subject)
			self.visit(alt.sub_expr, mx.subject)
		if mx.otherwise is not None:
			self.visit(mx.otherwise, mx.subject)

class ArityError(Exception):
	pass

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
			return ManifestBuilder(dfn.type_params,args).visit(dfn.body)
		if isinstance(dfn, syntax.Interface):
			return InterfaceType(dfn, args).exemplar()
		raise NotImplementedError(type(dfn))
	
	def visit_ArrowSpec(self, spec:syntax.ArrowSpec):
		return ArrowType(self._make_product(spec.lhs), self.visit(spec.rhs))
	
	def visit_MessageSpec(self, ms:syntax.MessageSpec) -> SophieType:
		if ms.type_exprs:
			product = self._make_product(ms.type_exprs)
			return MessageType(product).exemplar()
		else:
			return MESSAGE_READY_TO_SEND

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
	def on_sum(self, s:SumType):
		return SumType(s.variant, [a.visit(self) for a in s.type_args])
	def on_arrow(self, a: ArrowType):
		return ArrowType(a.arg.visit(self), a.res.visit(self))
	def on_product(self, p: ProductType):
		return ProductType([f.visit(self) for f in p.fields])

class Binder(Visitor):
	"""
	Discovers (or fails) a substitution-of-variables (in the formal)
	which makes the formal accept the actual as an instance.
	"""
	def __init__(self, engine:"DeductionEngine", env:TYPE_ENV):
		self.gamma = {}
		self.ok = True
		self._engine = engine
		self._dynamic_link = env
		
	def fail(self):
		self.ok = False
	
	def bind(self, formal: SophieType, actual: SophieType):
		if actual in (BOTTOM, ERROR) or formal.number == actual.number:
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
		for f, a in zip(formal, actual): self.bind(f, a)
	
	def visit_ProductType(self, formal: ProductType, actual: SophieType):
		if not isinstance(actual, ProductType):
			return self.fail()
		if len(formal.fields) != len(actual.fields):
			return self.fail()
		self.parallel(formal.fields, actual.fields)
		
	def visit_ArrowType(self, formal: ArrowType, actual: SophieType):
		if isinstance(actual, ArrowType):
			# Use a nested type-environment to bind the arguments "backwards":
			# The argument to the formal-function must be acceptable to the actual-function.
			# The actual-function does its work on that set of bindings.
			save_gamma = self.gamma
			self.gamma = dict(save_gamma)  # Generally fairly small, so asymptotic is NBD here.
			self.bind(actual.arg, formal.arg)
			# The actual-result could contain type-variables from the formal side,
			# and these must be suitable as what the formal-result dictates.
			result = actual.res.visit(Rewriter(self.gamma))
			self.gamma = save_gamma
			self.bind(formal.res, result)
		elif isinstance(actual, UDFType):
			if len(actual.fn.params) != len(formal.arg.fields):
				self.fail()
			else:
				# TODO: Check types against FormalParameter contracts.
				result = self._engine.apply_UDF(actual, formal.arg.fields, self._dynamic_link)
				self.bind(formal.res, result)
		else:
			self.fail()
	
	def visit_OpaqueType(self, formal: OpaqueType, actual: SophieType):
		self.fail()
	
	def visit_SumType(self, formal: SumType, actual: SophieType):
		if isinstance(actual, SumType):
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
			self.fail()
	
	def visit_RecordType(self, formal: RecordType, actual: SophieType):
		if isinstance(actual, RecordType) and formal.symbol is actual.symbol:
			self.parallel(formal.type_args, actual.type_args)
		else:
			self.fail()
	
	def visit_MessageType(self, formal: MessageType, actual: SophieType):
		if isinstance(actual, MessageType):
			return self.visit(formal.arg, actual.arg)
		elif isinstance(actual, UserTaskType):
			if len(actual.udf_type.fn.params) != len(formal.arg.fields):
				self.fail()
			else:
				result = self._engine.apply_UDF(actual.udf_type, formal.arg.fields, self._dynamic_link)
				self.bind(primitive.literal_act, result)
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
			# TODO: Put the specific mismatch on report.
			# 	if union is ERROR and that is not ERROR:
			#		mumble.failed_to_unify(self._prototype, that)
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
				type_args = tuple(BOTTOM for _ in this.st.variant.type_params)
				return SumType(this.st.variant, type_args)

	def visit_UDFType(self, this:UDFType, that: SophieType):
		if isinstance(that, UDFType):
			if len(this.fn.params) == len(that.fn.params):
				# In principle, we take the intersection of the parameters to the union of the results.
				# In practice, that means some sort of "try both" logic,
				# and it's entirely too complicated for a five-minute hack session.
				raise NotImplementedError("To do.")
			else:
				return None  # Non-matching arity is a definite error.
		elif isinstance(that, ArrowType):
			# If trying to unify with arrow-type, then the arrow-type itself may be a suitable unifier.
			# Try the arrow-type as a binder, and if it works, then it's a win.
			raise NotImplementedError("To do.")
		else:
			return None  # Not a function.
	
	@staticmethod
	def visit__Error(this: ERROR, that: SophieType):
		return this

class DeductionEngine(Visitor):
	def __init__(self, roadmap:RoadMap, report:diagnostics.Report):
		# self._trace_depth = 0
		self._report = report  # .on_error("Checking Types")
		self._types = { ot.symbol: ot for ot in _literal_type_map.values() }
		self._types[primitive.literal_act.symbol]  = primitive.literal_act
		self._constructors : dict[syntax.Symbol, SophieType] = {}
		self._ffi : dict[syntax.FFI_Alias, SophieType] = {}
		self._memo = {}
		self._recursion = {}
		self._deps_pass = DependencyPass()
		self._list_symbol = roadmap.list_symbol
		self._udf = {}
		self._root = RootFrame()
		self.visit_Module(roadmap.preamble)
		for module in roadmap.each_module:
			self.visit_Module(module)
	
	def visit_Module(self, module:syntax.Module):
		self._report.info("Type-Check", module.source_path)
		self._deps_pass.visit_Module(module)
		for td in module.types: self.visit(td)
		for fi in module.foreign: self.visit(fi)
		local = Activation.for_module(self._root, module)
		for expr in module.main:
			self._report.trace(" -->", expr)
			result = self.visit(expr, local)
			self._report.info(result)
		self._root._bindings.update(local._bindings)

	###############################################################################

	def visit_Record(self, r: syntax.Record):
		type_args = [TypeVariable() for _ in r.type_params]
		self._types[r] = RecordType(r, type_args)
		arg = ManifestBuilder(r.type_params, type_args).visit(r.spec)
		self._constructors[r] = ArrowType(arg, self._types[r])
	
	def visit_Variant(self, v: syntax.Variant):
		type_args = [TypeVariable() for _ in v.type_params]
		self._types[v] = SumType(v, type_args)
		builder = ManifestBuilder(v.type_params, type_args)
		for st in v.subtypes:
			if st.body is None:
				self._constructors[st] = EnumType(st)
			elif isinstance(st.body, syntax.RecordSpec):
				arg = builder.visit(st.body)
				res = TaggedRecord(st, type_args)
				self._constructors[st] = ArrowType(arg, res)
				
	def visit_TypeAlias(self, a: syntax.TypeAlias):
		type_args = [TypeVariable() for _ in a.type_params]
		self._types[a] = it = ManifestBuilder(a.type_params, type_args).visit(a.body)
		if isinstance(it, RecordType):
			formals = self._types[it.symbol].type_args
			original = self._constructors[it.symbol]
			gamma = dict(zip(formals, it.type_args))
			self._constructors[a] = original.visit(Rewriter(gamma))
	
	def visit_Opaque(self, td:syntax.Opaque):
		self._types[td] = OpaqueType(td)
	
	def visit_Interface(self, i:syntax.Interface):
		type_args = [TypeVariable() for _ in i.type_params]
		self._types[i] = InterfaceType(i, type_args)

	###############################################################################

	def visit_ImportForeign(self, d:syntax.ImportForeign):
		for group in d.groups:
			type_args = [TypeVariable() for _ in group.type_params]
			typ = ManifestBuilder(group.type_params, type_args).visit(group.type_expr)
			for sym in group.symbols:
				self._ffi[sym] = typ

	###############################################################################

	@staticmethod
	def visit_Literal(expr: syntax.Literal, env:TYPE_ENV) -> SophieType:
		return _literal_type_map[type(expr.value)]
	
	def apply_UDF(self, fn_type:UDFType, arg_types:Sequence[SophieType], env:TYPE_ENV) -> SophieType:
		fn = fn_type.fn
		arity = len(fn.params)
		if arity != len(arg_types): raise ArityError
		inner = Activation.for_function(fn_type.static_env, fn, arg_types)
		return self.exec_UDF(fn, inner)
		
	def exec_UDF(self, fn:syntax.UserFunction, env:TYPE_ENV):
		# The part where memoization must happen.
		memo_symbols = self._deps_pass.depends[fn]
		assert all(isinstance(s, syntax.FormalParameter) for s in memo_symbols)
		memo_types = tuple(
			env.chase(p).fetch(p)  # .number
			for p in memo_symbols
		)
		memo_key = fn, memo_types
		if memo_key in self._memo:
			return self._memo[memo_key]
		elif memo_key in self._recursion:
			self._recursion[memo_key] = True
			# self._report.trace(">Recursive:", fn, dict(zip((s.nom.text for s in memo_symbols), memo_types)))
			return BOTTOM
		else:
			# TODO: check argument and return against declared contract.
			#       Could do this with a binder if FormalParam gets associated SophieType.
			#       Also, pass around judgements not just types.
			self._recursion[memo_key] = False
			self._memo[memo_key] = self.visit(fn.expr, env)
			if self._recursion.pop(memo_key):
				prior = BOTTOM
				while prior != self._memo[memo_key]:
					prior = self._memo[memo_key]
					self._memo[memo_key] = self.visit(fn.expr, env)
				if prior is BOTTOM:
					self._report.ill_founded_function(env, fn)
				# self._report.trace("<Resolved:", fn)
					
		return self._memo[memo_key]
	
	def _call_site(self, site: syntax.ValExpr, fn_type, args:Sequence[ValExpr], env:TYPE_ENV) -> SophieType:
		arg_types = [self.visit(a, env) for a in args]
		if ERROR in arg_types:
			return ERROR

		env.pc = site

		if isinstance(fn_type, ArrowType):
			assert isinstance(fn_type.arg, ProductType)  # Maybe not forever, but now.
			arity = len(fn_type.arg.fields)
			if arity != len(args):
				self._report.wrong_arity(env, site, arity, args)
				return ERROR
			
			binder = Binder(self, env)
			for expr, need, got in zip(args, fn_type.arg.fields, arg_types):
				binder.bind(need, got)
				if not binder.ok:
					self._report.bad_type(env, expr, need, got)
					return ERROR

			# 2. Return the arrow's result-type rewritten using the bindings thus found.
			return fn_type.res.visit(Rewriter(binder.gamma))
		
		elif isinstance(fn_type, UDFType):
			try:
				result = self.apply_UDF(fn_type, arg_types, env)
				# self._report.trace("     ", fn_type, tuple(arg_types), '-->', result)
				return result
			except ArityError:
				self._report.wrong_arity(env, site, len(fn_type.fn.params), args)
				return ERROR
			
		else:
			raise NotImplementedError(type(fn_type))
	
	def visit_Call(self, site: syntax.Call, env: TYPE_ENV) -> SophieType:
		fn_type = self.visit(site.fn_exp, env)
		if fn_type is ERROR: return ERROR
		return self._call_site(site, fn_type, site.args, env)
	
	def visit_BinExp(self, expr:syntax.BinExp, env:TYPE_ENV) -> SophieType:
		return self._call_site(expr, OPS[expr.glyph], (expr.lhs, expr.rhs), env)
	
	def visit_ShortCutExp(self, expr:syntax.ShortCutExp, env:TYPE_ENV) -> SophieType:
		return self._call_site(expr, OPS[expr.glyph], (expr.lhs, expr.rhs), env)
	
	def visit_UnaryExp(self, expr: syntax.UnaryExp, env:TYPE_ENV) -> SophieType:
		return self._call_site(expr, OPS[expr.glyph], (expr.arg,), env)
		
	def visit_Lookup(self, lu:syntax.Lookup, env:TYPE_ENV) -> SophieType:
		target = lu.ref.dfn
		if isinstance(target, (syntax.TypeDeclaration, syntax.SubTypeSpec)):
			return self._constructors[target]  # Must succeed because of resolution.check_constructors
		if isinstance(target, syntax.FFI_Alias):
			return self._ffi[target]
		
		static_env = env.chase(target)
		if isinstance(target, syntax.UserFunction):
			if target.params:
				return UDFType(target, static_env).exemplar()
			else:
				inner = Activation.for_function(static_env, target, ())
				return self.exec_UDF(target, inner)
		else:
			assert isinstance(target, (syntax.FormalParameter, syntax.Subject))
			return static_env.fetch(target)
		
	def visit_ExplicitList(self, el:syntax.ExplicitList, env:TYPE_ENV) -> SumType:
		# Since there's guaranteed to be at least one value,
		# we should be able to glean a concrete type from it.
		# Having that, we should be able to get a union over them all.
		union_find = UnionFinder(BOTTOM)
		for e in el.elts:
			union_find.unify_with(self.visit(e, env))
			if union_find.died:
				self._report.type_mismatch(env, el.elts[0], e)
				return ERROR
		element_type = union_find.result()
		return SumType(self._list_symbol, (element_type,))

	def visit_Cond(self, cond:syntax.Cond, env:TYPE_ENV) -> SophieType:
		if_part_type = self.visit(cond.if_part, env)
		if if_part_type is ERROR: return ERROR
		if if_part_type != primitive.literal_flag:
			self._report.bad_type(env, cond.if_part, primitive.literal_flag, if_part_type)
			return ERROR
		union_find = UnionFinder(self.visit(cond.then_part, env))
		union_find.unify_with(self.visit(cond.else_part, env))
		if union_find.died:
			self._report.type_mismatch(env, cond.then_part, cond.else_part)
			return ERROR
		return union_find.result()
	
	def visit_MatchExpr(self, mx:syntax.MatchExpr, env:TYPE_ENV) -> SophieType:
		def try_everything(type_args:Sequence[SophieType]):
			union_find = UnionFinder(BOTTOM)
			for alt in mx.alternatives:
				subtype_symbol = mx.namespace[alt.nom.key()]
				inner = Activation.for_subject(env, mx.subject)
				inner.assign(mx.subject,  _hypothesis(subtype_symbol, type_args))
				for subfn in alt.where: inner.declare(subfn)
				union_find.unify_with(self.visit(alt.sub_expr, inner))
				if union_find.died:
					self._report.type_mismatch(env, mx.alternatives[0].sub_expr, alt.sub_expr)
					return ERROR
			if mx.otherwise is not None:
				inner = Activation.for_subject(env, mx.subject)
				inner.assign(mx.subject, subject_type)
				union_find.unify_with(self.visit(mx.otherwise, inner))
				if union_find.died:
					self._report.type_mismatch(env, mx.alternatives[0].sub_expr, mx.otherwise)
					return ERROR
			return union_find.result()

		subject_type = self.visit(mx.subject.expr, env)
		if subject_type is ERROR:
			return ERROR

		if isinstance(subject_type, SumType):
			return try_everything(subject_type.type_args)
		
		elif subject_type is BOTTOM:
			return try_everything([BOTTOM] * len(mx.variant.type_params))
		
		elif isinstance(subject_type, SubType) and subject_type.st.variant is mx.variant:
			case_key = subject_type.st.nom.text
			branch = mx.dispatch.get(case_key, mx.otherwise)
			env.assign(mx.subject, subject_type)
			return self.visit(branch, env)
		
		else:
			self._report.bad_type(env, mx.subject.expr, mx.variant, subject_type)
			return ERROR

	def visit_FieldReference(self, fr:syntax.FieldReference, env:TYPE_ENV) -> SophieType:
		lhs_type = self.visit(fr.lhs, env)
		if isinstance(lhs_type, RecordType):
			spec = lhs_type.symbol.spec
			parameters = lhs_type.symbol.type_params
		elif isinstance(lhs_type, TaggedRecord):
			spec = lhs_type.st.body
			parameters = lhs_type.st.variant.type_params
		elif lhs_type is BOTTOM:
			# In principle the evaluator could make an observation / infer a constraint
			return lhs_type
		elif lhs_type is ERROR:
			# Complaint has already been issued.
			return lhs_type
		else:
			self._report.type_has_no_fields(env, fr, lhs_type)
			return ERROR
		try:
			field_spec = spec.field_space[fr.field_name.text]
		except KeyError:
			self._report.record_lacks_field(env, fr, lhs_type)
			return ERROR
		assert isinstance(field_spec, syntax.FormalParameter), field_spec
		return ManifestBuilder(parameters, lhs_type.type_args).visit(field_spec.type_expr)

	def visit_BindMethod(self, mr:syntax.BindMethod, env:TYPE_ENV) -> SophieType:
		lhs_type = self.visit(mr.receiver, env)
		if lhs_type is ERROR: return ERROR
		if isinstance(lhs_type, InterfaceType):
			try:
				ms = lhs_type.symbol.method_space[mr.method_name.key()]
			except KeyError:
				self._report.bad_message(env, mr, lhs_type)
				return ERROR
			else:
				assert isinstance(ms, syntax.MethodSpec)
				parameters = lhs_type.symbol.type_params
				builder = ManifestBuilder(parameters, lhs_type.type_args)
				if ms.type_exprs:
					args = ProductType(builder.visit(tx) for tx in ms.type_exprs)
					return ArrowType(args, primitive.literal_act)
				else:
					return primitive.literal_act
		else:
			self._report.bad_message(env, mr, lhs_type)
			return ERROR
	
	def visit_DoBlock(self, do:syntax.DoBlock, env:TYPE_ENV) -> SophieType:
		# A bit verbose to pick up all errors, not just the first.
		answer = primitive.literal_act
		for step in do.steps:
			env.pc = step
			step_type = self.visit(step, env)
			assert isinstance(step_type, SophieType)
			if step_type is ERROR: answer = ERROR
			elif step_type is BOTTOM:
				if answer is not ERROR:
					answer = BOTTOM
			elif step_type != primitive.literal_act:
				self._report.bad_type(env, step, primitive.literal_act, step_type)
				answer = ERROR
		return answer
	
	def visit_AsTask(self, at:syntax.AsTask, env:TYPE_ENV) -> SophieType:
		def is_act(t): return t.number == primitive.literal_act.number
		inner = self.visit(at.sub, env)
		if is_act(inner):
			return MESSAGE_READY_TO_SEND
		elif isinstance(inner, ArrowType) and is_act(inner.res):
			return MessageType(inner.arg).exemplar()
		elif isinstance(inner, UDFType):
			return UserTaskType(inner)
		else:
			self._report.bad_type(env, at.sub, "procedure", inner)
			return ERROR

def _hypothesis(st:Symbol, type_args:Sequence[SophieType]) -> SubType:
	assert isinstance(st, syntax.SubTypeSpec)
	body = st.body
	if body is None:
		return EnumType(st)
	if isinstance(body, syntax.RecordSpec):
		return TaggedRecord(st, type_args)

