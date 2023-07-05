import sys
from typing import Sequence, Optional, NamedTuple, Union
from traceback import TracebackException
from pathlib import Path
from boozetools.support.failureprone import SourceText, Issue, Evidence, Severity, illustration
from . import syntax
from .ontology import Expr, Nom, Symbol, Reference
from .calculus import TYPE_ENV, SophieType

class Report:
	""" Might this end up participating in a result-monad? """
	_issues : list[Union[Issue, "Pic", "Redefined", "Undefined"]]
	_path : Optional[Path]
	
	def __init__(self, verbose:int):
		self._verbose = verbose or 0   # Because None is incomparable.
		self._issues = []
		self._redefined = {}
		self._undefined = None
		self._path = None
	
	def ok(self): return not self._issues
	def sick(self): return bool(self._issues)
	
	def reset(self):
		self._issues.clear()
	
	def info(self, *args):
		if self._verbose:
			print(*args, file=sys.stderr)
	
	def trace(self, *args):
		if self._verbose > 1:
			print(*args, file=sys.stderr)
	
	def set_path(self, path:Optional[Path]):
		""" Let the report know which file is under consideration, for in case of error. """
		# Yes, it's a temporal coupling. But it's a small worry, at least for now.
		self._path = path
		
	def error(self, phase: str, guilty: Sequence[slice], msg: str):
		""" Actually make an entry of an issue """
		for g in guilty:
			assert isinstance(g, slice), type(g)
		if guilty:
			assert self._path is not None
			for s in guilty:
				assert isinstance(s, slice), s
		evidence = {self._path: [Evidence(s, "") for s in guilty]}
		self._issues.append(Issue(phase, Severity.ERROR, msg, evidence))

	def complain_to_console(self):
		""" Emit all the issues to the console. """
		for i in self._issues:
			print("  -"*20, file=sys.stderr)
			print(i.as_text(_fetch), file=sys.stderr)
			
	def assert_no_issues(self):
		""" Does what it says on the tin """
		if self._issues:
			self.complain_to_console()
			assert False, "This is supposed to be impossible."
	
	# Methods the front-end is likely to call:
	def generic_parse_error(self, path: Path, lookahead, span: slice, hint: str):
		intro = "Sophie got confused by %s." % lookahead
		problem = [Annotation(path, span, "Sophie got confused here")]
		self._issues.append(Pic(intro, problem))
		self._issues.append(Pic(hint, []))

	# Methods the package / import mechanism invokes:

	def _file_error(self, path:Path, cause:Expr, prefix:str):
		intro = prefix+" "+str(path)
		if cause:
			problem = [Annotation(self._path, cause.head())]
		else:
			problem = []
		self._issues.append(Pic(intro, problem))
		
	def no_such_file(self, path:Path, cause:Expr):
		self._file_error(path, cause, "I see no file called")
	
	def broken_file(self, path:Path, cause:Expr):
		self._file_error(path, cause, "Something went pear-shaped while trying to read")
	
	def cyclic_import(self, cause, cycle):
		intro = "Here begins a cycle of imports. Sophie considers that an error."
		problem = [Annotation(self._path, cause.head())]
		footer = [" - The full cycle is:"]
		footer.extend('     '+str(path) for path in cycle)
		self._issues.append(Pic(intro, problem, footer))

	def no_such_package(self, cause:Nom):
		intro = "There's no such package:"
		problem = [Annotation(self._path, cause.head())]
		footer = ["(At the moment, there is only sys.)"]
		self._issues.append(Pic(intro, problem, footer))

	# Methods the resolver passes might call:
	def broken_foreign_module(self, source, tbx:TracebackException):
		msg = "Attempting to import this module threw an exception."
		text = ''.join(tbx.format())
		self._issues.append((Pic(text, [])))
		self.error("Defining words", [source.head()], msg)
	
	def missing_foreign_module(self, source):
		intro = "Missing Foreign Module"
		caption = "This module could not be found."
		self._issues.append(Pic(intro, [Annotation(self._path, source.head(), caption)]))

	def missing_foreign_linkage(self, source):
		intro = "Missing Foreign Linkage Function"
		caption = "This module has no 'sophie_init'."
		self._issues.append(Pic(intro, [Annotation(self._path, source.head(), caption)]))
		
	def wrong_linkage_arity(self, d:syntax.ImportForeign, arity:int):
		intro = "Disagreeable Foreign Linkage Function"
		caption = "This module's 'sophie_init' expects %d argument(s) but got %d instead."
		ann = Annotation(self._path, d.source.head(), caption%(arity, len(d.linkage)))
		self._issues.append(Pic(intro, [ann]))

	def redefined_name(self, earlier:Symbol, later:Nom):
		if earlier not in self._redefined:
			issue = Redefined(_fetch(self._path), earlier.nom.head())
			self._issues.append(issue)
			self._redefined[earlier] = issue
		self._redefined[earlier].note(later)

	def undefined_name(self, guilty:slice):
		if self._undefined is None:
			self._undefined = Undefined(_fetch(self._path))
			self._issues.append(self._undefined)
		self._undefined.note(guilty)

	def opaque_generic(self, guilty:Sequence[syntax.TypeParameter]):
		admonition = "Opaque types are not to be made generic."
		where = [g.head() for g in guilty]
		self.error("Defining Types", where, admonition)
	
	# Methods the Alias-checker calls
	def these_are_not_types(self, non_types:Sequence[syntax.TypeCall]):
		intro = "Words that get used like types, but refer to something else."
		problem = [Annotation(self._path, tc.head()) for tc in non_types]
		self._issues.append(Pic(intro, problem))
	
	def circular_type(self, scc:Sequence):
		intro = "What we have here is a circular type-definition."
		problem = [Annotation(self._path, node.head()) for node in scc]
		self._issues.append(Pic(intro, problem))
	
	def wrong_type_arity(self, tc:syntax.TypeCall, given:int, needed:int):
		pattern = "%d type-arguments were given; %d are needed."
		intro = pattern % (given, needed)
		problem = [Annotation(self._path, tc.head())]
		self._issues.append(Pic(intro, problem))
	
	# Methods the match-checker calls
	def not_a_variant(self, ref:Reference):
		intro = "That's not a variant-type name"
		ann = Annotation(self._path, ref.head())
		self._issues.append(Pic(intro, [ann]))
	
	def not_a_case_of(self, nom:Nom, variant:syntax.Variant):
		# pattern = "This case is not a member of the variant-type <%s>."
		# intro = pattern%variant.nom.text
		self.undefined_name(nom.head())
		pass
	
	def not_a_case(self, nom:Nom):
		intro = "This needs to refer to one case of a variant-type."
		ann = Annotation(self._path, nom.head())
		self._issues.append(Pic(intro, [ann]))
	
	def not_exhaustive(self, mx:syntax.MatchExpr):
		pattern = "This case-block does not cover all the cases of <%s> and lacks an else-clause."
		intro = pattern % mx.variant.nom.text
		ann = Annotation(self._path, mx.head())
		self._issues.append(Pic(intro, [ann]))
		
	def redundant_else(self, mx:syntax.MatchExpr):
		intro = "This case-block has an extra else-clause."
		problem = [
			Annotation(self._path, mx.head(), "covers every case"),
			Annotation(self._path, mx.otherwise.head(), "cannot happen")
		]
		footer = ["That's probably an oversight."]
		self._issues.append(Pic(intro, problem, footer))

	# Methods specific to report type-checking issues.
	
	def type_mismatch(self, env:TYPE_ENV, *args:syntax.ValExpr):
		intro = "Types for these expressions need to match, but they do not."
		path = env.path()
		problem = [Annotation(path, e.head()) for e in args]
		self._issues.append(Pic(intro, problem))
		self._issues.append(Pic("Here's how that happens:", trace_stack(env)))
	
	def wrong_arity(self, env:TYPE_ENV, site:syntax.ValExpr, arity:int, args:Sequence[syntax.ValExpr]):
		plural = '' if arity == 1 else 's'
		pattern = "This function takes %d argument%s, but got %d instead."
		intro = pattern % (arity, plural, len(args))
		problem = [Annotation(env.path(), site.head(), "Here")]
		self._issues.append(Pic(intro, problem+trace_stack(env)))

	def bad_type(self, env:TYPE_ENV, expr:syntax.ValExpr, need, got):
		intro = "Type-checking found a problem. Here's how it happens:"
		complaint = "This %s needs to be %s."%(got, need)
		problem = [Annotation(env.path(), expr.head(), complaint)]
		self._issues.append(Pic(intro, problem+trace_stack(env)))
	
	def type_has_no_fields(self, env:TYPE_ENV, fr:syntax.FieldReference, lhs_type):
		field = fr.field_name.text
		intro = "Type-checking found an unsuitable source for field '%s' access."%field
		complaint = "%s has no fields; in particular not '%s'."%(lhs_type, field)
		problem = [Annotation(env.path(), fr.lhs.head(), complaint)]
		self._issues.append(Pic(intro, problem+trace_stack(env)))
		
	def record_lacks_field(self, env:TYPE_ENV, fr:syntax.FieldReference, lhs_type:SophieType):
		field = fr.field_name.text
		intro = "Type-checking found an unsuitable source for field '%s' access."%field
		complaint = "Type '%s' has fields, but not one called '%s'."%(lhs_type, field)
		problem = [Annotation(env.path(), fr.lhs.head(), complaint)]
		self._issues.append(Pic(intro, problem+trace_stack(env)))
	
	def ill_founded_function(self, env:TYPE_ENV, udf:syntax.UserFunction):
		intro = "This function's definition turned up circular, as in a=a."
		problem = [Annotation(udf.source_path, udf.head(), "This one.")]
		self._issues.append(Pic(intro, problem+trace_stack(env)))


