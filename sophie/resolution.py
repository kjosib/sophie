"""
All the definition resolution stuff goes here.
By the time this pass is finished, every name points to its symbol table entry,
from which we can find the kind, type, and definition.
"""
from importlib import import_module
from pathlib import Path
from traceback import TracebackException
from typing import Union
from inspect import signature
from boozetools.support.foundation import Visitor, strongly_connected_components_hashable
from boozetools.support.symtab import NoSuchSymbol, SymbolAlreadyExists
from . import syntax, diagnostics, primitive
from .ontology import NS, Symbol
from .modularity import Program, SophieParseError, SophieImportError

class Yuck(Exception):
	"""
	The first argument will be the name of the pass fraught with error.
	The end-user might not care about this, but it's handy for testing.
	"""
	pass

class RoadMap:
	preamble : syntax.Module
	module_scopes : dict[syntax.Module, NS]
	import_alias : dict[syntax.Module, NS]
	each_module : list[syntax.Module]
	each_udf : list[syntax.UserFunction]
	each_match : list[syntax.MatchExpr]
	import_map : dict[syntax.ImportModule, syntax.Module]

	def __init__(self, base_path:Path, module_path:str, report:diagnostics.Report):
		self.module_scopes = {}
		self.import_alias = {}
		self.each_module = []
		self.each_udf = []
		self.each_match = []

		self.note_udf = self.each_udf.append
		self.note_match = self.each_match.append

		def register(parent, module_key):
			module = program.parsed_modules[module_key]
			assert isinstance(module, syntax.Module)
			self.module_scopes[module] = parent.new_child(module_key)
			self.import_alias[module] = NS(place=module_key)

			report.set_path(module_key)
			_WordDefiner(self, module, report)
			if report.sick(): raise Yuck("define")

			resolver = _WordResolver(self, module, report)
			if report.sick(): raise Yuck("resolve")

			_AliasChecker(self, module, report)
			if report.sick(): raise Yuck("alias")

			check_constructors(resolver.dubious_constructors, report)
			if report.sick(): raise Yuck("constructors")

			self.build_match_dispatch_tables()

			return module

		try: program = Program(base_path, module_path, report)
		except SophieParseError: raise Yuck("parse")
		except SophieImportError: raise Yuck("import")
		report.assert_no_issues()
		self.import_map = program.import_map

		self.preamble = register(primitive.root_namespace, program.preamble_key)
		preamble_scope = self.module_scopes[self.preamble]
		for path in program.module_sequence:
			self.each_module.append(register(preamble_scope, path))

	def build_match_dispatch_tables(self):
		""" The simple evaluator uses these. """
		# Cannot fail, for checks have been done earlier.
		for mx in self.each_match:
			mx.dispatch = {
				alt.nom.key() : alt.sub_expr
				for alt in mx.alternatives
			}
		self.each_match.clear()

class TopDown(Visitor):
	"""
	Convenience base-class to handle the dreary bits of a
	perfectly ordinary top-down walk through a syntax tree.
	"""

	def visit_ArrowSpec(self, it: syntax.ArrowSpec, env):
		for a in it.lhs:
			self.visit(a, env)
		self.visit(it.rhs, env)

	def visit_Literal(self, l:syntax.Literal, env): pass

	def visit_ImplicitType(self, it:syntax.ImplicitTypeVariable, env): pass

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
	
	def visit_BoundMethod(self, expr: syntax.BoundMethod, env):
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
	
	def visit_DoBlock(self, db: syntax.DoBlock, env):
		for s in db.steps:
			self.visit(s, env)

class _ResolutionPass(TopDown):
	globals: NS
	import_alias: NS

	def __init__(self, roadmap: RoadMap, module:syntax.Module, report:diagnostics.Report):
		self.roadmap = roadmap
		self.report = report
		self.globals = self.roadmap.module_scopes[module]
		self.import_alias = self.roadmap.import_alias[module]
		self.visit_Module(module)

	def visit_Module(self, module:syntax.Module):
		raise NotImplementedError(type(self))

