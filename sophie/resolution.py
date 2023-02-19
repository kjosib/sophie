"""
All the definition resolution stuff goes here.
By the time this pass is finished, every name points to its symbol table entry,
from which we can find the kind, type, and definition.
"""
from collections import defaultdict
from importlib import import_module
from boozetools.support.foundation import Visitor, strongly_connected_components_hashable
from boozetools.support.symtab import NoSuchSymbol, SymbolAlreadyExists
from . import syntax
from .ontology import NS, Symbol, Nom, MatchProxy
from .primitive import PrimitiveType

def resolve_words(module: syntax.Module, outside: NS, report):
	"""
	At the end of this action, every name-reference in the source text is visible where it's used.
	That is, a corresponding definition-object is in scope. It may not make sense,
	or be the right kind of name, but at least it's not an obvious misspelling.
	
	This will not be able to handle field-access (or keyword-args, etc) in the first instance,
	because those depend on some measure of type resolution. And to keep things simple,
	I'm going to worry about that part in a separate pass.
	"""
	assert isinstance(module, syntax.Module)
	if not report.issues:
		WordDefiner(module, outside, report.on_error("Defining words"))
	if not report.issues:
		StaticDepthPass(module)
		WordResolver(module, report.on_error("Finding Definitions"))
	if not report.issues:
		build_match_dispatch_tables(module, report.on_error("Validating Match Cases"))
	if not report.issues:
		AliasChecker(module, report.on_error("Circular reasoning"))

class WordPass(Visitor):
	""" Simple pass-through for word-agnostic expression syntax. """
	def visit_Literal(self, l:syntax.Literal, env:NS): pass
	
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

class WordDefiner(WordPass):
	"""
	At the end of this phase:
		Names used in declarations have an attached symbol table entry.
		The entry is installed in all appropriate namespaces.
		
	Attaches NameSpace objects in key places and install definitions.
	Takes note of names with more than one definition in the same scope.
	"""
	globals : NS
	
	def __init__(self, module:syntax.Module, outer:NS, on_error):
		self.redef, self.missing_foreign, self.broken_foreign = [], [], []
		self.globals = module.globals = outer.new_child(module)
		self.all_match_expressions = module.all_match_expressions = []
		self.all_functions = module.all_functions = []
		for td in module.types:
			self.visit(td)
		for d in module.foreign:
			self.visit(d, module.globals)
		if self.missing_foreign:
			on_error(self.missing_foreign, "Some foreign code could not be found.")
		if self.broken_foreign:
			on_error(self.broken_foreign, "Attempting to import this module threw an exception.")
		for fn in module.outer_functions:  # Can't iterate all-functions yet; must build it first.
			self.visit(fn, module.globals)
		if self.redef:
			on_error(self.redef, "I see the same name defined earlier in the same scope:")

	def _install(self, namespace: NS, dfn:Symbol):
		try: namespace[dfn.nom.text] = dfn
		except SymbolAlreadyExists: self.redef.append(dfn.nom)
	
	def visit_TypeDecl(self, td:syntax.TypeDecl):
		td.namespace = self.globals.new_child(td)
		quantifiers = []
		for param in td.parameters:
			self._install(td.namespace, param)
			param.quantifiers = ()
			quantifiers.append(param.typ)
		self.visit(td.body)
		self._install(self.globals, td)
		td.quantifiers = tuple(quantifiers)

	def visit_VariantSpec(self, vs:syntax.VariantSpec):
		vs.namespace = NS(place=vs)
		for subtype in vs.subtypes:
			assert isinstance(subtype, syntax.SubTypeSpec)
			self._install(self.globals, subtype)
			self._install(vs.namespace, subtype)
			if subtype.body is not None:
				self.visit(subtype.body)
		return

	def visit_RecordSpec(self, rs:syntax.RecordSpec):
		# Ought to have a local name-space with names having types.
		rs.namespace = NS(place=rs)
		for f in rs.fields:
			self._install(rs.namespace, f)
		return

	def visit_ArrowSpec(self, it:syntax.ArrowSpec):
		pass

	def visit_TypeCall(self, it:syntax.TypeCall):
		pass

	def visit_Function(self, fn:syntax.Function, env:NS):
		self.all_functions.append(fn)
		self._install(env, fn)
		inner = fn.namespace = env.new_child(fn)
		for param in fn.params:
			self._install(inner, param)
		for sub_fn in fn.where:
			self.visit(sub_fn, inner)
		self.visit(fn.expr, inner) # Might need to deal with let-expressions.
	
	def visit_Lookup(self, l:syntax.Lookup, env:NS): pass

	def visit_MatchExpr(self, mx:syntax.MatchExpr, env:NS):
		self.all_match_expressions.append(mx)
		for alt in mx.alternatives:
			self.visit(alt, env, mx.subject)
		if mx.otherwise is not None:
			self.visit(mx.otherwise, env)

	def visit_Alternative(self, alt: syntax.Alternative, env: NS, subject: Nom):
		inner = alt.namespace = env.new_child(alt)
		inner[subject.text] = alt.proxy = MatchProxy(subject)
		for sub_ex in alt.where:
			self.visit(sub_ex, inner)
		self.visit(alt.sub_expr, inner)
	
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
	

