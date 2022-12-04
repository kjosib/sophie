"""
Tests specifically related to things not fully working yet.

(When they work properly, they move to the regular tests.)

"""
from pathlib import Path
import unittest

from sophie.front_end import parse_file, complain
from sophie.resolution import resolve_words
from sophie.primitive import root_namespace
from sophie import experimental, manifest, diagnostics, algebra, syntax

base_folder = Path(__file__).parent.parent
example_folder = base_folder/"examples"
zoo_ok = base_folder/"zoo/ok"

def assert_convergent(sym):
	assert isinstance(sym, syntax.Function)
	typ = sym.typ
	assert isinstance(typ, algebra.Arrow), typ
	arg = set()
	typ.arg.poll(arg)
	
	res = set()
	typ.res.poll(res)
	
	free = res - arg
	
	assert not free, (typ.render({}, {}), free)
	

class ExperimentTests(unittest.TestCase):
	
	def setUp(self) -> None:
		algebra.TypeVariable._counter = 0
		self.report = diagnostics.Report()
	
	def load(self, folder, which):
		report = self.report
		module = parse_file(folder / (which + ".sg"), report)
		if not report.issues:
			resolve_words(module, root_namespace, report)
		if not report.issues:
			manifest.type_module(module, report)
		if report.issues:
			complain(report)
			assert False
		else:
			experimental.Experiment(module, self.report.on_error("Experimental Phase"))
			return module
	
	def test_Newton(self):
		module = self.load(example_folder, "Newton")
		assert not self.report.issues, complain(self.report)
		assert_convergent(module.namespace['iterate_four_times'])
		assert_convergent(module.namespace['root'])
	
	def test_bipartite(self):
		module = self.load(zoo_ok, "bipartite_list")
		assert not self.report.issues, complain(self.report)
		# A function's type is convergent when it has no free variables in the result.
		# In other words, all the type-variables in the result appear somewhere in a binding context:
		# either its own parameters, or those of its parent functions.
		assert_convergent(module.namespace['cmap'])
		pass

if __name__ == '__main__':
	unittest.main()