class _WordDefiner(_ResolutionPass):
	"""
	At the end of this phase:
		Names used in declarations have an attached symbol table entry.
		The entry is installed in all appropriate namespaces.

	Attaches NameSpace objects in key places and install definitions.
	Takes note of names with more than one definition in the same scope.
	"""

	def visit_Module(self, module:syntax.Module):
		for d in module.imports: self.visit_ImportModule(d)
		for td in module.types: self.visit(td)
		for d in module.foreign: self.visit_ImportForeign(d)
		for fn in module.outer_functions:  # Can't iterate all-functions yet; must build it first.
			self.visit(fn, self.globals)
		for expr in module.main:  # Might need to define some case-match symbols here.
			self.visit(expr, self.globals)
		pass

	def _install(self, namespace: NS, dfn:Symbol):
		try: namespace[dfn.nom.key()] = dfn
		except SymbolAlreadyExists:
			earlier = namespace[dfn.nom.key()]
			self.report.redefined_name(earlier, dfn.nom)

	def _declare_type(self, td:syntax.TypeDeclaration):
		self._install(self.globals, td)
		self._define_type_params(td)

	def _define_type_params(self, item:Union[syntax.TypeDeclaration, syntax.FFI_Group]):
		ps = item.param_space = self.globals.new_child(place=item)
		for p in item.type_params:
			assert isinstance(p, syntax.TypeParameter), type(p)
			self._install(ps, p)

	def visit_Opaque(self, o:syntax.Opaque):
		self._install(self.globals, o)
		if o.type_params:
			self.report.opaque_generic(o.type_params)

	def visit_Variant(self, v:syntax.Variant):
		self._declare_type(v)
		ss = v.sub_space = NS(place=v)
		for st in v.subtypes:
			self._install(self.globals, st)
			self._install(ss, st)
			if st.body is not None:
				self.visit(st.body)

	def visit_Record(self, r:syntax.Record):
		self._declare_type(r)
		self.visit(r.spec)

	def visit_TypeAlias(self, ta:syntax.TypeAlias):
		self._declare_type(ta)

	def visit_RecordSpec(self, rs:syntax.RecordSpec):
		# Ought to have a local name-space with names having types.
		rs.field_space = NS(place=rs)
		for f in rs.fields:
			self._install(rs.field_space, f)
		return

	def visit_TypeCall(self, it:syntax.TypeCall, env:NS):
		for a in it.arguments:
			self.visit(a, env)

	def visit_UserFunction(self, udf:syntax.UserFunction, env:NS):
		self.roadmap.note_udf(udf)
		self._install(env, udf)
		inner = udf.namespace = env.new_child(udf)
		for param in udf.params:
			self.visit(param, inner)
		if udf.result_type_expr is not None:
			self.visit(udf.result_type_expr, inner)
		for sub_fn in udf.where:
			self.visit(sub_fn, inner)
		self.visit(udf.expr, inner)

	def visit_FormalParameter(self, fp:syntax.FormalParameter, env:NS):
		self._install(env, fp)
		if fp.type_expr is not None:
			self.visit(fp.type_expr, env)

	def visit_ExplicitTypeVariable(self, gt:syntax.ExplicitTypeVariable, env:NS):
		if gt.nom.key() not in env:
			self._install(env, syntax.TypeParameter(gt.nom))

	def visit_Lookup(self, l:syntax.Lookup, env:NS): pass

	def visit_MatchExpr(self, mx:syntax.MatchExpr, env:NS):
		self.roadmap.note_match(mx)
		self.visit(mx.subject.expr, env)
		inner = mx.namespace = env.new_child(mx)
		self._install(inner, mx.subject)
		for alt in mx.alternatives:
			self.visit(alt, inner)
		if mx.otherwise is not None:
			self.visit(mx.otherwise, inner)

	def visit_Alternative(self, alt: syntax.Alternative, env: NS):
		for sub_ex in alt.where:
			self.visit(sub_ex, env)
		self.visit(alt.sub_expr, env)

	def visit_ImportModule(self, im:syntax.ImportModule):
		source_module = self.roadmap.import_map[im]
		source_namespace = self.roadmap.module_scopes[source_module]
		if im.nom is not None:
			self._install(self.import_alias, im)
		for alias in im.vocab:
			yonder, hither = alias.yonder, alias.hither or alias.yonder
			try: subject = source_namespace[yonder.key()]
			except KeyError: self.report.undefined_name(yonder.head())
			else:
				try: self.globals[hither.key()] = subject
				except SymbolAlreadyExists:
					collision = self.globals[hither.key()]
					self.report.redefined_name(collision, hither)

		pass

	def visit_ImportForeign(self, d:syntax.ImportForeign):
		try: py_module = import_module(d.source.value)
		except ModuleNotFoundError:
			self.report.missing_foreign_module(d.source)
		except ImportError as ex:
			tbx = TracebackException.from_exception(ex)
			self.report.broken_foreign_module(d.source, tbx)
		else:
			if d.linkage is not None:
				if not hasattr(py_module, "sophie_init"):
					self.report.missing_foreign_linkage(d.source)
					return
				arity = len(signature(py_module.sophie_init).parameters)
				if arity != len(d.linkage):
					self.report.wrong_linkage_arity(d, arity)
					return
			for group in d.groups:
				self._define_type_params(group)
				for sym in group.symbols:
					self.visit(sym, py_module)

	def visit_FFI_Alias(self, sym:syntax.FFI_Alias, py_module):
		key = sym.nom.key() if sym.alias is None else sym.alias.value
		try: sym.val = getattr(py_module, key)
		except AttributeError:
			guilty = (sym.alias or sym.nom).head()
			self.report.undefined_name(guilty)
		else: self._install(self.globals, sym)

