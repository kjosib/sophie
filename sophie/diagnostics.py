from typing import Sequence, Optional
from pathlib import Path
from boozetools.support.failureprone import SourceText, Issue, Evidence, Severity
from .ontology import Expr
from .syntax import FieldReference

class Report:
	""" Might this end up participating in a result-monad? """
	issues : list[Issue]
	_path : Optional[Path]
	
	def __init__(self):
		self.issues = []
		self._path = None
	
	def reset(self):
		self.issues.clear()
	
	def set_path(self, path:Optional[Path]):
		""" Let the report know which file is under consideration, for in case of error. """
		# Yes, it's a temporal coupling. But it's a small worry, at least for now.
		self._path = path
		
	def error(self, phase: str, guilty: Sequence[slice], msg: str):
		""" Actually make an entry of an issue """
		assert all(isinstance(g, slice) for g in guilty)
		if guilty: assert self._path is not None
		evidence = {self._path: [Evidence(s, "") for s in guilty]}
		self.issues.append(Issue(phase, Severity.ERROR, msg, evidence))

	def on_error(self, phase:str):
		""" Return a convenience-function for a particular phase/pass to complain. """
		# Can't call it a "pass" when "pass" is a reserved word...
		def err(items:list[Expr], msg:str):
			self.error(phase, [i.head() for i in items], msg)
		return err
	
	def complain_to_console(self):
		""" Emit all the issues to the console. """
		# Assuming an early-exit policy, so the issues aren't tied to files. Yet.
		# Type conflicts could reasonably have messages that incorporate facts from different modules,
		# but cross that bridge upon arrival.
		for i in self.issues:
			i.emit(_fetch)
			
	def assert_no_issues(self):
		""" Does what it says on the tin """
		if self.issues:
			self.complain_to_console()
			assert False
	
	# Methods specific to report type-checking issues.
	# Now this begins to look like something proper.
	
	def type_mismatch(self, path:Path, *args:Expr):
		evidence = {path: [Evidence(e.head(),"") for e in args]}
		issue = Issue("Checking Types", Severity.ERROR, "These don't have compatible types.", evidence)
		self.issues.append(issue)
	
	def wrong_arity(self, path:Path, arity:int, args:Sequence[Expr]):
		evidence = {path: [Evidence(a.head(), "") for a in args]}
		pattern = "The called function wants %d arguments, but got %d instead."
		issue = Issue("Checking Types", Severity.ERROR, pattern % (arity, len(args)), evidence)
		self.issues.append(issue)

	def bad_type(self, path: Path, expr: Expr, need, got):
		evidence = {path: [Evidence(expr.head(),"This expression has type %s."%got)]}
		issue = Issue("Checking Types", Severity.ERROR, "Needed %s; got something else." % need, evidence)
		self.issues.append(issue)
	
	def type_has_no_fields(self, path: Path, fr:FieldReference, lhs_type):
		evidence = {path: [Evidence(fr.lhs.head(),"This expression has type %s."%lhs_type)]}
		issue = Issue("Checking Types", Severity.ERROR, "This type has no fields; in particular not %s."%fr.field_name.text, evidence)
		self.issues.append(issue)
		
	def record_lacks_field(self, path: Path, fr:FieldReference, lhs_type):
		evidence = {path: [Evidence(fr.lhs.head(),"This expression has type %s."%lhs_type)]}
		issue = Issue("Checking Types", Severity.ERROR, "This type has no field called %s."%fr.field_name.text, evidence)
		self.issues.append(issue)

			
def _fetch(path):
	if path is None:
		return SourceText("")
	with open(path) as fh:
		return SourceText(fh.read(), filename=str(path))


