"""
The set of parse-nodes in simple form.
The parser calls these constructors with subordinate semantic-values in a bottom-up tree transduction.
These constructors may add a touch of organization.
Class-level type annotations make peace with pycharm wherever later passes add fields.
"""
from typing import Optional, Any, Sequence, NamedTuple, Union
from boozetools.parsing.interface import SemanticError
from boozetools.support.symtab import NameSpace
from .ontology import Nom, Symbol, Native, NS, Reference, TypeExpr, ValExpr
from .hot.concrete import Product, TypeVariable

class PlainReference(Reference):
	nom: Nom
	def __init__(self, nom:Nom):
		self.nom = nom
	def head(self) -> slice:
		return self.nom.head()

class QualifiedReference(Reference):
	nom: Nom
	space: Nom
	def __init__(self, nom:Nom, space:Nom):
		self.nom = nom
		self.space = space
	def head(self) -> slice:
		return slice(self.nom.head().start, self.space.head().stop)

SIMPLE_TYPE = Union["TypeCall", "ArrowSpec", "ImplicitType", "GenericType"]

class ArrowSpec(TypeExpr):
	lhs: Sequence[SIMPLE_TYPE]
	_head: slice
	rhs: SIMPLE_TYPE
	
	def __init__(self, lhs, _head, rhs):
		assert rhs is not None
		self.lhs = lhs
		self._head = _head
		self.rhs = rhs
	def head(self) -> slice:
		return self._head
	
class TypeCall(TypeExpr):
	def __init__(self, ref: Reference, arguments: Sequence[SIMPLE_TYPE] = ()):
		assert isinstance(ref, Reference)
		self.ref, self.arguments = ref, arguments or ()
	
	def head(self) -> slice: return self.ref.head()

class ImplicitType(TypeExpr):
	""" Stand-in as the relevant type-expression for when the syntax doesn't bother. """
	_head: slice
	def __init__(self, _head):
		self._head = _head
	def head(self) -> slice:
		return self._head

class GenericType(Reference):
	nom: Nom
	def __init__(self, _hook, nom:Nom):
		self._hook = _hook
		self.nom = nom
	def head(self) -> slice:
		return slice(self._hook.head().start, self.nom.head().stop)

def genericity(_hook, nom:Optional[Nom]):
	if nom is None: return ImplicitType(_hook)
	else: return GenericType(_hook, nom)

class FormalParameter(Symbol):
	def has_value_domain(self): return True
	def __init__(self, nom:Nom, type_expr: Optional[SIMPLE_TYPE]):
		super().__init__(nom)
		self.type_expr = type_expr
	def head(self) -> slice: return self.nom.head()
	def key(self): return self.nom.key()
	def __repr__(self): return "<:%s:%s>"%(self.nom.text, self.type_expr)

class RecordSpec(TypeExpr):
	namespace: NS  # WordDefiner pass fills this in.
	product_type: Product  # TypeBuilder pass sets this.
	def __init__(self, fields: list[FormalParameter]):
		self.fields = fields
	
	def field_names(self):
		return [f.nom.text for f in self.fields]

class SubTypeSpec(Symbol):
	body: Union[RecordSpec, TypeCall, ArrowSpec]
	variant:"TypeDecl"
	static_depth = 0
	def has_value_domain(self): return True
	def __init__(self, nom:Nom, body=None):
		super().__init__(nom)
		self.body = body
	def head(self) -> slice: return self.nom.head()
	def key(self): return self.nom.key()
	def __repr__(self): return "<:%s:%s>"%(self.nom.text, self.body)

class VariantSpec(TypeExpr):
	_kw: slice
	namespace: NS
	def __init__(self, _kw: slice, subtypes: list[SubTypeSpec]):
		self._kw = _kw
		self.subtypes = subtypes

class TypeParameter(Symbol):
	quantifiers = ()
	def __init__(self, nom:Nom):
		super().__init__(nom)
		self.typ = TypeVariable()
	def head(self) -> slice:
		return self.nom.head()
	def has_value_domain(self) -> bool:
		return False

class TypeDecl(Symbol):
	namespace: NS
	nom: Nom
	parameters: Sequence[TypeParameter]
	body: Union[TypeCall, VariantSpec, RecordSpec]
	quantifiers: list[TypeVariable]  # phase: WordDefiner
	static_depth = 0
	def __str__(self): return self.nom.text
	def __repr__(self):
		p = "[%s] "%",".join(map(str, self.parameters)) if self.parameters else ""
		return "{td:%s%s = %s}"%(self.nom.text, p, self.body)
	
	def __init__(self, nom, parameters: Sequence[Nom], body) -> None:
		super().__init__(nom)
		self.parameters = [TypeParameter(p) for p in parameters or ()]
		self.body = body
	def head(self) -> slice:
		return self.nom.head()
	def has_value_domain(self): return isinstance(self.body, RecordSpec)

