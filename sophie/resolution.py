"""
All the definition resolution stuff goes here.
By the time this pass is finished, every name points to its symbol table entry,
from which we can find the kind, type, and definition.
"""
from importlib import import_module
from boozetools.support.foundation import Visitor, strongly_connected_components_hashable
from boozetools.support.symtab import NoSuchSymbol, SymbolAlreadyExists
from . import syntax, diagnostics
from .ontology import NS, Symbol

class _WordPass(Visitor):
	""" Simple pass-through for word-agnostic expression syntax. """
	def visit_ArrowSpec(self, it: syntax.ArrowSpec, env: NS):
		for a in it.lhs:
			self.visit(a, env)
		self.visit(it.rhs, env)
	
	def visit_Literal(self, l:syntax.Literal, env:NS): pass
	def visit_ImplicitType(self, it:syntax.ImplicitTypeVariable, env:NS): pass

	def visit_ShortCutExp(self, it: syntax.ShortCutExp, env: NS):
		self.visit(it.lhs, env)
		self.visit(it.rhs, env)
	
	def visit_BinExp(self, it: syntax.BinExp, env: NS):
		self.visit(it.lhs, env)
		self.visit(it.rhs, env)
	
	def visit_UnaryExp(self, expr: syntax.UnaryExp, env: NS):
		self.visit(expr.arg, env)
	
	def visit_FieldReference(self, expr: syntax.FieldReference, env: NS):
		# word-agnostic until we know the type of expr.lhs.
		self.visit(expr.lhs, env)
	
	def visit_Call(self, expr: syntax.Call, env: NS):
		self.visit(expr.fn_exp, env)
		for a in expr.args:
			self.visit(a, env)
	
	def visit_Cond(self, expr: syntax.Cond, env: NS):
		self.visit(expr.if_part, env)
		self.visit(expr.then_part, env)
		self.visit(expr.else_part, env)
	
	def visit_ExplicitList(self, expr: syntax.ExplicitList, env: NS):
		for e in expr.elts:
			self.visit(e, env)

class WordDefiner(_WordPass):
	"""
	At the end of this phase:
		Names used in declarations have an attached symbol table entry.
		The entry is installed in all appropriate namespaces.
		
	Attaches NameSpace objects in key places and install definitions.
	Takes note of names with more than one definition in the same scope.
	"""
	globals : NS
	
	def __init__(self, outer:NS, report):
		self._outer = outer
		self._on_error = report.on_error("Defining words")
		self.redef, self.missing_foreign, self.broken_foreign = [], [], []

	def _install(self, namespace: NS, dfn:Symbol):
		try: namespace[dfn.nom.text] = dfn
		except SymbolAlreadyExists: self.redef.append(dfn.nom)
	
	def _declare_type(self, td:syntax.TypeDeclaration):
		self._install(self.globals, td)
		ps = td.param_space = self.globals.new_child(place=td)
		for p in td.parameters:
			self._install(ps, p)
	
	def visit_Module(self, module:syntax.Module):
		self.globals = module.globals = self._outer.new_child(module)
		self.all_match_expressions = module.all_match_expressions = []
		self.all_functions = module.all_functions = []
		for td in module.types:
			self.visit(td)
		for d in module.foreign:
			self.visit(d, module.globals)
		if self.missing_foreign:
			self._on_error(self.missing_foreign, "Some foreign code could not be found.")
		if self.broken_foreign:
			self._on_error(self.broken_foreign, "Attempting to import this module threw an exception.")
		for fn in module.outer_functions:  # Can't iterate all-functions yet; must build it first.
			self.visit(fn, module.globals)
		for expr in module.main:  # Might need to define some case-match symbols here.
			self.visit(expr, module.globals)
		if self.redef:
			self._on_error(self.redef, "I see the same name defined earlier in the same scope:")

	
	def visit_Opaque(self, o:syntax.Opaque):
		self._install(self.globals, o)
		if o.parameters:
			self._on_error(o.parameters, "Opaque types are not to be made generic.")
	
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

	def visit_UserDefinedFunction(self, fn:syntax.UserDefinedFunction, env:NS):
		self.all_functions.append(fn)
		self._install(env, fn)
		inner = fn.namespace = env.new_child(fn)
		for param in fn.params:
			self.visit(param, inner)
		if fn.result_type_expr is not None:
			self.visit(fn.result_type_expr, inner)
		for sub_fn in fn.where:
			self.visit(sub_fn, inner)
		self.visit(fn.expr, inner)
	
	def visit_FormalParameter(self, fp:syntax.FormalParameter, env:NS):
		self._install(env, fp)
		if fp.type_expr is not None:
			self.visit(fp.type_expr, env)
	
	def visit_ExplicitTypeVariable(self, gt:syntax.ExplicitTypeVariable, env:NS):
		if gt.nom.text not in env:
			self._install(env, syntax.TypeParameter(gt.nom))
	
	def visit_Lookup(self, l:syntax.Lookup, env:NS): pass

	def visit_MatchExpr(self, mx:syntax.MatchExpr, env:NS):
		self.all_match_expressions.append(mx)
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
	
	def visit_ImportForeign(self, d:syntax.ImportForeign, env:NS):
		try: py_module = import_module(d.source.value)
		except ModuleNotFoundError: self.missing_foreign.append(d.source)
		except ImportError: self.broken_foreign.append(d.source)
		else:
			for group in d.groups:
				for sym in group.symbols:
					self.visit(sym, env, py_module)
	
	def visit_FFI_Alias(self, sym:syntax.FFI_Alias, env:NS, py_module):
		key = sym.nom.text if sym.alias is None else sym.alias.value
		try: sym.val = getattr(py_module, key)
		except KeyError: self.missing_foreign.append(sym)
		else: self._install(env, sym)
	