class _WordResolver(_ResolutionPass):
	"""
	At the end of this action, every name-reference in the source text is visible where it's used.
	That is, a corresponding definition-object is in scope. It may not make sense,
	or be the right kind of name, but at least it's not an obvious misspelling.
	
	This will not be able to handle field-access (or keyword-args, etc) in the first instance,
	because those depend on some measure of type resolution. And to keep things simple,
	I'm going to worry about that part in a separate pass.
	
	Walk the tree looking for undefined words in each static scope.
	Report on every such occurrence.
	If this pass succeeds, every syntax.Name object is connected to its corresponding symbol table entry.
	This is also a good place to pick up interesting lists of syntax objects, such as all match-cases.
	"""
	
	dubious_constructors: list[syntax.Reference]

	def visit_Module(self, module:syntax.Module):
		self.dubious_constructors = []
		for td in module.types:
			self.visit(td)
		for item in module.foreign:
			self.visit(item)
		for item in self.roadmap.each_udf:
			self.visit(item)
		for expr in module.main:
			self.visit(expr, self.globals)

	def visit_Variant(self, v:syntax.Variant):
		for st in v.subtypes:
			if st.body is not None:
				self.visit(st.body, v.param_space)
	
	def visit_Record(self, r:syntax.Record):
		self.visit(r.spec, r.param_space)
	
	def visit_TypeAlias(self, ta:syntax.TypeAlias):
		self.visit(ta.body, ta.param_space)
	
	def visit_RecordSpec(self, rs:syntax.RecordSpec, env:NS):
		for f in rs.fields:
			self.visit(f.type_expr, env)
	
	def _lookup(self, nom:syntax.Nom, env:NS):
		try: return env[nom.key()]
		except NoSuchSymbol:
			self.report.undefined_name(nom.head())
			return Bogon(nom)

	def visit_PlainReference(self, ref:syntax.PlainReference, env:NS):
		# This kind of reference searches the local-scoped name-space
		ref.dfn = self._lookup(ref.nom, env)
	
	def visit_QualifiedReference(self, ref:syntax.QualifiedReference, env:NS):
		# Search among imports.
		im = self._lookup(ref.space, self.import_alias)
		if isinstance(im, Bogon): ref.dfn = im
		else:
			assert isinstance(im, syntax.ImportModule)
			target_module = self.roadmap.import_map[im]
			target_namespace = self.roadmap.module_scopes[target_module]
			ref.dfn = self._lookup(ref.nom, target_namespace)
	
	def visit_TypeCall(self, tc:syntax.TypeCall, env:NS):
		self.visit(tc.ref, env)
		for p in tc.arguments:
			self.visit(p, env)

	def visit_UserFunction(self, sym:syntax.UserFunction):
		for param in sym.params:
			if param.type_expr is not None:
				self.visit(param.type_expr, sym.namespace)
		if sym.result_type_expr is not None:
			self.visit(sym.result_type_expr, sym.namespace)
		self.visit(sym.expr, sym.namespace)

	def visit_MatchExpr(self, mx:syntax.MatchExpr, env:NS):
		self.visit(mx.subject.expr, env)
		for alt in mx.alternatives:
			self.visit(alt.sub_expr, mx.namespace)
			for sub_ex in alt.where:
				self.visit(sub_ex)
		if mx.otherwise is not None:
			self.visit(mx.otherwise, mx.namespace)
			
	def visit_Lookup(self, lu: syntax.Lookup, env: NS):
		self.visit(lu.ref, env)
		dfn = lu.ref.dfn
		if isinstance(dfn, syntax.TypeAlias) or not dfn.has_value_domain():
			self.dubious_constructors.append(lu.ref)
	
	def visit_ImportForeign(self, d:syntax.ImportForeign):
		for ref in d.linkage or ():
			self.visit(ref, self.globals)
		for group in d.groups:
			self.visit(group.type_expr, group.param_space)

