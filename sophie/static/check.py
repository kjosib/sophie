"""

I want a new feature: Let's statically check the manifest type annotations
for *plausibility* before the detailed simulation. That way, even code that
isn't called is still checked, which is probably great in library context.

* A plausible function does nothing obviously wrong.
* A safe function obviously does nothing wrong.

"""
# ----------------------------------------------------------------

from typing import Sequence, Optional
from boozetools.support.foundation import Visitor
from .. import syntax
from ..ontology import Nom, TypeSymbol, SELF
from ..syntax import Subroutine, RecordSymbol, RecordTag, FormalParameter, TypeCase
from ..primitive import literal_type_map
from ..stacking import Frame, RootFrame, Activation, CRUMB
from ..diagnostics import Report
from ..resolution import RoadMap
from .domain import (
	SophieType, SymbolicType, ArrowType, Closure, DynamicDispatch, InferenceVariable,
	Special, Error, BOTTOM, is_equivalent, ACTION, MessageType, READY_MESSAGE,
	ParametricTask, ParametricTpl, ConcreteTpl, UDAType, ZERO_ARG_PROC,
)
from .manifest import translate, constructor, Translator
from .binding import PlausibleCover
from .promotion import PromotionFinder

TypeFrame = Frame[SophieType]


class TypeMemo:
	def __init__(self, initial_guess):
		self.is_solved = False
		self.is_on_stack = False
		self.sophie_type = initial_guess
	def __str__(self): return "[Memo: solved=%s, stacked=%s, type=%s]"%(self.is_solved, self.is_on_stack, self.sophie_type)

def _initial_guess(sub:Subroutine):
	if isinstance(sub, syntax.UserFunction): return BOTTOM
	if isinstance(sub, syntax.UserProcedure): return ACTION
	assert False, type(sub)  # Did we invent something new?