class StaticDepthPass(WordPass):
	# Assign static depth to the definitions of all parameters and functions.
	# This pass cannot fail.
	def __init__(self, module):
		for fn in module.outer_functions:
			self.visit_Function(fn, 0)
		for expr in module.main:
			self.visit(expr, 0)
			
	def visit_Function(self, fn:syntax.Function, depth:int):
		fn.static_depth = depth
		inner = depth + (1 if fn.params else 0)
		for param in fn.params:
			param.static_depth = inner
		self.visit(fn.expr, inner)
		for sub_fn in fn.where:
			self.visit_Function(sub_fn, inner)
		
	def visit_MatchExpr(self, mx:syntax.MatchExpr, depth:int):
		for alt in mx.alternatives:
			alt.proxy.static_depth = depth
			self.visit(alt.sub_expr, depth)
		if mx.otherwise is not None:
			self.visit(mx.otherwise, depth)

	def visit_Lookup(self, l:syntax.Lookup, depth:int):
		assert not hasattr(l, "source_depth")
		l.source_depth = depth


class WordResolver(WordPass):
	"""
	Walk the tree looking for undefined words in each static scope.
	Report on every such occurrence.
	If this pass succeeds, every syntax.Name object is connected to its corresponding symbol table entry.
	This is also a good place to pick up interesting lists of syntax objects, such as all match-cases.
	"""
	def __init__(self, module:syntax.Module, on_error):
		self.undef:list[syntax.Nom] = []
		self.non_value:list[syntax.Reference] = []
		self.module = module
		for td in module.types:
			self.visit(td)
		for d in module.foreign:
			self.visit(d)
		for fn in module.all_functions:
			self.visit(fn)
		for expr in module.main:
			self.visit(expr, module.globals)
		if self.undef:
			on_error(self.undef, "I do not see an available definition for:")
		if self.non_value:
			on_error(self.non_value, "This word is defined only in type context, not value context:")
	
	def visit_TypeDecl(self, td:syntax.TypeDecl):
		self.visit(td.body, td.namespace)
	
	def visit_ArrowSpec(self, it: syntax.ArrowSpec, env: NS):
		for a in it.lhs:
			self.visit(a, env)
		self.visit(it.rhs, env)
	
	def visit_VariantSpec(self, vs:syntax.VariantSpec, env:NS):
		for st in vs.subtypes:
			if st.body is not None:
				self.visit(st.body, env)
			pass
	
	def visit_RecordSpec(self, rs:syntax.RecordSpec, env:NS):
		for f in rs.fields:
			self.visit(f.type_expr, env)
	
	def _lookup(self, nom:syntax.Nom, env:NS):
		try:
			return env[nom.text]
		except NoSuchSymbol:
			self.undef.append(nom)

	def visit_PlainReference(self, ref:syntax.PlainReference, env:NS):
		# This kind of reference searches the local-scoped name-space
		ref.dfn = self._lookup(ref.nom, env)
	
	def visit_QualifiedReference(self, ref:syntax.QualifiedReference, env:NS):
		# Search among imports.
		space = self._lookup(ref.space, self.module.module_imports)
		ref.dfn = self._lookup(ref.nom, space) if space else None
	
	def visit_TypeCall(self, tc:syntax.TypeCall, env:NS):
		self.visit(tc.ref, env)
		for p in tc.arguments:
			self.visit(p, env)

	def visit_Function(self, fn:syntax.Function):
		for param in fn.params:
			if param.type_expr is not None:
				self.visit(param.type_expr, self.module.globals)
		if fn.result_type_expr is not None:
			self.visit(fn.result_type_expr, self.module.globals)
		self.visit(fn.expr, fn.namespace)

	def visit_MatchExpr(self, mx:syntax.MatchExpr, env:NS):
		mx.subject_dfn = self._lookup(mx.subject, env)
		for alt in mx.alternatives:
			self.visit(alt.pattern, self.module.globals)
			inner = alt.namespace
			self.visit(alt.sub_expr, inner)
			for sub_ex in alt.where:
				self.visit(sub_ex)
		if mx.otherwise is not None:
			self.visit(mx.otherwise, env)
			
	def visit_Lookup(self, expr: syntax.Lookup, env: NS):
		self.visit(expr.ref, env)
		dfn = expr.ref.dfn
		if dfn is not None and not dfn.has_value_domain():
			self.non_value.append(expr.ref)

	def visit_ImportForeign(self, d:syntax.ImportForeign):
		for group in d.groups:
			self.visit(group.type_expr, self.module.globals)