class Bogon(syntax.Symbol):
	def has_value_domain(self) -> bool:
		return False

class _AliasChecker(Visitor):
	"""
	Check the arity of TypeCall forms.
	Check for aliases being well-founded, up front before getting caught in a loop later:
	There should be no cycles in the aliasing dependency graph, and no wrong-kind references.
	Also re-orders type definitions in order of alias topology.
	
	Stop worrying about function cycles; I'll catch that problem in the type checker.
	"""
	
	def __init__(self, roadmap: RoadMap, module:syntax.Module, report:diagnostics.Report):
		self.on_error = report.on_error("Circular Reasoning")
		self.roadmap = roadmap
		self.report = report
		self.globals = self.roadmap.module_scopes[module]
		self.import_alias = self.roadmap.import_alias[module]
		self.visit_Module(module)

	def visit_Module(self, module: syntax.Module):
		self.non_types = []
		self.graph = {td:[] for td in module.types}
		self._tour(module.types)
		self._tour(module.foreign)
		self._tour(self.roadmap.each_udf)
		if self.non_types:
			self.on_error(self.non_types, "Need a type-name here; found this instead.")
		alias_order = []
		ok = True
		for scc in strongly_connected_components_hashable(self.graph):
			if len(scc) == 1:
				node = scc[0]
				if node in self.graph[node]:
					self.on_error([node], "This is a circular definition.")
				elif isinstance(node, syntax.TypeDeclaration):
					alias_order.append(node)
			else:
				self.on_error(scc, "These make a circular definition.")
				ok = False
		if ok:
			assert len(alias_order) == len(module.types)
			module.types = alias_order
	pass

	def _tour(self, them):
		for item in them:
			self.visit(item)
	
	def visit_TypeAlias(self, ta:syntax.TypeAlias):
		self.graph[ta].append(ta.body)
		self.visit(ta.body)
	
	def visit_TypeCall(self, tc:syntax.TypeCall):
		assert tc not in self.graph
		self.graph[tc] = edges = list(tc.arguments)
		referent = tc.ref.dfn
		if isinstance(referent, syntax.TypeDeclaration):
			param_arity = len(referent.type_params)
			edges.append(referent)
		elif isinstance(referent, syntax.TypeParameter):
			param_arity = 0
		else:
			self.non_types.append(tc)
			return
		# a. Do we have the correct arity?
		arg_arity = len(tc.arguments)
		if arg_arity != param_arity:
			pattern = "%d type-arguments were given; %d are needed."
			self.on_error([tc], pattern % (arg_arity, param_arity))
		for arg in tc.arguments:
			self.visit(arg)

	def visit_Variant(self, v: syntax.Variant):
		# A variant cannot participate in an aliasing cycle because it is a nominal type.
		for st in v.subtypes:
			if st.body is not None:
				self.visit(st.body)
	
	def visit_Record(self, r:syntax.Record):
		self.visit(r.spec)
	
	def visit_RecordSpec(self, expr: syntax.RecordSpec):
		for f in expr.fields:
			self.visit(f)
	
	def visit_FormalParameter(self, param: syntax.FormalParameter):
		if param.type_expr is not None:
			self.visit(param.type_expr)
	
	def visit_ArrowSpec(self, expr:syntax.ArrowSpec):
		assert expr not in self.graph
		self.graph[expr] = list(expr.lhs)
		for p in expr.lhs:
			self.visit(p)
		if expr.rhs is not None:
			self.graph[expr].append(expr.rhs)
			self.visit(expr.rhs)

	def visit_ExplicitTypeVariable(self, expr:syntax.ExplicitTypeVariable): pass
	def visit_ImplicitTypeVariable(self, it:syntax.ImplicitTypeVariable): pass

	def visit_UserFunction(self, sym:syntax.UserFunction):
		for p in sym.params: self.visit(p)
		if sym.result_type_expr: self.visit(sym.result_type_expr)

	def visit_ImportForeign(self, d:syntax.ImportForeign):
		for group in d.groups:
			self.visit(group.type_expr)

def check_constructors(dubious_constructors:list[syntax.Reference], report:diagnostics.Report):
	bogons = [ref.head() for ref in dubious_constructors if not ref.dfn.has_value_domain()]
	if bogons: report.error("Checking Constructors", bogons, "These type-names are not data-constructors.")