class StaticDepthPass(_WordPass):
	# Assign static depth to the definitions of all parameters and functions.
	# This pass cannot fail.
	def __init__(self, module):
		for fn in module.outer_functions:
			self.visit_UserDefinedFunction(fn, 0)
		for expr in module.main:
			self.visit(expr, 0)
			
	def visit_UserDefinedFunction(self, fn:syntax.UserDefinedFunction, depth:int):
		fn.static_depth = depth
		inner = depth + (1 if fn.params else 0)
		for param in fn.params:
			param.static_depth = inner
		self.visit(fn.expr, inner)
		for sub_fn in fn.where:
			self.visit_UserDefinedFunction(sub_fn, inner)
		
	def visit_MatchExpr(self, mx:syntax.MatchExpr, depth:int):
		mx.subject.static_depth = depth
		self.visit(mx.subject.expr, depth)
		for alt in mx.alternatives:
			self.visit(alt.sub_expr, depth)
		if mx.otherwise is not None:
			self.visit(mx.otherwise, depth)

	def visit_Lookup(self, l:syntax.Lookup, depth:int):
		assert not hasattr(l, "source_depth")
		l.source_depth = depth


class WordResolver(_WordPass):
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
	
	def __init__(self, module:syntax.Module, report):
		on_error = report.on_error("Finding Definitions")
		self.dubious_constructors = []
		self.undef:list[syntax.Nom] = []
		self.module = module
		for td in module.types:
			self.visit(td)
		for d in module.foreign:
			self.visit(d)
		for fn in module.all_functions:
			self.visit_UserDefinedFunction(fn)
		for expr in module.main:
			self.visit(expr, module.globals)
		if self.undef:
			on_error(self.undef, "I do not see an available definition for:")
	
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
		try:
			return env[nom.text]
		except NoSuchSymbol:
			self.undef.append(nom)
			return Bogon(nom)

	def visit_PlainReference(self, ref:syntax.PlainReference, env:NS):
		# This kind of reference searches the local-scoped name-space
		ref.dfn = self._lookup(ref.nom, env)
	
	def visit_QualifiedReference(self, ref:syntax.QualifiedReference, env:NS):
		# Search among imports.
		space = self._lookup(ref.space, self.module.module_imports)
		if isinstance(space, Bogon): return space
		ref.dfn = self._lookup(ref.nom, space)
	
	def visit_GenericType(self, ref:syntax.ExplicitTypeVariable, env:NS):
		ref.dfn = self._lookup(ref.nom, env)
	
	def visit_TypeCall(self, tc:syntax.TypeCall, env:NS):
		self.visit(tc.ref, env)
		for p in tc.arguments:
			self.visit(p, env)

	def visit_UserDefinedFunction(self, fn:syntax.UserDefinedFunction):
		for param in fn.params:
			if param.type_expr is not None:
				self.visit(param.type_expr, fn.namespace)
		if fn.result_type_expr is not None:
			self.visit(fn.result_type_expr, fn.namespace)
		self.visit(fn.expr, fn.namespace)

	def visit_MatchExpr(self, mx:syntax.MatchExpr, env:NS):
		self.visit(mx.subject.expr, env)
		for alt in mx.alternatives:
			self.visit(alt.pattern, self.module.globals)
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
		for group in d.groups:
			self.visit(group.type_expr, self.module.globals)

