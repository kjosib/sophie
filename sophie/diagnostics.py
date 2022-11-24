from boozetools.support.failureprone import Issue, Evidence, Severity
from .ontology import SyntaxNode

class Report:
	issues : list[Issue]
	
	def __init__(self):
		self.issues = []
		
	def error(self, guilty:list[slice], phase:str, msg:str):
		evidence = {"": [Evidence(s, "") for s in guilty]}
		self.issues.append(Issue(phase, Severity.ERROR, msg, evidence))

	def on_error(self, phase:str):
		def err(items:list[SyntaxNode], msg:str):
			self.error([i.head() for i in items], phase, msg)
		return err
		
