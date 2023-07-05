"""
The set of parse-nodes in simple form.
The parser calls these constructors with subordinate semantic-values in a bottom-up tree transduction.
These constructors may add a touch of organization.
Class-level type annotations make peace with pycharm wherever later passes add fields.
"""
from pathlib import Path
from typing import Optional, Any, Sequence, NamedTuple, Union
from boozetools.parsing.interface import SemanticError
from .ontology import (
	Nom, Symbol, NS, Reference,
	Expr, Term,
)

class MismatchedBookendsError(SemanticError):
	# The one semantic error we catch early enough to interrupt the parse.
	# It's early warning that things have gotten out of whack.
	def __init__(self, head: slice, coda: slice):
		super().__init__(head, coda)

class TypeParameter(Symbol):
	static_depth = 0
	def __init__(self, nom:Nom):
		super().__init__(nom)
	def head(self) -> slice:
		return self.nom.head()
	def has_value_domain(self) -> bool:
		return False

class TypeDeclaration(Symbol):
	static_depth = 0
	param_space: NS   # Will address the type parameters. Word-definer fills this.
	type_params: tuple[TypeParameter, ...]
	
	def __init__(self, nom: Nom, type_params:tuple[TypeParameter, ...]):
		super().__init__(nom)
		self.type_params = type_params

def type_parameters(param_names:Sequence[Nom]):
	return tuple(TypeParameter(n) for n in param_names)

class SimpleType(Expr):
	def can_construct(self) -> bool: raise NotImplementedError(type(self))

class ValExpr(Expr):
	pass

class PlainReference(Reference):
	def head(self) -> slice:
		return self.nom.head()
	def __str__(self): return "<ref:%s>"%self.nom.text

class QualifiedReference(Reference):
	space: Nom
	def __init__(self, nom:Nom, space:Nom):
		super().__init__(nom)
		self.space = space
	def head(self) -> slice:
		return slice(self.nom.head().start, self.space.head().stop)

ARGUMENT_TYPE = Union[SimpleType, "ImplicitTypeVariable", "ExplicitTypeVariable"]

class ArrowSpec(SimpleType):
	lhs: Sequence[ARGUMENT_TYPE]
	_head: slice
	rhs: ARGUMENT_TYPE
	
	def __init__(self, lhs, _head, rhs):
		assert rhs is not None
		self.lhs = lhs
		self._head = _head
		self.rhs = rhs
	def head(self) -> slice: return self._head
	def can_construct(self) -> bool: return False

class TypeCall(SimpleType):
	def __init__(self, ref: Reference, arguments: Optional[Sequence[ARGUMENT_TYPE]] = ()):
		assert isinstance(ref, Reference)
		self.ref, self.arguments = ref, arguments or ()
	def head(self) -> slice: return self.ref.head()
	def can_construct(self) -> bool: return self.ref.dfn.has_value_domain()

class ImplicitTypeVariable:
	""" Stand-in as the relevant type-expression for when the syntax doesn't bother. """
	_slice: slice
	def __init__(self, a_slice):
		self._slice = a_slice
	def head(self) -> slice:
		return self._slice

class ExplicitTypeVariable(Reference):
	def __init__(self, _hook, nom:Nom):
		super().__init__(nom)
		self._hook = _hook
	def head(self) -> slice:
		return slice(self._hook.head().start, self.nom.head().stop)

class FormalParameter(Symbol):
	def has_value_domain(self): return True
	def __init__(self, nom:Nom, type_expr: Optional[ARGUMENT_TYPE]):
		super().__init__(nom)
		self.type_expr = type_expr
	def head(self) -> slice: return self.nom.head()
	def key(self): return self.nom.key()
	def __repr__(self): return "<:%s:%s>"%(self.nom.text, self.type_expr)

class RecordSpec:
	field_space: NS  # WordDefiner pass fills this in.
	def __init__(self, fields: list[FormalParameter]):
		self.fields = fields
	
	def field_names(self):
		return [f.nom.text for f in self.fields]

class VariantSpec(NamedTuple):
	subtypes: list["SubTypeSpec"]

class Opaque(TypeDeclaration):
	def __init__(self, nom: Nom):
		super().__init__(nom, ())
	def has_value_domain(self): return False

class TypeAlias(TypeDeclaration):
	body: SimpleType
	def __init__(self, nom: Nom, type_params:tuple[TypeParameter, ...], body:SimpleType):
		super().__init__(nom, type_params)
		self.body = body
	def has_value_domain(self) -> bool: return self.body.can_construct()

class Record(TypeDeclaration):
	def __init__(self, nom: Nom, type_params:tuple[TypeParameter, ...], spec:RecordSpec):
		super().__init__(nom, type_params)
		self.spec = spec
	def has_value_domain(self) -> bool: return True

class Variant(TypeDeclaration):
	sub_space: NS  # WordDefiner pass fills this in.
	def __init__(self, nom: Nom, type_params:tuple[TypeParameter, ...], spec:VariantSpec):
		super().__init__(nom, type_params)
		self.subtypes = spec.subtypes
		for s in spec.subtypes: s.variant = self
	def has_value_domain(self) -> bool: return False