def build_match_dispatch_tables(module: syntax.Module, on_error):
	""" The simple evaluator uses these. """
	for mx in module.all_match_expressions:
		mx.dispatch = {}
		seen = {}
		for alt in mx.alternatives:
			key = alt.pattern.nom.key()
			if key in seen:
				on_error([seen[key], alt.pattern], "Duplication here...")
			else:
				mx.dispatch[key] = alt.sub_expr
		

class AliasChecker(Visitor):
	"""
	Check for aliases being well-founded, up front before getting caught in a loop later:
	There should be no cycles in the aliasing dependency graph, and no wrong-kind references.
	Also re-orders type definitions in order of alias topology.
	"""
	
	def __init__(self, module: syntax.Module, on_error):
		self.on_error = on_error
		self.non_types = []
		self.non_values = []
		self.graph = defaultdict(list)
		for td in module.types:
			self.visit(td)
		for d in module.foreign:
			self.visit(d)
		for fn in module.all_functions:
			self.visit_Function(fn)
		for expr in module.main:
			self.visit(expr)
		if self.non_types:
			self.on_error(self.non_types, "Need a type-name here; found this instead.")
		if self.non_values:
			self.on_error(self.non_values, "Need a value-name or constructor here; found this type-name instead.")
		alias_order = []
		ok = True
		for scc in strongly_connected_components_hashable(self.graph):
			if len(scc) == 1:
				node = scc[0]
				if node in self.graph[node]:
					self.on_error([node], "This is a circular.")
				elif isinstance(node, syntax.TypeDecl):
					alias_order.append(node)
			else:
				self.on_error(scc, "These make a circular definition.")
				ok = False
		if ok:
			assert len(alias_order) == len(module.types)
			module.types = alias_order
	pass
	
	def visit_TypeDecl(self, td:syntax.TypeDecl):
		self.graph[td].append(td.body)
		self.visit(td.body)
	
	def visit_FormalParameter(self, param:syntax.FormalParameter):
		if param.type_expr is not None:
			self.visit(param.type_expr)
	
	def visit_TypeCall(self, expr:syntax.TypeCall):
		referent = expr.ref.dfn
		arg_arity = len(expr.arguments)
		if isinstance(referent, syntax.TypeDecl):
			param_arity = len(referent.parameters)
			self.graph[expr].append(referent)
		elif isinstance(referent, (PrimitiveType, syntax.TypeParameter)):
			param_arity = 0
		else:
			self.non_types.append(expr)
			return
		self.graph[expr].extend(expr.arguments)
		# a. Do we have the correct arity?
		if arg_arity != param_arity:
			pattern = "%d type-arguments were given; %d are needed."
			self.on_error([expr], pattern % (arg_arity, param_arity))
		for arg in expr.arguments:
			self.visit(arg)

	def visit_VariantSpec(self, expr: syntax.VariantSpec):
		for alt in expr.subtypes:
			if alt.body is not None:
				self.visit(alt.body)
	def visit_RecordSpec(self, expr: syntax.RecordSpec):
		for f in expr.fields:
			self.visit(f)
	def visit_ArrowSpec(self, expr:syntax.ArrowSpec):
		self.graph[expr].extend(expr.lhs)
		for p in expr.lhs:
			self.visit(p)
		if expr.rhs is not None:
			self.graph[expr].append(expr.rhs)
			self.visit(expr.rhs)

	def visit_Function(self, fn:syntax.Function):
		for p in fn.params:
			self.visit(p)
		if fn.result_type_expr:
			self.visit(fn.result_type_expr)
		self.graph[fn].append(fn.expr)
		self.visit(fn.expr)

	def visit_MatchExpr(self, mx: syntax.MatchExpr):
		self.graph[mx].append(mx.subject_dfn)
	
	def visit_Cond(self, expr: syntax.Cond):
		self.graph[expr].append(expr.if_part)
		self.visit(expr.if_part)
	
	def visit_Call(self, expr: syntax.Call):
		self.graph[expr].append(expr.fn_exp)
		self.visit(expr.fn_exp)
	
	def visit_BinExp(self, expr: syntax.BinExp):
		for s in expr.lhs, expr.rhs:
			self.graph[expr].append(s)
			self.visit(s)
	
	def visit_ShortCutExp(self, expr: syntax.ShortCutExp):
		self.graph[expr].append(expr.lhs)
		self.visit(expr.lhs)
	
	def visit_UnaryExp(self, expr: syntax.UnaryExp):
		self.graph[expr].append(expr.arg)
		self.visit(expr.arg)
 	
	def visit_Lookup(self, lu: syntax.Lookup):
		dfn = lu.ref.dfn
		# Allow functions, parameters, and proper constructors.
		if dfn.has_value_domain():
			self.graph[lu].append(dfn)
		else:
			self.non_values.append(lu.ref)
	
	def visit_Literal(self, l:syntax.Literal):
		pass
	
	def visit_ExplicitList(self, l:syntax.ExplicitList):
		pass
	
	def visit_ImportForeign(self, d:syntax.ImportForeign):
		for group in d.groups:
			self.visit(group.type_expr)