class Annotation(NamedTuple):
	path: Path
	slice: slice
	caption: str = ""
	
def illustrate(source, the_slice, caption):
	row, col = source.find_row_col(the_slice.start)
	single_line = source.line_of_text(row)
	width = the_slice.stop - the_slice.start
	return illustration(single_line, col, width, prefix='% 6d :' % row, caption=caption)

class Tracer:
	def __init__(self):
		self.trace = []
	def called_with(self, path, span:slice, args:dict):
		bind_text = ', '.join("%s:%s" % (p.nom.text, t) for p, t in args.items())
		self.trace.append(Annotation(path, span, "Called with " + bind_text))
	def called_from(self, path, span):
		self.trace.append(Annotation(path, span, "Called from here"))
	def hit_bottom(self):
		pass
	def trace_frame(self, breadcrumb, bindings, pc):
		path = breadcrumb.source_path
		if pc is not None: self.called_from(path, pc.head())
		args = {
			k:v for k,v in bindings.items()
			if isinstance(k, syntax.FormalParameter)
		}
		if args: self.called_with(path, breadcrumb.head(), args)

def trace_stack(env:TYPE_ENV) -> list[Annotation]:
	tracer = Tracer()
	env.trace(tracer)
	return tracer.trace

class Pic:
	def __init__(self, intro:str, trace:list[Annotation], footer=()):
		source, path = ..., ...
		self.lines = [intro, ""]
		for ann in trace:
			if ann.path != path:
				path = ann.path
				self.lines.append(str(path))
				source = _fetch(path)
			self.lines.append(illustrate(source, ann.slice, ann.caption))
		self.lines.extend(footer)
	def as_text(self, fetch):
		return '\n'.join(self.lines)
		
def _fetch(path) -> SourceText:
	if path is None:
		return SourceText("")
	with open(path) as fh:
		return SourceText(fh.read(), filename=str(path))

class Redefined:
	def __init__(self, source:SourceText, earliest:slice):
		self._source = source
		self._lines = [
			"This symbol is defined more than once in the same scope.",
			illustrate(source, earliest, "Earliest definition"),
		]
	def note(self, later:Nom):
		self._lines.append(illustrate(self._source, later.head(), ""))
	def as_text(self, fetch):
		return '\n'.join(self._lines)

class Undefined:
	def __init__(self, source:SourceText):
		self._source = source
		self._lines = ["I don't see what this refers to."]
	def note(self, later:slice):
		self._lines.append(illustrate(self._source, later, ""))
	def as_text(self, fetch):
		return '\n'.join(self._lines)

