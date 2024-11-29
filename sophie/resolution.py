"""
All the definition resolution stuff goes here.
By the time this pass is finished, every name points to its symbol table entry,
from which we can find the kind, type, and definition.
"""
from importlib import import_module
from pathlib import Path
from traceback import TracebackException
from typing import Union, Optional, Iterable, TypeAlias
from inspect import signature
from boozetools.support.foundation import Visitor, strongly_connected_components_hashable
from . import syntax, primitive
from .diagnostics import Report
from .ontology import Symbol, TypeSymbol, TermSymbol, SELF, Nom
from .modularity import Program, SophieParseError, SophieImportError
from .space import Space, Layer, Scope, AlreadyExists

TypeSpace:TypeAlias = Space[TypeSymbol]
ParamList:TypeAlias = Iterable[syntax.FormalParameter]
FormalLayer:TypeAlias = Layer[syntax.FormalParameter]

class Yuck(Exception):
	"""
	The first argument will be the name of the pass fraught with error.
	The end-user might not care about this, but it's handy for testing.
	"""
	pass

class RoadMap:
	preamble : syntax.Module
	list_symbol : syntax.Variant
	order_symbol : syntax.Variant
	export_scopes : dict[syntax.Module, Scope]
	each_module : list[syntax.Module]  # Does not include the preamble, apparently.
	import_map : dict[syntax.ImportModule, syntax.Module]

	def __init__(self, main_path:Path, report:Report):
		self.export_scopes = {}
		self.each_module = []

		def register(parent:Scope, module:syntax.Module):
			report.set_path(module.source_path)
			resolver = Resolver(self, module, parent, report)
			if report.sick(): raise Yuck("resolve")
			
			_report_circular_aliases(resolver.alias_graph, report)
			if report.sick(): raise Yuck("alias")
			
			self.export_scopes[module] = resolver.export_scope()
			return module
		
		def _fetchVariant(key: str) -> syntax.Variant:
			symbol = preamble_scope.types.symbol(key)
			assert isinstance(symbol, syntax.Variant)
			return symbol
		
		try: program = Program(main_path, report)
		except SophieParseError: raise Yuck("parse")
		except SophieImportError: raise Yuck("import")
		report.assert_no_issues("Parser reported an error but failed to fail.")
		self.import_map = program.import_map

		self.preamble = register(primitive.root_scope, program.preamble)
		preamble_scope = self.export_scopes[self.preamble].atop(primitive.root_scope)
		self.list_symbol = _fetchVariant('list')
		self.order_symbol = _fetchVariant('order')
		self.each_module = list(program.module_sequence)
		for item in self.each_module: register(preamble_scope, item)

class TopDown(Visitor):
	"""
	Convenience base-class to handle the dreary bits of a
	perfectly ordinary top-down walk through a syntax tree.
	"""
	
	def visit_ArrowSpec(self, it: syntax.ArrowSpec, env):
		for a in it.lhs:
			self.visit(a, env)
		self.visit(it.rhs, env)
	
	def visit_Absurdity(self, absurd: syntax.Absurdity, env): pass
	def visit_Literal(self, l:syntax.Literal, env): pass
	def visit_Skip(self, s:syntax.Skip, env): pass
	def visit_ImplicitTypeVariable(self, it:syntax.ImplicitTypeVariable, env): pass

	def visit_ShortCutExp(self, it: syntax.ShortCutExp, env):
		self.visit(it.lhs, env)
		self.visit(it.rhs, env)
	
	def visit_BinExp(self, it: syntax.BinExp, env):
		self.visit(it.lhs, env)
		self.visit(it.rhs, env)
	
	def visit_UnaryExp(self, expr: syntax.UnaryExp, env):
		self.visit(expr.arg, env)
	
	def visit_FieldReference(self, expr: syntax.FieldReference, env):
		# word-agnostic until we know the type of expr.lhs.
		self.visit(expr.lhs, env)
	
	def visit_BindMethod(self, expr: syntax.BindMethod, env):
		# word-agnostic until we know the type of expr.receiver.
		self.visit(expr.receiver, env)
	
	def visit_Call(self, expr: syntax.Call, env):
		self.visit(expr.fn_exp, env)
		for a in expr.args:
			self.visit(a, env)
	
	def visit_Cond(self, expr: syntax.Cond, env):
		self.visit(expr.if_part, env)
		self.visit(expr.then_part, env)
		self.visit(expr.else_part, env)
	
	def visit_ExplicitList(self, expr: syntax.ExplicitList, env):
		for e in expr.elts:
			self.visit(e, env)
	
	def visit_AsTask(self, at: syntax.AsTask, env):
		self.visit(at.proc_ref, env)

