"""
The set of parse-nodes in simple form.
The parser calls these constructors with subordinate semantic-values in a bottom-up tree transduction.
These constructors may add a little or a lot of of organization.
Class-level type annotations make peace with pycharm wherever later passes add fields.
"""
from pathlib import Path
from typing import Optional, Any, Sequence, NamedTuple, Union
from boozetools.parsing.interface import SemanticError
from .ontology import (
	TypeExpression, ValueExpression, Phrase,
	Nom, Symbol, TypeSymbol, TermSymbol, MemoSchedule
)
from .space import Layer



class MismatchedBookendsError(SemanticError):
	# The one semantic error we catch early enough to interrupt the parse.
	# It's early warning that things have gotten out of whack.
	def __init__(self, head: Nom, coda: Nom):
		super().__init__(head, coda)

class Reference(Phrase):
	nom:Nom
	dfn:Symbol   # Should happen during WordResolver pass.
	def __init__(self, nom:Nom): self.nom = nom
	def left(self): return self.nom.left()
	def right(self): return self.nom.right()

class PlainReference(Reference):
	def __repr__(self): return "<ref:%s>"%self.nom.text

class SelfReference(Reference):
	def __repr__(self): return "<SELF>"

class MemberReference(Reference):
	def __repr__(self): return "<my %s>"%self.nom.text
	def left(self): return self.nom.left() - 1

class QualifiedReference(Reference):
	space: Nom
	def __init__(self, nom:Nom, space:Nom):
		super().__init__(nom)
		self.space = space
	def right(self): return self.space.right()

class TypeParameter(TypeSymbol):
	def type_arity(self): return 0

class TypeDefinition(TypeSymbol):
	type_params: tuple[TypeParameter, ...] = ()
	def __init__(self, nom: Nom, param_names):
		super().__init__(nom)
		self.type_params = type_parameters(param_names)
	def type_arity(self): return len(self.type_params)
	def as_token(self): return self
	def right(self): return (self.type_params[-1] if self.type_params else self.nom).right()

def type_parameters(param_names) -> tuple[TypeParameter, ...]:
	return tuple(TypeParameter(n) for n in param_names or ())

class ArrowSpec(TypeExpression):
	lhs: Sequence[TypeExpression]
	_head: Nom
	rhs: TypeExpression
	
	def __init__(self, lhs, _head:Nom, rhs):
		assert rhs is not None
		self.lhs = lhs
		self.rhs = rhs
	def left(self): return self.lhs[0].left()
	def right(self): return self.rhs.right()
	def dispatch_token(self): return None

class MessageSpec(TypeExpression):  # The anonymous kind that shows up in signatures
	type_exprs: Sequence[TypeExpression]
	def __init__(self, _head:Nom, type_exprs):
		self._head = _head
		self.type_exprs = type_exprs or ()
	def left(self): return self._head.left()
	def right(self): return (self.type_exprs[-1] if self.type_exprs else self._head).right()
	def dispatch_token(self): return None

class TypeCall(TypeExpression):
	def __init__(self, ref: Reference, arguments: Optional[Sequence[TypeExpression]] = ()):
		assert isinstance(ref, Reference)
		self.ref, self.arguments = ref, arguments or ()
	def left(self): return self.ref.left()
	def right(self): return (self.arguments[-1] if self.arguments else self.ref).right()
	def dispatch_token(self):
		symbol = self.ref.dfn
		assert isinstance(symbol, TypeDefinition)
		return symbol.as_token()
	def __repr__(self):
		return "%s[%s]"%(self.ref, self.arguments) if self.arguments else repr(self.ref)

class TypeCapture(TypeExpression):
	type_parameter: TypeParameter
	def __init__(self, _hook, nom:Nom):
		self._hook = _hook
		self.nom = nom
	def dispatch_token(self): return None

class FreeType(TypeExpression):
	def __init__(self, head:Nom):
		self._head = head
	def dispatch_token(self): return None
	
