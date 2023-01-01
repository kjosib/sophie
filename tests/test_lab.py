"""
Tests specifically related to things not fully working yet.

(When they work properly, they move to the regular tests.)

"""
from pathlib import Path
import unittest

from sophie.preamble import static_root
from sophie import experimental, manifest, diagnostics, algebra, syntax, primitive, modularity

base_folder = Path(__file__).parent.parent
example_folder = base_folder/"examples"
zoo_ok = base_folder/"zoo/ok"

def assert_convergent(sym):
	# Maybe a function's type is "convergent" when it has no free variables in the result.
	# In other words, all the type-variables in the result appear somewhere in a binding context:
	# either its own parameters, or those of its parent functions.
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
		loader = modularity.Loader(static_root, report, experimental=False)
		module = loader.need_module(folder, which + ".sg")
		if report.issues:
			report.complain_to_console()
			assert False
		else:
			experimental.Experiment(module, self.report.on_error("Experimental Phase"), verbose=True)
			return module
	
	def test_Newton(self):
		module = self.load(example_folder, "Newton")
		assert not self.report.issues, self.report.complain_to_console()
		assert_convergent(module.globals['iterate_four_times'])
		root = module.globals['root']
		assert_convergent(root)
		assert isinstance(root.typ, algebra.Arrow)
		arg = root.typ.arg
		assert isinstance(arg, algebra.Product)
		assert len(arg.fields) == 1
		a0 = arg.fields[0]
		assert isinstance(a0, algebra.Nominal)
		assert a0.dfn is primitive.literal_number.dfn
	
	def test_bipartite(self):
		module = self.load(zoo_ok, "bipartite_list")
		assert not self.report.issues, self.report.complain_to_console()
		cmap = module.globals['cmap']
		assert_convergent(cmap)
		assert isinstance(cmap.typ, algebra.Arrow)
		res = cmap.typ.res
		assert isinstance(res, algebra.Nominal)
		assert res.dfn.nom.text == "critter"
		assert res.params[0] != res.params[1]
	
	def test_recur(self):
		""" (number, number) -> list[<a>] is the wrong type for a recurrence relation. """
		module = self.load(zoo_ok, "recur")
		assert not self.report.issues, self.report.complain_to_console()
		assert_convergent(module.globals['recur'])

if __name__ == '__main__':
	unittest.main()