_spec_to_decl = {
	RecordSpec : Record,
	VariantSpec : Variant,
	TypeCall : TypeAlias,
	ArrowSpec : TypeAlias,
}

def concrete_type(nom: Nom, body): return generic_type(nom, (), body)
def generic_type(nom: Nom, type_params:tuple[TypeParameter, ...], body):
	return _spec_to_decl[body.__class__](nom, type_params, body)

class SubTypeSpec(Symbol):
	body: Optional[Union[RecordSpec, TypeCall, ArrowSpec]]
	variant: Variant
	static_depth = 0
	# To clarify: The SubType here describes a *tagged* value, not the type of the value so tagged.
	# One can tag any kind of value; even a function. Therefore yes, you can always
	# treat a (tagged) subtype as a function. At least, once everything works right.
	def has_value_domain(self) -> bool: return True
	def __init__(self, nom:Nom, body=None):
		super().__init__(nom)
		self.body = body
	def head(self) -> slice: return self.nom.head()
	def key(self): return self.nom.key()
	def __repr__(self): return "<:%s:%s>"%(self.nom.text, self.body)

class Assumption(NamedTuple):
	names: list[Nom]
	type_expr: SimpleType

def _bookend(head: Nom, coda: Nom):
	if head.text != coda.text:
		raise MismatchedBookendsError(head.head(), coda.head())

class UserFunction(Term):
	source_path: Path
	namespace: NS
	params: Sequence[FormalParameter]
	where: Sequence["UserFunction"]
	def has_value_domain(self): return True
	def head(self) -> slice: return self.nom.head()
	def __repr__(self):
		p = ", ".join(map(str, self.params))
		return "{fn:%s(%s)}" % (self.nom.text, p)
	def __init__(
			self,
			nom: Nom,
			params: Sequence[FormalParameter],
			expr_type: Optional[ARGUMENT_TYPE],
			expr: ValExpr,
			where: Optional["WhereClause"]
	):
		super().__init__(nom)
		self.params = params or ()
		self.result_type_expr = expr_type
		self.expr = expr
		if where:
			_bookend(nom, where.end_name)
			self.where = where.sub_fns
		else:
			self.where = ()


class WhereClause(NamedTuple):
	sub_fns: Sequence[UserFunction]
	end_name: Nom

class Literal(ValExpr):
	def __init__(self, value: Any, a_slice: slice):
		self.value, self._slice = value, a_slice
	
	def __str__(self):
		return "<Literal %r>" % self.value
	
	def head(self) -> slice:
		return self._slice

def truth(a_slice:slice): return Literal(True, a_slice)
def falsehood(a_slice:slice): return Literal(False, a_slice)

class Lookup(ValExpr):
	# Reminder: This AST node exists in opposition to TypeCall so I can write
	# behavior for references in value context vs. references in type context.
	ref:Reference
	def __init__(self, ref: Reference): self.ref = ref
	def head(self) -> slice: return self.ref.head()
	def __str__(self): return str(self.ref)

class FieldReference(ValExpr):
	def __init__(self, lhs: ValExpr, field_name: Nom): self.lhs, self.field_name = lhs, field_name
	def __str__(self): return "(%s.%s)" % (self.lhs, self.field_name.text)
	def head(self) -> slice: return self.field_name.head()

class BoundMethod(ValExpr):
	def __init__(self, receiver: ValExpr, method_name: Nom):
		self.receiver, self.method_name = receiver, method_name
	def __str__(self): return "(%s.%s)" % (self.receiver, self.method_name.text)
	def head(self) -> slice: return self.method_name.head()

class BinExp(ValExpr):
	def __init__(self, glyph: str, lhs: ValExpr, o:slice, rhs: ValExpr):
		self.glyph, self.lhs, self.rhs = glyph, lhs, rhs
		self._head = o
	def head(self) -> slice: return self._head

def _be(glyph: str): return lambda a, o, b: BinExp(glyph, a, o, b)

PowerOf = _be("PowerOf")
Mul = _be("Mul")
FloatDiv = _be("FloatDiv")
FloatMod = _be("FloatMod")
IntDiv = _be("IntDiv")
IntMod = _be("IntMod")
Add = _be("Add")
Sub = _be("Sub")

EQ = _be("EQ")
NE = _be("NE")
LE = _be("LE")
LT = _be("LT")
GE = _be("GE")
GT = _be("GT")

class ShortCutExp(ValExpr):
	def __init__(self, glyph: str, lhs: ValExpr, o:slice, rhs: ValExpr):
		self.glyph, self.lhs, self._head, self.rhs = glyph, lhs, o, rhs
	
	def head(self) -> slice:
		return self._head
def LogicalAnd(a, o, b): return ShortCutExp("LogicalAnd", a, o, b)
def LogicalOr(a, o, b): return ShortCutExp("LogicalOr", a, o, b)

class UnaryExp(ValExpr):
	def __init__(self, glyph: str, o:slice, arg: ValExpr):
		self.glyph, self.arg = glyph, arg
		self._head = o

	def head(self) -> slice: return self._head