class FormalParameter(TermSymbol):
	def __init__(self, stricture, nom:Nom, type_expr: Optional[TypeExpression]):
		super().__init__(nom)
		self.is_strict = stricture is not None
		self.type_expr = type_expr
	def key(self): return self.nom.key()
	def __repr__(self): return "<:%s:%s>"%(self.nom.text, self.type_expr)
	def dispatch_token(self):
		""" The outermost symbol in the type-expr, if at all possible. """
		if self.type_expr:
			return self.type_expr.dispatch_token()

def FieldDefinition(nom:Nom, type_expr: Optional[TypeExpression]):
	return FormalParameter(None, nom, type_expr)

class OpaqueSymbol(TypeDefinition):
	pass

class RecordSpec:
	field_space:Layer[FormalParameter]  # Resolver fills this in.
	def __init__(self, fields: list[FormalParameter]):
		assert all(isinstance(f, FormalParameter) for f in fields)
		self.fields = fields
	
	def field_names(self):
		return [f.nom.text for f in self.fields]

class RecordSymbol(TypeDefinition):
	spec: RecordSpec
	def __init__(self, nom: Nom, param_names, spec:RecordSpec):
		super().__init__(nom, param_names)
		self.spec = spec

class TypeAliasSymbol(TypeDefinition):
	type_expr: TypeExpression
	def __init__(self, nom: Nom, param_names, type_expr:TypeExpression):
		super().__init__(nom, param_names)
		self.type_expr = type_expr
	def as_token(self): return self.type_expr.dispatch_token()

class VariantSymbol(TypeDefinition):
	sub_space: dict[str, "TypeCase"]  # For checking match exhaustiveness.
	
	def __init__(self, nom, param_names, type_cases: list["TypeCase"]):
		super().__init__(nom, param_names)
		self.type_cases = type_cases
		self.sub_space = {}
		for st in type_cases:
			st.variant = self
			self.sub_space[st.nom.key()] = st

class Ability(Symbol):
	def __init__(self, nom:Nom, type_exprs:Sequence[TypeExpression]):
		super().__init__(nom)
		self.type_exprs = type_exprs or ()

class RoleSymbol(TypeDefinition):
	ability_space: Layer[Ability]  # Resolver supplies this
	def __init__(self, nom, param_names, abilities:Sequence[Ability]):
		super().__init__(nom, param_names)
		self.abilities = abilities
	def as_token(self): return None

class TypeCase(TypeSymbol):
	variant: VariantSymbol  # Inherited attribute: Variant constructor fills this in.
	def __repr__(self): return "<%s>"%self.nom.text
	def as_token(self): return self.variant
	def type_arity(self): return self.variant.type_arity()

class EnumTag(TypeCase):
	pass

class RecordTag(TypeCase):
	spec: RecordSpec
	def __init__(self, nom:Nom, spec: RecordSpec):
		super().__init__(nom)
		self.spec = spec

class Assumption(NamedTuple):
	names: list[Nom]
	type_expr: TypeExpression

def _bookend(head: Nom, where: Optional["WhereClause"]) -> Sequence["Subroutine"]:
	if where is None: return ()
	if head.text == where.coda.text:
		return where.sub_fns
	else:
		raise MismatchedBookendsError(head, where.coda)

class Subroutine(TermSymbol):
	source_path: Path
	params: Sequence[FormalParameter]
	result_type_expr: Optional[TypeExpression]
	expr: ValueExpression
	where: Sequence["Subroutine"]
	captures: set[TermSymbol]  # Resolver builds this.
	memo_schedule: MemoSchedule
	strictures: tuple[int, ...]  # Tree-walking runtime uses this.
	def is_thunk(self) -> bool:
		""" So the compiler can decide how to encode these things """
		raise NotImplementedError(type(self))

class WhereClause(NamedTuple):
	sub_fns: Sequence[Subroutine]
	coda: Nom

class UserFunction(Subroutine):
	def __init__(
			self,
			nom: Nom,
			params: Sequence[FormalParameter],
			expr_type: Optional[TypeExpression],
			expr: ValueExpression,
			where: Optional[WhereClause]
	):
		super().__init__(nom)
		self.params = params or ()
		self.result_type_expr = expr_type
		self.expr = expr
		self.where = _bookend(nom, where)
			
	def right(self): return self.expr.left() - 1
	
	def is_thunk(self) -> bool:
		return not self.params
	
	def __repr__(self):
		p = ", ".join(map(str, self.params))
		return "{fn|%s(%s)}" % (self.nom.text, p)