class Resolver(TopDown):
	"""
	This single top-down tree-walk does many things.
	
	* Wrangle imported symbols.
	* Define the fields and methods of records and actors.
	* Connect all name references to their proper definitions in scope.
	* Connect "assume" types to formal-parameters that lack annotations.
	
	NB: "assume" types are done by modifying the AST in-place,
	    as if the programmer put the annotation directly.
	
	"""
	exported_types: Layer[syntax.TypeDeclaration]
	exported_terms: Layer[TermSymbol]
	
	def export_scope(self):
		return Scope(self.exported_types, self.exported_terms)
	
	module: syntax.Module
	report: Report
	
	_aliased_imports: Layer[syntax.ImportModule]
	_module_scope : Scope
	_assumptions: FormalLayer
	
	_type_calls_must_supply_arguments: bool
	
	_member_space: Optional[FormalLayer]
	_reads_members: set[Symbol]
	
	_current_type_alias: Optional[syntax.TypeAlias]
	alias_graph: dict[syntax.TypeAlias, set[syntax.TypeAlias]]
	
	def _install(self, space:Space, symbol:Symbol):
		# Convenience function for most definitions.
		self._alias(space, symbol.nom, symbol)
	
	def _install_each(self, space:Space, symbols:Iterable[Symbol]):
		for s in symbols: self._install(space, s)
	
	def _alias(self, space:Space, alias:Nom, symbol:Symbol):
		# Suitable for aliased imports.
		try: space.alias(alias, symbol)
		except AlreadyExists:
			key = alias.key()
			self.report.redefined(key, space.locate(key), alias.head())
	
	def _undefined(self, nom: syntax.Nom):
		self.report.undefined_name(nom.head())
		return Bogon(nom)

	def _lookup(self, nom: syntax.Nom, env:Space):
		return env.symbol(nom.key()) or self._undefined(nom)
	
	def _lookup_member(self, nom: syntax.Nom):
		if self._member_space is None:
			self.report.can_only_see_member_within_behavior(nom)
			return Bogon(nom)
		else:
			return self._lookup(nom, self._member_space)
	
	def _tour(self, items, *args):
		for i in items:
			self.visit(i, *args)
	
	def _formal_layer(self, params:ParamList, type_env:TypeSpace) -> FormalLayer:
		layer = Layer()
		for p in params:
			self._install(layer, p)
			if p.type_expr is None:
				assumption = self._assumptions.symbol(p.nom.key())
				if assumption: p.type_expr = assumption.type_expr 
			if p.type_expr is not None:
				self.visit(p.type_expr, type_env)
		return layer
	
	def __init__(self, roadmap: RoadMap, module:syntax.Module, outer:Scope, report:Report):
		self.roadmap = roadmap
		self.module = module
		self.report = report
		self._aliased_imports = Layer()
		self.exported_types = Layer()
		self.exported_terms = Layer()
		self._module_scope = Scope.fresh().atop(outer)
		self._assumptions = Layer()
		self._member_space = None
		self._reads_members = set()
		self._current_type_alias = None
		self.alias_graph = {}

		self._type_calls_must_supply_arguments = True
		for im in module.imports: self.declare_import(im)
		for td in module.types: self.declare_type(td)
		for fn in module.top_subs:
			if not isinstance(fn, syntax.UserOperator):
				self.declare_term(fn)
		for uda in module.actors: self.declare_term(uda)

		for td in module.types: self.visit(td, self._generic(td))
		for fi in module.foreign: self.define_foreign(fi)
		
		self._type_calls_must_supply_arguments = False
		for a in module.assumptions: self.note_assumption(a)
		for fn in module.top_subs: self.visit(fn, self._module_scope)
		for uda in module.actors: self.define_actor(uda)
		for expr in self.module.main:
			self.visit(expr, self._module_scope)
	
	def _imported_scope(self, nom: Nom) -> Optional[Scope]:
		im = self._aliased_imports.symbol(nom.key())
		if im is not None:
			source_module = self.roadmap.import_map[im]
			return self.roadmap.export_scopes[source_module]
	
	def declare_import(self, im:syntax.ImportModule):
		source_module = self.roadmap.import_map[im]
		source_scope = self.roadmap.export_scopes[source_module]
		
		if im.nom is not None:
			self._install(self._aliased_imports, im)

		for yonder, hither in im.vocab:
			self.import_symbol(source_scope, yonder, hither or yonder)
	
	def import_symbol(self, scope:Scope, yonder:Nom, hither:Nom):
		# If the yonder name is in scope.types, import the type.
		# If in scope.terms, import the term.
		# If neither, complain.
		
		typ = scope.types.symbol(yonder.key())
		trm = scope.terms.symbol(yonder.key())
		
		if typ: self._alias(self._module_scope.types, hither, typ)
		if trm: self._alias(self._module_scope.terms, hither, trm)
		
		if not (typ or trm):
			self.report.undefined_name(yonder.head())
	
	def declare_type(self, td:syntax.TypeDeclaration):
		self._install(self._module_scope.types, td)
		self._install(self.exported_types, td)
		if isinstance(td, syntax.TypeAlias): self.alias_graph[td] = set()
		if isinstance(td, syntax.Record): self.declare_term(td)
		if isinstance(td, syntax.Variant):
			for sub in td.subtypes: self.declare_term(sub)
	
	def declare_term(self, symbol:Symbol):
		self._install(self._module_scope.terms, symbol)
		self._install(self.exported_terms, symbol)

	def _generic(self, item:Union[syntax.TypeDeclaration, syntax.FFI_Group]) -> TypeSpace:
		type_env = self._module_scope.types.child()
		for fp in item.type_params: self._install(type_env, fp)
		return type_env

	def visit_Variant(self, v:syntax.Variant, type_env:TypeSpace):
		for sub in v.subtypes:
			self.visit(sub, type_env)
	
	def visit_Tag(self, t: syntax.Tag, type_env:Space):
		pass
	
	def visit_TaggedRecord(self, record: syntax.TaggedRecord, type_env:TypeSpace):
		self.visit_RecordSpec(record.spec, type_env)
	
	def visit_Record(self, record: syntax.Record, type_env:TypeSpace):
		self.visit_RecordSpec(record.spec, type_env)
	
	def visit_TypeAlias(self, ta: syntax.TypeAlias, type_env:TypeSpace):
		# Idea: Should this optionally create a term-alias?
		assert self._current_type_alias is None
		self._current_type_alias = ta
		self.visit(ta.body, type_env)
		self._current_type_alias = None
	
	def visit_Opaque(self, td: syntax.Opaque, type_env:TypeSpace):
		if td.type_params: self.report.opaque_generic(td.type_params)
	
	def visit_Role(self, role:syntax.Role, type_env:TypeSpace):
		role.ability_space = Layer()
		for ability in role.abilities:
			self._install(role.ability_space, ability)
			self._tour(ability.type_exprs, type_env)
	
	def visit_MessageSpec(self, ms: syntax.MessageSpec, type_env:TypeSpace):
		self._tour(ms.type_exprs, type_env)
	
	def visit_RecordSpec(self, spec: syntax.RecordSpec, type_env:TypeSpace):
		spec.field_space = self._formal_layer(spec.fields, type_env)
	
	def _resolve_type(self, ref:syntax.Reference, type_env:TypeSpace) -> TypeSymbol:
		if isinstance(ref, (syntax.PlainReference, syntax.ExplicitTypeVariable)):
			symbol = self._lookup(ref.nom, type_env)
			if self._current_type_alias and isinstance(symbol, syntax.TypeAlias):
				self.alias_graph[self._current_type_alias].add(symbol)
		else:
			assert isinstance(ref, syntax.QualifiedReference), type(ref)
			scope = self._imported_scope(ref.space)
			if scope is None: symbol = self._undefined(ref.space)
			else: symbol = self._lookup(ref.nom, scope.types)
		ref.dfn = symbol
		return symbol
	
	def visit_TypeCall(self, tc: syntax.TypeCall, type_env:TypeSpace):
		symbol = self._resolve_type(tc.ref, type_env)
		if isinstance(symbol, syntax.TypeParameter):
			if tc.arguments:
				self.report.called_a_type_parameter(tc)
		elif isinstance(symbol, syntax.TypeDeclaration):
			actual_arity = len(tc.arguments)
			if actual_arity or self._type_calls_must_supply_arguments:
				formal_arity = len(symbol.type_params)
				if actual_arity == formal_arity:
					for p in tc.arguments: self.visit(p, type_env)
				else:
					self.report.wrong_type_arity(tc, actual_arity, formal_arity)
		else:
			assert isinstance(symbol, Bogon), symbol

	def define_foreign(self, fi:syntax.ImportForeign):
		try: py_module = import_module(fi.source.value)
		except ModuleNotFoundError:
			self.report.missing_foreign_module(fi.source)
		except ImportError as ex:
			tbx = TracebackException.from_exception(ex)
			self.report.broken_foreign_module(fi.source, tbx)
		else:
			if fi.linkage is not None:
				if not hasattr(py_module, "sophie_init"):
					self.report.missing_foreign_linkage(fi.source)
					return
				arity = len(signature(py_module.sophie_init).parameters)
				if arity != len(fi.linkage):
					self.report.wrong_linkage_arity(fi, arity)
					return
				for ref in fi.linkage or ():
					self.visit(ref, self._module_scope)
			for group in fi.groups:
				self.visit(group.type_expr, self._generic(group))
				for sym in group.symbols:
					self.define_FFI_Alias(sym, py_module)
					if isinstance(sym, syntax.FFI_Operator):
						self.module.ffi_operators.append(sym)

	def define_FFI_Alias(self, sym:syntax.FFI_Alias, py_module):
		key = sym.nom.key() if sym.alias is None else sym.alias.value
		try: sym.val = getattr(py_module, key)
		except AttributeError:
			self.report.undefined_name(sym.span_of_native_name())
		else:
			self.declare_term(sym)

	def note_assumption(self, a:syntax.Assumption):
		""" Update the self.assume namespace accordingly. """
		for nom in a.names:
			fp = syntax.FieldDefinition(nom, a.type_expr)
			self._install(self._assumptions, fp)
	
	def visit_Lookup(self, lu: syntax.Lookup, scope:Scope):
		ref = lu.ref
		if isinstance(ref, syntax.PlainReference):
			dfn = self._lookup(ref.nom, scope.terms)
		elif isinstance(ref, syntax.QualifiedReference):
			target = self._imported_scope(ref.space)
			if target is None: dfn = self._undefined(ref.space)
			else: dfn = self._lookup(ref.nom, target.terms)
		elif isinstance(ref, syntax.MemberReference):
			dfn = self._lookup_member(ref.nom)
			self._reads_members.add(dfn)
		elif isinstance(ref, syntax.SelfReference):
			dfn = SELF if self._member_space else self._undefined(ref.nom)
		else: assert False, type(ref)
		lu.dfn = ref.dfn = dfn

	def visit_UserFunction(self, udf:syntax.UserFunction, outer:Scope):
		self.module.all_fns.append(udf)
		self._ponder_subroutine(udf, outer)

	def visit_LambdaForm(self, lf: syntax.LambdaForm, scope:Scope):
		self.visit(lf.function, scope)

	def define_actor(self, uda:syntax.UserActor):
		# Housekeeping:
		uda.source_path = self.module.source_path
		
		# Real Stuff:
		uda.field_space = self._formal_layer(uda.fields, self._module_scope.types)
		uda.behavior_space = Layer()
		self._member_space = uda.field_space
		for behavior in uda.behaviors:
			self._install(uda.behavior_space, behavior)
			self._reads_members = behavior.reads_members = set()
			self.visit_UserProcedure(behavior, self._module_scope)
		self._member_space = None
	
	def visit_UserProcedure(self, proc:syntax.UserProcedure, outer:Scope):
		self.module.all_procs.append(proc)
		self._ponder_subroutine(proc, outer)
	
	def _ponder_subroutine(self, sub:syntax.Subroutine, outer:Scope):
		sub.source_path = self.module.source_path
		type_layer = outer.types.child()
		term_layer = self._formal_layer(sub.params, type_layer)
		if sub.result_type_expr: self.visit(sub.result_type_expr, type_layer)
		self._install_each(term_layer, sub.where)
		inner = outer.with_terms(term_layer)
		self.visit(sub.expr, inner)
		self._tour(sub.where, inner)

	def visit_ExplicitTypeVariable(self, gt:syntax.ExplicitTypeVariable, type_env:TypeSpace):
		if gt.nom.key() not in type_env:
			self._install(type_env, syntax.TypeParameter(gt.nom))
		gt.dfn = self._resolve_type(gt, type_env)

	def visit_DoBlock(self, db: syntax.DoBlock, outer:Scope):
		if db.actors:
			cast = Layer()
			inner = outer.with_terms(cast)
			for new_actor in db.actors:
				self.visit(new_actor.expr, inner)
				self._install(cast, new_actor)
		else:
			inner = outer
		for s in db.steps:
			self.visit(s, inner)
	
	def visit_AssignMember(self, am:syntax.AssignMember, env):
		am.dfn = self._lookup_member(am.nom)
		return self.visit(am.expr, env)

	def visit_MatchExpr(self, mx:syntax.MatchExpr, outer:Scope):
		self.visit(mx.subject.expr, outer)
		if mx.hint is not None:
			mx.hint.dfn = self._resolve_type(mx.hint, outer.types)
		_build_match_dispatch(mx, self._module_scope, self.report)
		subject_layer = Layer()
		self._install(subject_layer, mx.subject)
		subject_scope = outer.with_terms(subject_layer)
		for alt in mx.alternatives:
			alt_layer = Layer()
			for fn in alt.where: self._install(alt_layer, fn)
			alt_scope = subject_scope.with_terms(alt_layer)
			self.visit(alt.sub_expr, alt_scope)
			for fn in alt.where: self.visit(fn, alt_scope)
		if mx.otherwise is not None:
			self.visit(mx.otherwise, subject_scope)
	
	def visit_FieldReference(self, expr: syntax.FieldReference, env):
		super().visit_FieldReference(expr, env)
		if _is_a_self_reference(expr):
			self.report.use_my_instead(env, expr)


