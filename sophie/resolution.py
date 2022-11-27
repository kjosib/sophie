"""
All the definition resolution stuff goes here.
By the time this pass is finished, every name points to its symbol table entry,
from which we can find the kind, type, and definition.
"""
from collections import defaultdict
from boozetools.support.foundation import Visitor, strongly_connected_components_hashable
from boozetools.support.symtab import NoSuchSymbol, SymbolAlreadyExists
from . import syntax, algebra
from .ontology import SymbolTableEntry, SyntaxNode, NS
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
		WordResolver(module, report.on_error("Finding Definitions"))
	if not report.issues:
		build_match_dispatch_tables(module, report.on_error("Validating Match Cases"))
	if not report.issues:
		AliasChecker(module, report.on_error("Circular reasoning"))

class WordDefiner(Visitor):
	"""
	At the end of this phase:
		Names used in declarations have an attached symbol table entry.
		The entry is installed in all appropriate namespaces.
		
	Attaches NameSpace objects in key places and install definitions.
	Takes note of names with more than one definition in the same scope.
	"""
	globals : NS
	
	def __init__(self, module:syntax.Module, outer:NS, on_error):
		self.redef = []
		self.globals = module.namespace = outer.new_child(module)
		for td in module.types:
			self.visit(td)
		for fn in module.functions:
			self.visit(fn, module.namespace)
		if self.redef:
			on_error(self.redef, "I see the same name defined earlier in the same scope:")

	def _install(self, namespace: NS, name: syntax.Name, dfn, typ=None):
		name.entry = SymbolTableEntry(name.key(), dfn, typ)
		self._import(namespace, name)
	
	def _import(self, namespace: NS, name: syntax.Name):
		try: namespace[name.key()] = name.entry
		except SymbolAlreadyExists: self.redef.append(name)
	
	def visit_TypeDecl(self, td:syntax.TypeDecl):
		td.namespace = self.globals.new_child(td)
		quantifiers = []
		for param in td.parameters:
			typ = algebra.TypeVariable()
			self._install(td.namespace, param.name, param, typ)
			param.name.entry.quantifiers = ()
			quantifiers.append(typ)
		self.visit(td.body)
		self._install(self.globals, td.name, td)
		td.name.entry.quantifiers = tuple(quantifiers)

	def visit_VariantSpec(self, vs:syntax.VariantSpec):
		vs.namespace = NS(place=vs)
		for summand in vs.alternatives:
			assert isinstance(summand, syntax.FormalParameter)
			self._install(vs.namespace, summand.name, summand)
			self._import(self.globals, summand.name)
			if summand.type_expr is not None:
				self.visit(summand.type_expr)
		return

	def visit_RecordSpec(self, rd:syntax.RecordSpec):
		# Ought to have a local name-space with names having types.
		rd.namespace = NS(place=rd)
		for f in rd.fields:
			self._install(rd.namespace, f.name, f)
		return

	def visit_ArrowSpec(self, it:syntax.ArrowSpec):
		pass

	def visit_Name(self, it:syntax.Name):
		pass

	def visit_TypeCall(self, it:syntax.TypeCall):
		pass

	def visit_Function(self, fn:syntax.Function, env:NS):
		inner = fn.namespace = env.new_child(fn)
		for param in fn.params:
			self._install(inner, param.name, param)
		self._install(env, fn.name, fn)
		fn.sub_fns = {}  # for simple evaluator
		for sub_fn in fn.where:
			sub_name = sub_fn.name
			self.visit(sub_fn, inner)
			fn.sub_fns[sub_name.text] = sub_fn
		del fn.where  # Don't need this anymore.