class UserOperator(UserFunction):
	"""
	An operator is just a function with a funny name
	and some special syntax and calling conventions. 
	"""
	def __init__(self, nom: Nom, params: Sequence[FormalParameter], expr_type: Optional[TypeExpression], expr: ValueExpression, where: Optional["WhereClause"]):
		super().__init__(nom, params, expr_type, expr, where)
		for fp in self.params:
			fp.is_strict = True
	
	def dispatch_vector(self):
		return tuple(fp.dispatch_token() for fp in self.params)

class UserProcedure(Subroutine):
	result_type_expr = None  # Simplifies the resolver.
	
	def __repr__(self):
		p = ", ".join(map(str, self.params))
		return "{to %s(%s)}" % (self.nom.text, p)
	def __init__(
		self,
		nom: Nom,
		params: Sequence[FormalParameter],
		expr: ValueExpression,
		where: Optional[WhereClause]
	):
		super().__init__(nom)
		self.params = params or ()
		for p in self.params: p.is_strict = True
		self.expr = expr
		self.where = _bookend(nom, where)
	
	def left(self): return self.nom.left() - 1
	def right(self): return self.expr.left() - 1
	def is_thunk(self) -> bool:
		return False

class UserActor(TermSymbol):
	fields: Sequence[FormalParameter]
	behaviors: Sequence[UserProcedure]
	field_space: Layer[FormalParameter]  # Resolver supplies this
	behavior_space: Layer[UserProcedure]  # Resolver supplies this
	def left(self): return self.nom.left() - 1
	def __init__(
		self,
		nom: Nom,
		members: Optional[Sequence[FormalParameter]],
		behaviors: Sequence[UserProcedure],
		coda: Nom,
	):
		super().__init__(nom)
		self.fields = members or ()
		self.behaviors = behaviors
		if nom.text != coda.text:
			raise MismatchedBookendsError(nom, coda)

	def member_names(self):
		return [f.nom.text for f in self.fields]

class Literal(ValueExpression):
	def __init__(self, value: Any, spot: int):
		assert isinstance(spot, int) or spot is None, type(spot)
		self.value, self._spot = value, spot
	
	def __str__(self): return "<Literal %r>" % self.value
	def left(self): return self._spot
	def right(self): return self._spot

def truth(token:Nom): return Literal(True, token.spot)
def falsehood(token:Nom): return Literal(False, token.spot)

class Lookup(ValueExpression):
	# Reminder: This AST node exists in opposition to TypeCall so I can write
	# behavior for references in value context vs. references in type context.
	ref:Reference
	def __init__(self, ref: Reference): self.ref = ref
	def __str__(self): return str(self.ref)
	def left(self): return self.ref.left()
	def right(self): return self.ref.right()

class FieldReference(ValueExpression):
	def __init__(self, lhs: ValueExpression, field_name: Nom):
		self.lhs, self.field_name = lhs, field_name
	def __str__(self): return "(%s.%s)" % (self.lhs, self.field_name.text)
	def left(self): return self.lhs.left()
	def right(self): return self.field_name.right()

class BindMethod(ValueExpression):
	def __init__(self, receiver: ValueExpression, _bang:Nom, method_name: Nom):
		self.receiver, self.method_name = receiver, method_name
	def __str__(self): return "(%s.%s)" % (self.receiver, self.method_name.text)
	def left(self): return self.method_name.left()-1
	def right(self): return self.method_name.right()

class AsTask(ValueExpression):
	def __init__(self, bang:Nom, proc_ref:ValueExpression):
		self._bang = bang
		self.proc_ref = proc_ref
	def left(self): return self._bang.left()
	def right(self): return self.proc_ref.right()

class Skip(ValueExpression):
	def __init__(self, head: Nom): self._head = head
	def left(self): return self._head.left()
	def right(self): return self._head.right()

class Binary(ValueExpression):
	def __init__(self, lhs: ValueExpression, op:Nom, rhs: ValueExpression):
		self.lhs, self.op, self.rhs = lhs, op, rhs
	def left(self): return self.lhs.left()
	def right(self): return self.rhs.right()

