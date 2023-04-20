from typing import Sequence, Optional
from boozetools.support.failureprone import SourceText, Issue, Evidence, Severity
from .ontology import Expr

class Report:
	""" Might this end up participating in a result-monad? """
	issues : list[Issue]
	_path : Optional[str]
	
	def __init__(self):
		self.issues = []
		self._path = None
	
	def set_path(self, path):
		""" Let the report know which file is under consideration, for in case of error. """
		# Yes, it's a temporal coupling. But it's a small worry, at least for now.
		self._path = path
		
	def error(self, phase: str, guilty: Sequence[slice], msg: str):
		""" Actually make an entry of an issue """
		assert all(isinstance(g, slice) for g in guilty)
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

			
def _fetch(path):
	if path:
		with open(path) as fh:
			return SourceText(fh.read(), filename=path)
	else:
		import sys
		return SourceText(sys.modules["sophie.preamble"].__doc__)