class MismatchedBookendsError(SemanticError):
	# The one semantic error we catch early enough to interrupt the parse.
	# It's early warning that things have gotten out of whack.
	def __init__(self, head: slice, coda: slice):
		super().__init__(head, coda)

def _bookend(head: Nom, coda: Nom):
	if head.text != coda.text:
		raise MismatchedBookendsError(head.head(), coda.head())

class Function(Symbol):
	namespace: NS
	sub_fns: dict[str:"Function"]  # for simple evaluator
	where: Sequence["Function"]
	
	def has_value_domain(self): return True
	def __repr__(self):
		p = ", ".join(map(str, self.params))
		return "{fn:%s(%s)}"%(self.nom.text, p)
	def __init__(
			self,
			nom: Nom,
			params: Sequence[FormalParameter],
			expr_type: Optional[SIMPLE_TYPE],
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
	
	def head(self) -> slice: return self.nom.head()

class WhereClause(NamedTuple):
	sub_fns: Sequence[Function]
	end_name: Nom

class Literal(ValExpr):
	def __init__(self, value: Any, a_slice: slice):
		self.value, self._slice = value, a_slice
	
	def __str__(self):
		return "<Literal %r>" % self.value
	
	def head(self) -> slice:
		return self._slice

class Lookup(ValExpr):
	ref:Reference
	source_depth:int
	def __init__(self, ref: Reference): self.ref = ref
	def head(self) -> slice: return self.ref.head()

class FieldReference(ValExpr):
	def __init__(self, lhs: ValExpr, field_name: Nom): self.lhs, self.field_name = lhs, field_name
	def __str__(self): return "(%s.%s)" % (self.lhs, self.field_name.text)
	def head(self) -> slice: return self.field_name.head()

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

class SubjectWithExpr(NamedTuple):
	expr: ValExpr
	nom: Nom

class Alternative(ValExpr):
	pattern: Reference
	sub_expr: ValExpr
	where: Sequence[Function]
	
	namespace: NS  # WordDefiner fills
	
	def __init__(self, pattern:Reference, _head, sub_expr:ValExpr, where:WhereClause):
		self.pattern = pattern
		self._head = _head
		self.sub_expr = sub_expr
		if where:
			_bookend(pattern.nom, where.end_name)
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
	
	variant:TypeDecl  # check_match_expressions infers this from the patterns
	dispatch: dict[Optional[str]:ValExpr]
	
	def __init__(self, subject:Subject, hint:Optional[Reference], alternatives: list[Alternative], otherwise: Optional[ValExpr]):
		self.subject = subject
		self.hint = hint
		self.alternatives, self.otherwise = alternatives, otherwise
	
	def head(self) -> slice:
		return self.subject.head()

class ImportDirective: pass

class ImportModule(ImportDirective):
	def __init__(self, relative_path:Literal, nom:Nom):
		self.relative_path = relative_path
		self.nom = nom

class FFI_Alias(Native):
	def __init__(self, nom:Nom, alias:Optional[Literal]):
		super().__init__(nom)
		self.nom = nom
		self.alias = alias

def FFI_Symbol(nom:Nom):
	return FFI_Alias(nom, None)

class FFI_Group:
	def __init__(self, symbols:list[FFI_Alias], type_expr:Union[TypeCall, ArrowSpec]):
		self.symbols = symbols
		self.type_expr = type_expr

class ImportForeign(ImportDirective):
	def __init__(self, source:Literal, groups:list[FFI_Group]):
		self.source = source
		self.groups = groups

class Module:
	imports: list[ImportModule]
	foreign: list[ImportForeign]
	module_imports: NameSpace[NS]  # Modules imported with an "as" clause.
	wildcard_imports: NS  # Names imported with a wildcard. Sits underneath globals.
	globals: NS  # WordDefiner pass creates this.
	constructors: dict[str:]
	all_match_expressions: list[MatchExpr]  # WordResolver pass creates this.
	all_functions: list[Function]
	all_record_specs: list[RecordSpec]  # Handy to save trouble around variants.
	all_variant_specs: list[VariantSpec]
	all_subtype_specs: list[SubTypeSpec]
	def __init__(self, exports:list, imports:list[ImportDirective], types:list, functions:list, main:list):
		self.exports = exports
		self.imports = [i for i in imports if isinstance(i, ImportModule)]
		self.foreign = [i for i in imports if isinstance(i, ImportForeign)]
		self.types = types
		self.outer_functions = functions
		self.main = main
		self.module_imports = NameSpace(place=self)