class BinExp(Binary): pass
class ShortCutExp(Binary): pass

class UnaryExp(ValueExpression):
	def __init__(self, op:Nom, arg: ValueExpression):
		self.op, self.arg = op, arg

	def left(self): return self.op.left()
	def right(self): return self.arg.right()

class Cond(ValueExpression):
	def __init__(self, then_part: ValueExpression, _kw:Nom, if_part: ValueExpression, else_part: ValueExpression):
		self.then_part, self.if_part, self.else_part = then_part, if_part, else_part
	def left(self): return self.then_part.left()
	def right(self): return self.else_part.right()

def CaseWhen(when_parts: list, else_part: ValueExpression):
	for _kw, test, then in reversed(when_parts):
		else_part = Cond(then, _kw, test, else_part)
	return else_part

class Call(ValueExpression):
	def __init__(self, fn_exp: ValueExpression, args: list[ValueExpression]):
		self.fn_exp, self.args = fn_exp, args
	
	def __str__(self):
		return "%s(%s)" % (self.fn_exp, ', '.join(map(str, self.args)))
	
	def left(self): return self.fn_exp.left()
	def right(self): return self.args[-1].right()

def call_upon_list(fn_exp: ValueExpression, list_arg: ValueExpression):
	return Call(fn_exp, [list_arg])

class ExplicitList(ValueExpression):
	def __init__(self, elts: list[ValueExpression]):
		for e in elts:
			assert isinstance(e, ValueExpression), e
		self.elts = elts
		
	def left(self): return self.elts[0].left()
	def right(self): return self.elts[-1].right()

class Alternative:
	pattern: Nom
	dfn: TypeCase  # Either the match-check pass or the type-checker fills this.
	sub_expr: ValueExpression
	where: Sequence[Subroutine]
	
	def __init__(self, pattern:Nom, _arrow:Nom, sub_expr:ValueExpression, where:Optional[WhereClause]):
		self.pattern = pattern
		self._arrow = _arrow
		self.sub_expr = sub_expr
		self.where = _bookend(pattern, where)
	def left(self): return self.pattern.left()
	def right(self): return self._arrow.right()
	
class Absurdity(ValueExpression):
	def __init__(self, keyword:Nom, reason:Optional[Literal]):
		self.keyword = keyword
		self.reason = reason
	def left(self): return self.keyword.left()
	def right(self): return (self.reason or self.keyword).right()

def absurdAlternative(pattern:Nom, _head:Nom, absurdity:Absurdity):
	return Alternative(pattern, _head, absurdity, None)
	
class Subject(TermSymbol):
	""" Within a match-case, a name must reach a different symbol with the particular subtype """
	expr: ValueExpression
	def __init__(self, expr: ValueExpression, alias: Optional[Nom]):
		super().__init__(alias or _implicit_nom(expr))
		self.expr = expr

def _implicit_nom(expr: ValueExpression):
	if isinstance(expr, Lookup) and isinstance(expr.ref, PlainReference):
		return expr.ref.nom
	else:
		return Nom(_gensym(), expr.left() - 1)

_gs_count = 0
def _gensym():
	global _gs_count
	_gs_count += 1
	return "#gs:"+str(_gs_count)

class MatchExpr(ValueExpression):
	subject:Subject  # Symbol in scope within alternative expressions; contains the value of interest
	hint: Optional[Reference]
	alternatives: list[Alternative]
	otherwise: Optional[ValueExpression]
	
	variant:VariantSymbol  # Match-Check fills these two.
	dispatch: dict[Symbol:Alternative] # It is now part of the WordResolver pass.
	
	def __init__(self, subject, hint, alternatives, otherwise):
		self.subject = subject
		self.hint = hint
		self.alternatives, self.otherwise = alternatives, otherwise
	
	def left(self): return self.subject.left()-1
	def right(self): return self.subject.right()

class NewActor(TermSymbol):
	def __init__(self, nom:Nom, expr:ValueExpression):
		super().__init__(nom)
		self.expr = expr