def _is_a_self_reference(expr:syntax.ValExpr) -> bool:
	return isinstance(expr, syntax.Lookup) and expr.ref.dfn is SELF

class Bogon(syntax.Symbol): pass

def _report_circular_aliases(graph, report:Report):
	for scc in strongly_connected_components_hashable(graph):
		if len(scc) == 1:
			node = scc[0]
			if node in graph[node]:
				report.circular_type(scc)
		else:
			report.circular_type(scc)


def _build_match_dispatch(mx: syntax.MatchExpr, scope:Scope, report: Report):
	# Figure out what type of variant-record this MatchExpr is dissecting.
	if mx.hint is None:
		# Guess the variant based on the first alternative.
		#
		# Someday: Expand this to deal with local ambiguity
		#          by consulting a larger amount of context.
		first = mx.alternatives[0].pattern
		case = scope.terms.symbol(first.key())
		if case is None:
			report.undefined_name(first.head())
			return
		if not isinstance(case, syntax.TypeCase):
			report.not_a_case(first)
			return
		variant = case.variant
	else:
		variant = mx.hint.dfn
		if not isinstance(variant, syntax.Variant):
			report.not_a_variant(mx.hint)
			return

	# Check for duplicate cases and typos.
	mx.dispatch = {}
	for alt in mx.alternatives:
		try: st = variant.sub_space[alt.pattern.key()]
		except KeyError: report.not_a_case_of(alt.pattern, variant)
		else:
			if st in mx.dispatch:
				report.redundant_pattern(mx.dispatch[st], alt)
			else:
				alt.dfn = st
				mx.dispatch[st] = alt
	
	# Check for exhaustiveness.

	mx.variant = variant
	exhaustive = len(mx.dispatch) == len(variant.subtypes)
	if      exhaustive and mx.otherwise : report.redundant_else(mx)
	if not (exhaustive or  mx.otherwise): report.not_exhaustive(mx)

