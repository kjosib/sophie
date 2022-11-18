from boozetools.support.failureprone import Issue, Evidence, Severity

class Report:
	issues : list[Issue]
	
	def __init__(self):
		self.issues = []
		
	def error(self, guilty:list[slice], phase:str, description:str):
		evidence = {"": [Evidence(s, "") for s in guilty]}
		self.issues.append(Issue(phase, Severity.ERROR, description, evidence))