class TypeChecker(Visitor):
	_global: TypeFrame
	_well_known: dict[str, SymbolicType]
	_conditional: ArrowType
	_logical: ArrowType
	_manifest_params: dict[FormalParameter, SophieType]
	_manifest_result: dict[Subroutine, SophieType]
	_memo: dict[tuple, TypeMemo]
	_tos: TypeFrame

	def __init__(self, report: Report):
		self._report = report
	
	def _reset(self):
		self._well_known = {}
		self._manifest_params = {}
		self._manifest_result = {}
		self._unary_types = {}
		self._binary_types = {}
		self._memo = {}
		self._global = self._tos = RootFrame()

	def push(self, breadcrumb:CRUMB, memo_key:tuple):
		self._tos = Activation(self._tos, breadcrumb)
		self._tos.memo_key = memo_key

	def pop(self, memo_key:tuple):
		assert self._tos.memo_key == memo_key
		self._tos = self._tos.dynamic_link

	def _note_cycle_in_call_graph(self, memo_key):
		"""
		Every frame in the cycle (save for the outermost) gets
		marked is_recursion_body so it won't trust its result.
		The outermost frame gets tagged as a recursive head.
		
		The observant and contemplative reader will recognize
		this as way to indicate strongly-connected components
		(and their roots) in the call-graph while constrained
		to discover that call-graph as we go along and take
		several trips through some of the same nodes.
		
		It may not the be most theoretically-efficient algorithm,
		but it's practical enough and it gets the job done.
		"""
		frame = self._tos
		# Mark some stack as participating in mutual recursion:
		while frame.memo_key != memo_key:
			frame.is_recursion_body = True
			frame = frame.dynamic_link
		# At this point, we've found the frame at the head of the (current) recursion.
		# Mark it is_recursion_head. Note that is_recursion_body takes precedence.
		frame.is_recursion_head = True
	
	def _found_cycle_in_call_graph(self) -> bool:
		return hasattr(self._tos, "cycle")
	
	def check(self, expr) -> SophieType:
		# Housekeeping around the generic visitation protocol
		# so that error messages remain reasonably localized.
		note = self._tos.pc
		self._tos.pc = expr
		typ = self.visit(expr)
		self._tos.pc = note
		return typ if isinstance(typ, SophieType) else self.drat("Failed to return a type from %r"%type(expr))
	
	def tour(self, items) -> None:
		for i in items: self.visit(i)
	
	def check_program(self, roadmap: RoadMap):
		self._reset()
		self._report.info("Type-Check", roadmap.preamble.source_path)
		self.tour(roadmap.preamble.types)
		self._note_well_known_types(roadmap)
		self.prepare_built_in_generics()
		self.check_terms(roadmap.preamble)
		for module in roadmap.each_module:
			self._report.info("Type-Check", module.source_path)
			self.tour(module.types)
			self.check_terms(module)
		pass
	
	def _note_well_known_types(self, roadmap: RoadMap):
		def slurp(layer, names):
			for name in  names:
				symbol = layer.symbol(name)
				assert isinstance(symbol, TypeSymbol)
				type_args = InferenceVariable.several(symbol.type_arity())
				self._well_known[name] = SymbolicType(symbol, type_args)
		
		self._well_known.clear()
		preamble_scope = roadmap.export_scopes[roadmap.preamble]
		slurp(preamble_scope.types, ("number", "string", "flag", "order"))
		slurp(preamble_scope.terms, ("nil", "cons", "less", "same", "more"))
		
		flag = self._well_known["flag"]
		var = InferenceVariable()
		self._conditional = ArrowType((flag, var, var), var)
		self._logical = ArrowType((flag, flag), flag)
	
	def _install_operator(self, glyph:str, case:SophieType):
		arity = case.value_arity()
		if 2 == arity: where = self._binary_types
		elif 1 == arity: where = self._unary_types
		else: return self.drat("How'd we get here?")
		if glyph not in where: where[glyph] = DynamicDispatch(glyph, arity)
		where[glyph].append_case(case, self._report)
	
	def prepare_built_in_generics(self):
		def bin_op(src, dst):
			src_type = self._well_known[src]
			return ArrowType((src_type, src_type), self._well_known[dst])
		math_op = bin_op("number", "number")
		for op in '^ * / DIV MOD + -'.split():
			self._install_operator(op, math_op)
		def multi(ops, op_typ):
			for glyph in ops.split(): self._install_operator(glyph, op_typ)
		
		multi("== !=", bin_op("flag", "flag"))
		for ot in "number", "string":
			multi("== != <= < > >=", bin_op(ot, "flag"))
			self._install_operator("<=>", bin_op(ot, "order"))
		for op, ot in (("-", "number"), ("NOT", "flag")):
			self._install_operator(op, ArrowType([self._well_known[ot]], self._well_known[ot]))
		pass

	def check_terms(self, module: syntax.Module):
		assert self._tos is self._global
		self.tour(module.foreign)
		for sub in (module.all_fns + module.all_procs):
			self.make_manifest(sub)
		self.tour(module.actors)
		self.install_closures(module.top_subs)
		for op in module.user_operators:
			self._install_operator(op.nom.key(), self._global.fetch(op))
		self.push(module,())
		module.performative = list(map(self.display, module.main))
		self.pop(())
		assert self._tos is self._global
	
	def make_manifest(self, sub:syntax.Subroutine):
		translator = Translator({})
		for p in sub.params: self._manifest_params[p] = translator.visit(p.type_expr)
		self._manifest_result[sub] = translator.visit(sub.result_type_expr)
	
	def visit_OpaqueSymbol(self, type_dfn: syntax.OpaqueSymbol):
		# An opaque type has no associated term.
		pass
	
	def visit_RecordSymbol(self, td: syntax.RecordSymbol):
		self._global.assign(td, constructor(td.type_params, td.spec, td))

	def visit_VariantSymbol(self, td: syntax.VariantSymbol):
		for case in td.type_cases:
			self._global.assign(case, self.check(case))

	@staticmethod
	def visit_EnumTag(case: syntax.EnumTag):
		typ_args = (BOTTOM,) * len(case.variant.type_params)
		return SymbolicType(case, typ_args)
	
	@staticmethod
	def visit_RecordTag(case:syntax.RecordTag):
		return constructor(case.variant.type_params, case.spec, case)
	
	def visit_TypeAliasSymbol(self, td: syntax.TypeAliasSymbol):
		# A type alias has no associated term.
		pass

	def visit_RoleSymbol(self, td: syntax.RoleSymbol):
		# A role has no associated term.
		pass

	def visit_ImportForeign(self, d: syntax.ImportForeign):
		for group in d.groups:
			sophie_type = translate(group.type_params, group.type_expr)
			for symbol in group.symbols:
				self._global.assign(symbol, sophie_type)
	
	def visit_UserActor(self, actor:syntax.UserActor):
		translator = Translator({})
		for p in actor.fields: self._manifest_params[p] = translator.visit(p.type_expr)
		if actor.fields: tpl = ParametricTpl(actor)
		else: tpl = ConcreteTpl(actor, ())
		self._global.assign(actor, tpl)
	
	def visit_Call(self, site: syntax.Call) -> SophieType:
		fn_type = self.check(site.fn_exp)
		if fn_type.is_error() or fn_type is BOTTOM: return fn_type
		return self.call_site(site.fn_exp, fn_type, site.args)

	def visit_BinExp(self, expr: syntax.BinExp) -> SophieType:
		dynamic = self._binary_types[expr.op.text]
		return self.call_site(expr, dynamic, (expr.lhs, expr.rhs))

	def visit_ShortCutExp(self, expr: syntax.ShortCutExp) -> SophieType:
		return self.call_site(expr, self._logical, (expr.lhs, expr.rhs))

	def visit_UnaryExp(self, expr: syntax.UnaryExp) -> SophieType:
		dynamic = self._unary_types[expr.op.text]
		return self.call_site(expr, dynamic, (expr.arg,))
	
	def call_site(self, site:syntax.ValueExpression, callee, args: Sequence[syntax.ValueExpression]) -> SophieType:
		# Callee is surely not error (or inference variable) at this point.
		
		# Begin by checking arity:
		need, got = callee.value_arity(), len(args)
		if need < 0:
			self._report.not_callable(self._tos, site, callee)
			return Error("255: Not Callable")
		if need != got:
			self._report.wrong_arity(self._tos, site, need, got)
			return Error("258: Wrong Arity")
		
		# Assuming correct number of params, work out their types:
		actual_types = []
		for a in args:
			at = self.check(a)
			if at.is_error(): return at
			actual_types.append(at)
		
		# If callee is dynamic-dispatch, figure out which case applies:
		if isinstance(callee, DynamicDispatch):
			# NB: reassign `callee` and fall through
			if BOTTOM in actual_types: return BOTTOM
			callee = callee.dispatch(actual_types)
			if callee is None:
				self._report.no_applicable_method(self._tos, actual_types)
				return Error("274: No Suitable Method")
		
		# (How to) Bind formal parameters to actual types:
		def bind(engine, manifest, continuation) -> SophieType:
			cover = PlausibleCover(engine)
			for expr, formal, actual in zip(args, manifest, actual_types):
				cover.bind(formal, actual)
				if not cover.is_ok():
					self._report.bad_argument(self._tos, expr, cover.mismatch)
					return Error("283: Bad Argument")
			return continuation(cover)
		
		def manifest_in(params:Sequence[syntax.FormalParameter]):
			return [self._manifest_params[p] for p in params]
		
		def a_la_closure(closure:Closure):
			continuation = lambda cover: self.apply_closure(closure, actual_types, cover)
			return bind(None, manifest_in(closure.sub.params), continuation)
		
		# Work out the result type:
		if isinstance(callee, ArrowType):
			return bind(self, callee.arg_types, lambda cover: callee.result_type.rewrite(cover.bindings))
		elif isinstance(callee, Closure):
			return a_la_closure(callee)
		elif isinstance(callee, MessageType):
			return bind(self, callee.arg_types, lambda _: READY_MESSAGE)
		elif isinstance(callee, ParametricTpl):
			# CHANGEME: For now, it works more like a closure. Eventually, more like an arrow / record-constructor.
			dfn = callee.actor_dfn
			return bind(None, manifest_in(dfn.fields), lambda _:ConcreteTpl(dfn, actual_types))
		elif isinstance(callee, ParametricTask):
			return _dispatchable(a_la_closure(callee.closure))
		else:
			self.drat("Dunno how to apply a %s"%type(callee))
			return Error("308")
	
	def apply_closure(self, callee:Closure, actual_types, context:PlausibleCover) -> SophieType:
		memo_key = callee.memo_key(actual_types)
		if memo_key not in self._memo:
			self._memo[memo_key] = TypeMemo(_initial_guess(callee.sub))
		memo = self._memo[memo_key]
		if memo.is_solved: return memo.sophie_type
		elif memo.is_on_stack:
			self._note_cycle_in_call_graph(memo_key)
			return memo.sophie_type
		# Otherwise, we do this the hard way.
		
		self.push(callee.sub, memo_key)
		memo.is_on_stack = True
		
		while not memo.is_solved:
			prior_guess = memo.sophie_type
			memo.sophie_type = self._eval_closure(callee, actual_types, context)
			if memo.sophie_type.is_error(): break
			if self._tos.is_recursion_body: break
			if self._tos.is_recursion_head:
				# This is the root of cycle. We are done when a run
				# yields the same result as the previous best-guess.
				memo.is_solved = is_equivalent(prior_guess, memo.sophie_type)
			else: memo.is_solved = True
		
		if memo.is_solved and memo.sophie_type is BOTTOM and BOTTOM not in actual_types:
			self._report.ill_founded_function(self._tos, callee.sub)
			memo.sophie_type = Error("325: Ill-founded function")
		
		memo.is_on_stack = False
		self.pop(memo_key)
		return memo.sophie_type
	
	def _eval_closure(self, callee:Closure, actual_types, context) -> SophieType:
		sub = callee.sub
		inner = self._tos
		inner.update(zip(sub.params, actual_types))
		inner.update(callee.captured)
		self.install_closures(sub.where)
		result = self.check(sub.expr)
		if result.is_error(): return result
		if sub.result_type_expr:
			context.visit(self._manifest_result[sub], result)
		if context.is_ok():
			if isinstance(sub, syntax.UserFunction):
				if result is ACTION: self._report.must_not_express_behavior(inner, sub)
				else: return result
			elif isinstance(sub, syntax.UserProcedure):
				if _can_perform(result): return self.perform(result)
				else: self._report.does_not_express_behavior(inner, sub, actual_types)
			else: raise AssertionError("eh? "+str(type(sub)))
		else:
			self._report.bad_result(inner, sub, context.mismatch)
		return Error("350: result mismatch: %r"%[context.mismatch])

	def install_closures(self, where: Sequence[Subroutine]):
		# This has to be a two-phase process,
		# because closures can capture each other mutually.
		closures = [Closure(sub, self._tos) for sub in where]
		for c in closures: self._tos.assign(c.sub, c)
		for c in closures: c.perform_capture(self._tos)
	
	def drat(self, hint) -> SophieType:
		self._report.drat(self._tos, hint)
		return Error("361")
	
	@staticmethod
	def visit_Absurdity(_: syntax.Absurdity) -> SophieType:
		return BOTTOM
	
	def visit_Lookup(self, lu: syntax.Lookup) -> SophieType:
		# The Lookup is guaranteed to be a term, which is always
		# in either the global scope or the current local scope,
		# thanks to the nice closure-capture mechanism.
		symbol = lu.ref.dfn
		frame = self._tos if self._tos.holds(symbol) else self._global
		result = frame.fetch(symbol)
		while isinstance(result, Closure) and result.sub.is_thunk():
			result = self.apply_closure(result, (), PlausibleCover(None))
			frame.assign(symbol, result)
		if isinstance(result, Closure) and not result.value_arity():
			# Must be a zero-argument procedure at this point.
			result = self.perform(result)
			if result is ACTION: result = ZERO_ARG_PROC
			frame.assign(symbol, result)
		# At this point, if the thing is a zero-argument closure,
		# then it must refer to a procedure.
		return result
	
	def visit_Literal(self, expr: syntax.Literal) -> SophieType:
		type_name = literal_type_map[type(expr.value)]
		return self._well_known[type_name]
	
	def visit_FieldReference(self, fr:syntax.FieldReference) -> SophieType:
		lhs = self.check(fr.lhs)
		if isinstance(lhs, Special): return lhs
		if isinstance(lhs, SymbolicType):
			sym = lhs.symbol
			if isinstance(sym, RecordSymbol): params = sym.type_params
			elif isinstance(sym, RecordTag): params = sym.variant.type_params
			else:
				self._report.type_has_no_fields(self._tos, fr, lhs)
				return Error("394")
			field = sym.spec.field_space.symbol(fr.field_name.key())
			if field:
				gamma = dict(zip(params, lhs.type_args))
				return Translator(gamma).visit(field.type_expr)
			else:
				self._report.record_lacks_field(self._tos, fr, lhs)
				return Error("401")
		# if isinstance(lhs, UDAType):
		# 	self._report.no_telepathy_allowed(self._tos, fr, lhs)
		# 	return Error("404")
		self._report.type_has_no_fields(self._tos, fr, lhs)
		return Error("406")
	
	def visit_LambdaForm(self, lf: syntax.LambdaForm) -> SophieType:
		# No need to chase to find a static environment:
		# It's taken from the point-of-use by definition.
		closure = Closure(lf.function, self._tos)
		closure.perform_capture(self._tos)
		return closure
	
	def _expect_same(self, judgments):
		# A bit hairy, but it encapsulates a hairy procedure.
		each = iter(judgments)
		src1, typ1 = next(each)
		if typ1.is_error(): return typ1
		uf = PromotionFinder(typ1)
		for src, typ in each:
			if typ.is_error(): return typ
			uf.unify_with(typ)
			if uf.result().is_error():
				self._report.type_mismatch(self._tos, src1, typ1, src, typ)
				break
		return uf.result()
	
	def visit_ExplicitList(self, el: syntax.ExplicitList) -> SophieType:
		if not el.elts: return self._well_known["nil"]
		elt_type = self._expect_same((node, self.check(node)) for node in el.elts)
		if elt_type.is_error(): return elt_type
		else: return SymbolicType(self._well_known["cons"].symbol, (elt_type,))
	
	def visit_Cond(self, cond: syntax.Cond) -> SophieType:
		return self.call_site(cond, self._conditional, [cond.if_part, cond.then_part, cond.else_part])
	
	def visit_MatchExpr(self, mx: syntax.MatchExpr) -> SophieType:
		
		def try_one_alternative(alt:syntax.Alternative, case: SymbolicType) -> SophieType:
			self._tos.assign(mx.subject, case)
			self.install_closures(alt.where)
			return self.check(alt.sub_expr)
		
		def try_otherwise():
			self._tos.assign(mx.subject, subject_type)
			return self.check(mx.otherwise)
		
		def each_case_judgment(type_args: Sequence[SophieType]):
			for alt in mx.alternatives:
				case_symbol = mx.variant.sub_space[alt.pattern.key()]
				case_type = SymbolicType(case_symbol, type_args)
				case_result = try_one_alternative(alt, case_type)
				yield alt.sub_expr, case_result
			if mx.otherwise is not None:
				yield mx.otherwise, try_otherwise()
		
		def try_everything(type_args: Sequence[SophieType]):
			return self._expect_same(each_case_judgment(type_args))
		
		subject_type = self.check(mx.subject.expr)
		if subject_type.is_error(): return subject_type
		elif subject_type is BOTTOM:
			return try_everything([BOTTOM] * len(mx.variant.type_params))
		elif isinstance(subject_type, SymbolicType):
			sym = subject_type.symbol
			is_suitable_typecase = isinstance(sym, TypeCase) and sym.variant is mx.variant
			is_proper_variant = sym is mx.variant
			if is_suitable_typecase or is_proper_variant:
				return try_everything(subject_type.type_args)
		# If not returned yet:
		self._report.bad_type(self._tos, mx.subject.expr, mx.variant, subject_type)
		return Error("473: Bad Match")
	
	def _bind_role_method(self, role:syntax.RoleSymbol, type_args, method_name:Nom) -> SophieType:
		ability = role.ability_space.symbol(method_name.key())
		if ability is None:
			self._report.bad_message(self._tos, method_name, role.nom)
			return Error("479: Unknown Message")
		else:
			mapping = dict(zip(role.type_params, type_args))
			translator = Translator(mapping)
			return MessageType(tuple(map(translator.visit, ability.type_exprs)))
	
	def visit_BindMethod(self, mr:syntax.BindMethod) -> SophieType:
		rx_type = self.check(mr.receiver)
		if rx_type.is_error(): return rx_type
		# TODO: Eventually deal with multi-role things here.
		if isinstance(rx_type, SymbolicType):
			symbol = rx_type.symbol
			if isinstance(symbol, syntax.RoleSymbol):
				return self._bind_role_method(symbol, rx_type.type_args, mr.method_name)
		elif isinstance(rx_type, UDAType):
			return self._bind_uda_method(rx_type, mr.method_name)
		self._report.not_an_actor(self._tos, mr.receiver, rx_type)
		return Error("511: non-actor %s can't bind messages"%rx_type)

	def _bind_uda_method(self, actor:UDAType, method_name:Nom) -> SophieType:
		tpl = actor.tpl
		try: method = tpl.behavior[method_name.key()]
		except KeyError:
			self._report.bad_message(self._tos, method_name, actor)
			return Error("517: Actor %s does not understand message %s."%(actor, method_name))
		return self.user_message(method)
	
	def visit_DoBlock(self, do:syntax.DoBlock) -> SophieType:
		# 1. Bring any new-actors into scope:
		for new_actor in do.actors:
			assert isinstance(new_actor, syntax.NewActor)
			template = self.check(new_actor.expr)
			if template.is_error(): return template
			if isinstance(template, ConcreteTpl):
				actor_type = template.fields.fetch(SELF)
			else:
				self._report.bad_type(self._tos, new_actor.expr, "Actor Template", template)
				return Error("531: Bogus Actor Template")
			self._tos.assign(new_actor, actor_type)
		
		# 2. Judge the types of the steps in the updated scope:
		for step in do.steps:
			result = self.perform(self.check(step))
			if result.is_error(): return result
		return ACTION
	
	def perform(self, typ: SophieType) -> SophieType:
		while isinstance(typ, Closure) and not typ.value_arity():
			typ = self.apply_closure(typ, (), PlausibleCover(None))
		if typ.is_error(): return typ
		if typ is ACTION or is_equivalent(typ, READY_MESSAGE): return ACTION
		self._report.bad_type(self._tos, self._tos.pc, "action", typ)
		return Error("550: non-action in procedure")
	
	def display(self, expr:syntax.ValueExpression) -> bool:
		t = self.check(expr)
		if _can_perform(t): t = self.perform(t)
		return t is ACTION

	@staticmethod
	def visit_Skip(_s:syntax.Skip) -> SophieType: return ACTION
	
	def user_message(self, closure:Closure):
		assert isinstance(closure.sub, syntax.UserProcedure)
		if closure.value_arity(): return ParametricTask(closure)
		else: return _dispatchable(self.perform(closure))
	
	def visit_AsTask(self, at:syntax.AsTask) -> SophieType:
		typ = self.check(at.proc_ref)
		if isinstance(typ, Closure) and isinstance(typ.sub, syntax.UserProcedure):
			return self.user_message(typ)
		if isinstance(typ, ArrowType) and typ.result_type is ACTION:
			return MessageType(typ.arg_types)
		self._report.bad_task(self._tos, at.proc_ref, typ)
		return Error("549: Not Task-able")
	
	def visit_AssignMember(self, am: syntax.AssignMember) -> SophieType:
		# The concept is to make sure the field's formal
		# type can accept the value given here.
		
		expr_type = self.check(am.expr)
		if expr_type.is_error(): return expr_type
		
		assert isinstance(am.dfn, syntax.FormalParameter)
		field_type = self._manifest_params[am.dfn]
		cover = PlausibleCover(self)
		cover.bind(field_type, expr_type)
		if cover.is_ok(): return ACTION
		else:
			self._report.bad_type(self._tos, am.expr, field_type, expr_type)
			return Error("587: Bad assignment")

def _can_perform(t:SophieType) -> bool:
	"""
	I.E. the sort of thing that can be a step in a process.
	A reference to a 
	"""
	if t is ACTION: return True
	if is_equivalent(t, READY_MESSAGE): return True
	if isinstance(t, Closure): return not t.value_arity()
	return False

def _dispatchable(result:SophieType):
	if result is ACTION:
		return READY_MESSAGE
	else:
		assert result.is_error()
		return result