class WordResolver(Visitor):
	"""
	Walk the tree looking for undefined words in each static scope.
	Report on every such occurrence.
	If this pass succeeds, every syntax.Name object is connected to its corresponding symbol table entry.
	This is also a good place to pick up interesting lists of syntax objects, such as all match-cases.
	"""
	def __init__(self, module:syntax.Module, on_error):
		self.undef:list[syntax.Name] = []
		self.globals = module.namespace
		module.all_match_expressions = self.all_match_expressions = []
		for td in module.types:
			self.visit(td)
		for fn in module.functions:
			self.visit(fn)
		for expr in module.main:
			self.visit(expr, module.namespace)
		if self.undef:
			on_error(self.undef, "I do not see an available definition for:")
	
	def visit_TypeDecl(self, td:syntax.TypeDecl):
		self.visit(td.body, td.namespace)
		
	def visit_VariantSpec(self, it:syntax.VariantSpec, env:NS):
		for alt in it.alternatives:
			if alt.type_expr is not None:
				self.visit(alt.type_expr, env)
			pass
	
	def visit_RecordSpec(self, it:syntax.RecordSpec, env:NS):
		for f in it.fields:
			self.visit(f.type_expr, env)
			
	def visit_Name(self, name:syntax.Name, env:NS):
		try:
			name.entry = env[name.text]
		except NoSuchSymbol:
			self.undef.append(name)
	
	def visit_TypeCall(self, it:syntax.TypeCall, env:NS):
		self.visit(it.name, env)
		for p in it.arguments:
			self.visit(p, env)

	def visit_Function(self, fn:syntax.Function):
		for param in fn.params:
			if param.type_expr is not None:
				self.visit(param.type_expr, self.globals)
		if fn.expr_type is not None:
			self.visit(fn.expr_type, self.globals)
		self.visit(fn.expr, fn.namespace)
		for item in fn.sub_fns.values():
			self.visit(item)
	
	def visit_Literal(self, it:syntax.Literal, env:NS):
		pass
	
	def visit_ArrowSpec(self, it:syntax.ArrowSpec, env:NS):
		for a in it.lhs:
			self.visit(a, env)
		self.visit(it.rhs, env)

	def visit_ShortCutExp(self, it:syntax.ShortCutExp, env:NS):
		self.visit(it.lhs, env)
		self.visit(it.rhs, env)

	def visit_BinExp(self, it:syntax.BinExp, env:NS):
		self.visit(it.lhs, env)
		self.visit(it.rhs, env)

	def visit_UnaryExp(self, expr:syntax.UnaryExp, env:NS):
		self.visit(expr.arg, env)
	
	def visit_Lookup(self, expr:syntax.Lookup, env:NS):
		self.visit(expr.name, env)
	
	def visit_FieldReference(self, expr:syntax.FieldReference, env:NS):
		self.visit(expr.lhs, env)
		# Save expr.field_name for once types are more of a thing.
	
	def visit_Call(self, expr:syntax.Call, env:NS):
		self.visit(expr.fn_exp, env)
		for a in expr.args:
			self.visit(a, env)
	
	def visit_Cond(self, expr:syntax.Cond, env:NS):
		self.visit(expr.if_part, env)
		self.visit(expr.then_part, env)
		self.visit(expr.else_part, env)

	def visit_ExplicitList(self, expr:syntax.ExplicitList, env:NS):
		for e in expr.elts:
			self.visit(e, env)
	
	def visit_MatchExpr(self, mx:syntax.MatchExpr, env:NS):
		self.all_match_expressions.append(mx)
		self.visit(mx.name, env)
		for pattern, sub_expr in mx.alternatives:
			self.visit(pattern, self.globals)
			self.visit(sub_expr, env)
		if mx.otherwise is not None:
			self.visit(mx.otherwise, env)

def build_match_dispatch_tables(module: syntax.Module, on_error):
	""" The simple evaluator uses these. """
	for mx in module.all_match_expressions:
		mx.dispatch = {}
		seen = {}
		for alt in mx.alternatives:
			key = alt.pattern.key()
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
		self.graph : dict[SyntaxNode:list[SyntaxNode]] = defaultdict(list)
		for td in module.types:
			self.visit(td)
		for fn in module.functions:
			self.visit(fn)
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
		#assert td.name.entry.dfn is td
		self.graph[td].append(td.body)
		self.visit(td.body)
	
	def visit_FormalParameter(self, param:syntax.FormalParameter):
		if param.type_expr is not None:
			self.visit(param.type_expr)
	
	def visit_TypeCall(self, expr:syntax.TypeCall):
		referent = expr.name.entry.dfn
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
		for alt in expr.alternatives:
			self.visit(alt)
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
		if fn.expr_type:
			self.visit(fn.expr_type)
		self.graph[fn].append(fn.expr)
		self.visit(fn.expr)

	def visit_MatchExpr(self, expr: syntax.MatchExpr):
		self.graph[expr].append(expr.name.entry.dfn)
	
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
		dfn = lu.name.entry.dfn
		# Allow functions, parameters, and proper constructors.
		if dfn.has_value_domain():
			self.graph[lu].append(dfn)
		else:
			self.non_values.append(lu.name)
	
	def visit_Literal(self, l:syntax.Literal):
		pass
	
	def visit_ExplicitList(self, l:syntax.ExplicitList):
		pass
