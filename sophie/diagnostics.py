import sys
from collections import defaultdict
from typing import Sequence, Optional, NamedTuple, Any, Union
from pathlib import Path
from boozetools.support.failureprone import SourceText, Issue, Evidence, Severity, illustration
from .ontology import Expr
from .syntax import FieldReference, UserDefinedFunction
from .calculus import TYPE_ENV
from .stacking import ActivationRecord

class Report:
	""" Might this end up participating in a result-monad? """
	_issues : list[Issue]
	_path : Optional[Path]
	
	def __init__(self, verbose:bool):
		self._verbose = verbose
		self._issues : list[Union[Issue, "Pic"]] = []
		self._path = None
	
	def ok(self): return not self._issues
	def sick(self): return bool(self._issues)
	
	def reset(self):
		self._issues.clear()
	
	def info(self, *args):
		if self._verbose:
			print(*args, file=sys.stderr)
	
	def set_path(self, path:Optional[Path]):
		""" Let the report know which file is under consideration, for in case of error. """
		# Yes, it's a temporal coupling. But it's a small worry, at least for now.
		self._path = path
		
	def error(self, phase: str, guilty: Sequence[slice], msg: str):
		""" Actually make an entry of an issue """
		assert all(isinstance(g, slice) for g in guilty)
		if guilty:
			assert self._path is not None
			for s in guilty:
				assert isinstance(s, slice), s
		evidence = {self._path: [Evidence(s, "") for s in guilty]}
		self._issues.append(Issue(phase, Severity.ERROR, msg, evidence))

	def on_error(self, phase:str):
		""" Return a convenience-function for a particular phase/pass to complain. """
		# Can't call it a "pass" when "pass" is a reserved word...
		def err(items:list[Expr], msg:str):
			self.error(phase, [i.head() for i in items], msg)
		return err
	
	def complain_to_console(self):
		""" Emit all the issues to the console. """
		for i in self._issues:
			print("  -"*20, file=sys.stderr)
			print(i.as_text(_fetch), file=sys.stderr)
			
	def assert_no_issues(self):
		""" Does what it says on the tin """
		if self._issues:
			self.complain_to_console()
			assert False
	
	# Methods the front-end is likely to call:
	def file_error(self, path:Path, msg:str):
		issue = Issue("trying to read a file", Severity.ERROR, msg, {})
		self._issues.append(issue)

	# Methods specific to report type-checking issues.
	# Now this begins to look like something proper.
	
	def type_mismatch(self, env:TYPE_ENV, *args:Expr):
		intro = "Types for these expressions need to match, but they do not."
		path = env.path()
		problem = [Annotation(path, e.head(), "") for e in args]
		self._issues.append(Pic(intro, problem))
		self._issues.append(Pic("Here's how that happens:", trace_stack(env)))
	
	def wrong_arity(self, path:Path, arity:int, args:Sequence[Expr]):
		evidence = {path: [Evidence(a.head(), "") for a in args]}
		pattern = "The called function wants %d arguments, but got %d instead."
		issue = Issue("Checking Types", Severity.ERROR, pattern % (arity, len(args)), evidence)
		self._issues.append(issue)

	def bad_type(self, env:TYPE_ENV, expr: Expr, need, got):
		intro = "Type-checking found a problem. Here's how it happens:"
		complaint = "This %s needs to be %s."%(got, need)
		problem = [Annotation(env.path(), expr.head(), complaint)]
		self._issues.append(Pic(intro, problem+trace_stack(env)))
	
	def type_has_no_fields(self, path: Path, fr:FieldReference, lhs_type):
		evidence = {path: [Evidence(fr.lhs.head(),"This has type %s."%lhs_type)]}
		issue = Issue("Checking Types", Severity.ERROR, "This type has no fields; in particular not %s."%fr.field_name.text, evidence)
		self._issues.append(issue)
		
	def record_lacks_field(self, path: Path, fr:FieldReference, lhs_type):
		evidence = {path: [Evidence(fr.lhs.head(),"This has type %s."%lhs_type)]}
		issue = Issue("Checking Types", Severity.ERROR, "This type has no field called %s."%fr.field_name.text, evidence)
		self._issues.append(issue)
	
	def ill_founded_function(self, path: Path, udf:UserDefinedFunction):
		evidence = {path: [Evidence(udf.head(), "here")]}
		issue = Issue("Checking Types", Severity.ERROR, "This function's definition turned up circular, as in a=a.", evidence)
		self._issues.append(issue)


class Annotation(NamedTuple):
	path: Path
	slice: slice
	caption: str
	
def illustrate(source, the_slice, caption):
	row, col = source.find_row_col(the_slice.start)
	single_line = source.line_of_text(row)
	width = the_slice.stop - the_slice.start
	return illustration(single_line, col, width, prefix='% 6d :' % row, caption=caption)

def trace_stack(env:TYPE_ENV) -> list[Annotation]:
	trace = []
	while isinstance(env, ActivationRecord):
		bindings = ', '.join("%s:%s" % (p.nom.text, t) for p, t in env.bindings.items())
		trace.append(Annotation(env.path(), env.udf.head(), "Called with " + bindings))
		env = env.dynamic_link
		if hasattr(env, "pc"):
			trace.append(Annotation(env.path(), env.pc.head(), "Called from here"))
	return trace

class Pic:
	def __init__(self, intro:str, trace:list[Annotation]):
		source, path = ..., ...
		self.lines = [intro, ""]
		for ann in trace:
			if ann.path != path:
				path = ann.path
				self.lines.append(str(path))
				source = _fetch(path)
			self.lines.append(illustrate(source, ann.slice, ann.caption))
	def as_text(self, fetch):
		return '\n'.join(self.lines)
		
def _fetch(path) -> SourceText:
	if path is None:
		return SourceText("")
	with open(path) as fh:
		return SourceText(fh.read(), filename=str(path))