def Negative(o, arg): return UnaryExp("Negative", o, arg)

def LogicalNot(o, arg): return UnaryExp("LogicalNot", o, arg)

class Cond(ValExpr):
	_kw: slice
	def __init__(self, then_part: ValExpr, _kw, if_part: ValExpr, else_part: ValExpr):
		self._kw = _kw
		self.then_part, self.if_part, self.else_part = then_part, if_part, else_part
	def head(self) -> slice:
		return self._kw

def CaseWhen(when_parts: list, else_part: ValExpr):
	for _kw, test, then in reversed(when_parts):
		else_part = Cond(then, _kw, test, else_part)
	return else_part

class Call(ValExpr):
	def __init__(self, fn_exp: ValExpr, args: list[ValExpr]):
		self.fn_exp, self.args = fn_exp, args
	
	def __str__(self):
		return "%s(%s)" % (self.fn_exp, ', '.join(map(str, self.args)))
	
	def head(self) -> slice: return self.fn_exp.head()

def call_upon_list(fn_exp: ValExpr, list_arg: ValExpr):
	return Call(fn_exp, [list_arg])

class ExplicitList(ValExpr):
	def __init__(self, elts: list[ValExpr]):
		for e in elts:
			assert isinstance(e, ValExpr), e
		self.elts = elts
	def head(self) -> slice:
		raise AssertionError

class Alternative(Symbol):
	sub_expr: ValExpr
	where: Sequence[UserFunction]
	
	namespace: NS  # WordDefiner fills

	def __init__(self, pattern:Nom, _head, sub_expr:ValExpr, where:WhereClause):
		super().__init__(pattern)
		self._head = _head
		self.sub_expr = sub_expr
		if where:
			_bookend(pattern, where.end_name)
			self.where = where.sub_fns
		else:
			self.where = ()
	def head(self) -> slice:
		return self._head
	
class Subject(Symbol):
	""" Within a match-case, a name must reach a different symbol with the particular subtype """
	expr: ValExpr
	def __init__(self, expr: ValExpr, nom: Nom):
		super().__init__(nom)
		self.expr = expr
	def has_value_domain(self) -> bool: return True

def simple_subject(nom:Nom):
	return Subject(Lookup(PlainReference(nom)), nom)

class MatchExpr(ValExpr):
	subject:Subject  # Symbol in scope within alternative expressions; contains the value of interest
	hint: Optional[Reference]
	alternatives: list[Alternative]
	otherwise: Optional[ValExpr]
	
	namespace: NS  # WordDefiner fills
	
	variant:Variant  # Filled in match-check pass
	dispatch: dict[Optional[str]:ValExpr]
	
	def __init__(self, subject, hint, alternatives, otherwise):
		self.subject = subject
		self.hint = hint
		self.alternatives, self.otherwise = alternatives, otherwise
	
	def head(self) -> slice:
		return self.subject.head()

class DoBlock(ValExpr):
	def __init__(self, steps:list[ValExpr]):
		self.steps = steps

class ImportSymbol(NamedTuple):
	yonder : Nom
	hither : Optional[Nom]

class ImportModule(Symbol):
	module_key: Path  # Module loader fills this.
	def __init__(self, package:Optional[Nom], relative_path:Literal, nom:Optional[Nom], vocab:Optional[Sequence[ImportSymbol]]):
		super().__init__(nom)
		self.package = package
		self.relative_path = relative_path
		self.vocab = vocab or ()

class FFI_Alias(Term):
	""" Built-in and foreign (Python) function symbols. """
	val:Any  # Fill in during WordDefiner pass
	
	def __init__(self, nom:Nom, alias:Optional[Literal]):
		super().__init__(nom)
		self.nom = nom
		self.alias = alias

def FFI_Symbol(nom:Nom):
	return FFI_Alias(nom, None)

class FFI_Group:
	param_space: NS   # Will address the type parameters. Word-definer fills this.
	def __init__(self, symbols:list[FFI_Alias], type_params:Optional[Sequence[TypeParameter]], type_expr:SimpleType):
		self.symbols = symbols
		self.type_params = type_params or ()
		self.type_expr = type_expr

class ImportForeign:
	def __init__(self, source:Literal, linkage:Optional[Sequence[Reference]], groups:list[FFI_Group]):
		self.source = source
		self.linkage = linkage
		self.groups = groups

ImportDirective = Union[ImportModule, ImportForeign]

class Module:
	imports: list[ImportModule]
	foreign: list[ImportForeign]
	source_path: Path  # Module loader fills this.

	def __init__(self, exports:list, imports:list[ImportDirective], types:list[TypeDeclaration], assumption:list[Assumption], functions:list[UserFunction], main:list):
		self.exports = exports
		self.imports = [i for i in imports if isinstance(i, ImportModule)]
		self.foreign = [i for i in imports if isinstance(i, ImportForeign)]
		self.types = types
		self.outer_functions = functions
		self.main = main
	
	def head(self): return slice(0,0)