class Bogon(syntax.Symbol):
	
	def has_value_domain(self) -> bool:
		return False
	

class AliasChecker(Visitor):
	"""
	Check the arity of TypeCall forms.
	Check for aliases being well-founded, up front before getting caught in a loop later:
	There should be no cycles in the aliasing dependency graph, and no wrong-kind references.
	Also re-orders type definitions in order of alias topology.
	
	Stop worrying about function cycles; I'll catch that problem in the type checker.
	"""
	
	def __init__(self, module: syntax.Module, report: diagnostics.Report):
		self.on_error = report.on_error("Circular reasoning")
		self.non_types = []
		self.graph = {td:[] for td in module.types}
		for td in module.types:
			self.visit(td)
		for d in module.foreign:
			self.visit(d)
		for fn in module.all_functions:
			self.visit(fn)
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
	
	def visit_TypeAlias(self, ta:syntax.TypeAlias):
		self.graph[ta].append(ta.body)
		self.visit(ta.body)
	
	def visit_TypeCall(self, tc:syntax.TypeCall):
		assert tc not in self.graph
		self.graph[tc] = edges = list(tc.arguments)
		referent = tc.ref.dfn
		if isinstance(referent, syntax.TypeDeclaration):
			param_arity = len(referent.parameters)
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

	def visit_UserDefinedFunction(self, fn:syntax.UserDefinedFunction):
		for p in fn.params:
			self.visit(p)
		if fn.result_type_expr:
			self.visit(fn.result_type_expr)
	
	def visit_ImportForeign(self, d:syntax.ImportForeign):
		for group in d.groups:
			self.visit(group.type_expr)

def check_constructors(dubious_constructors:list[syntax.Reference], report:diagnostics.Report):
	bogons = [ref.head() for ref in dubious_constructors if not ref.dfn.has_value_domain()]
	if bogons: report.error("Checking Constructors", bogons, "These type-names are not data-constructors.")

def check_all_match_expressions(module: syntax.Module, report):
	on_match_error = report.on_error("Checking Type-Case Matches")
	for mx in module.all_match_expressions:
		_check_one_match_expression(mx, on_match_error)

def _check_one_match_expression(mx:syntax.MatchExpr, on_error):
	non_subtypes = []
	duplicates = set()
	first = {}
	
	subtypes : list[syntax.SubTypeSpec] = []
	
	for alt in mx.alternatives:
		dfn = alt.pattern.dfn
		if isinstance(dfn, syntax.SubTypeSpec):
			subtypes.append(dfn)
			if dfn in first:
				duplicates.add(first[dfn])
				duplicates.add(alt.pattern)
			else:
				first[dfn] = alt.pattern
		else:
			non_subtypes.append(alt.pattern)
	
	if non_subtypes:
		on_error(non_subtypes, "This case is not a member of any variant.")
	if duplicates:
		on_error(list(duplicates), "Duplicate cases here...")
	if non_subtypes or duplicates:
		return
	
	primary_variant = subtypes[0].variant
	mistypes = [alt.pattern for alt in mx.alternatives if alt.pattern.dfn.variant is not primary_variant]
	
	if mistypes:
		on_error([mx.alternatives[0].pattern] + mistypes, "These do not all come from the same variant type.")
		return

	mx.variant = primary_variant
	exhaustive = len(first) == len(primary_variant.subtypes)
	if exhaustive and mx.otherwise:
		on_error([mx, mx.otherwise], "This case-construction is exhaustive; the else-clause cannot happen.")
	if not (exhaustive or mx.otherwise):
		on_error([mx], "This case-construction does not cover all the cases of <%s> and lacks an otherwise-clause." % mx.variant.nom.text)
	pass

def build_match_dispatch_tables(module: syntax.Module):
	""" The simple evaluator uses these. """
	for mx in module.all_match_expressions:
		mx.dispatch = {}
		for alt in mx.alternatives:
			key = alt.pattern.nom.key()
			mx.dispatch[key] = alt.sub_expr


