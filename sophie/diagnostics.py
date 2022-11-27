from typing import Sequence
from boozetools.support.failureprone import Issue, Evidence, Severity
from .ontology import SyntaxNode

class Report:
	""" Might this end up participating in a result-monad? """
	issues : list[Issue]
	
	def __init__(self):
		self.issues = []
		
	def error(self, phase: str, guilty: Sequence[slice], msg: str):
		assert all(isinstance(g, slice) for g in guilty)
		evidence = {"": [Evidence(s, "") for s in guilty]}
		self.issues.append(Issue(phase, Severity.ERROR, msg, evidence))

	def on_error(self, phase:str):
		def err(items:list[SyntaxNode], msg:str):
			self.error(phase, [i.head() for i in items], msg)
		return err
		