class DoBlock(ValueExpression):
	# The value of a do-block does not depend on when it runs.
	# Its consequence may so depend, but by definition steps run in sequence.

	def __init__(self, actors:list[NewActor], keyword:Nom, steps:list[ValueExpression]):
		self.actors = actors
		self.steps = steps
		self._keyword = keyword
		
	def left(self): return self._keyword.left()
	def right(self): return self.steps[-1].right()

class AssignMember(Reference):
	def __init__(self, nom:Nom, expr:ValueExpression):
		super().__init__(nom)
		self.expr = expr
	def left(self): return self.nom.left() - 1
	def right(self): return self.nom.right() + 1

class LambdaForm(ValueExpression):
	# This is essentially a special kind of literal constant.
	# It happens to be connected to a function definition.
	def __init__(self, left:Nom, params:list[FormalParameter], body:ValueExpression, right:Nom):
		assert params
		self._left, self._right = left.left(), right.right()
		nom = Nom(_gensym(), self._left)
		self.function = UserFunction(nom, params, None, body, None)
		
	def left(self): return self._left
	def right(self): return self._right

class ImportSymbol(NamedTuple):
	yonder : Nom
	hither : Optional[Nom]

class ImportModule(Symbol):
	module_key: Path  # Module loader fills this.
	def __init__(self, package:Optional[Nom], relative_path:Literal, alias:Optional[Nom], vocab:Optional[Sequence[ImportSymbol]]):
		super().__init__(alias)
		self.package = package
		self.relative_path = relative_path
		self.vocab = vocab or ()

class FFI_Alias(TermSymbol):
	""" Built-in and foreign (Python) function symbols. """
	ffi_type: "FFI_Group"
	val:Any  # Fill in during WordDefiner pass
	
	def __init__(self, alias:Optional[Literal], nom:Nom):
		super().__init__(nom)
		self.alias = alias

def FFI_Symbol(nom:Nom): return FFI_Alias(None, nom)

class FFI_Operator(FFI_Alias):
	"""
	Similar to a UserOperator, this is just another foreign symbol
	with fun semantics. For obvious reasons, it must have an alias. 
	"""
	pass

class FFI_Group:
	def __init__(self, symbols:list[FFI_Alias], param_names:Optional[Sequence[Nom]], type_expr:TypeExpression):
		self.symbols = symbols
		self.type_params = type_parameters(param_names)
		self.type_expr = type_expr
		for symbol in self.symbols:
			symbol.ffi_type = self 

class ImportForeign:
	def __init__(self, source:Literal, linkage:Optional[Sequence[Reference]], groups:list[FFI_Group]):
		self.source = source
		if linkage is None: self.linkage = None
		else: self.linkage = [Lookup(ref) for ref in linkage]
		self.groups = groups

ImportDirective = Union[ImportModule, ImportForeign]

class Module:
	imports: list[ImportModule]
	foreign: list[ImportForeign]
	assumptions: list[Assumption]
	top_subs: list[Subroutine]
	actors: list[UserActor]
	user_operators: list[UserOperator]
	
	source_path: Path  # Module loader fills this.
	all_fns: list[UserFunction]  # WordDefiner pass fills this.
	all_procs: list[UserProcedure]  # WordDefiner pass fills this.
	ffi_operators: list[FFI_Operator]  # WordDefiner fills this too.
	
	performative : list[bool]  # Type checker fills this in so compiler emits correctly.

	def __init__(self, imports:list[ImportDirective], types:list[TypeDefinition], assumptions:list[Assumption], top_levels:list, main:list[ValueExpression]):
		self.imports = [i for i in imports if isinstance(i, ImportModule)]
		self.foreign = [i for i in imports if isinstance(i, ImportForeign)]
		self.types = types
		self.assumptions = assumptions
		self.top_subs = []
		self.actors = []
		self.user_operators = []
		self.all_fns = []
		self.all_procs = []
		self.ffi_operators = []
		for item in top_levels:
			if isinstance(item, UserOperator): self.user_operators.append(item)
			if isinstance(item, Subroutine): self.top_subs.append(item)
			elif isinstance(item, UserActor): self.actors.append(item)
			else: assert False, type(item)
		self.main = main
	
