from pathlib import Path
import unittest
from sophie import modularity, diagnostics, syntax

base_folder = Path(__file__).parent.parent
example_folder = base_folder/"examples"

def _good_example(which) -> modularity.Loader:
	report = diagnostics.Report(verbose=False)
	loader = modularity.Loader(report, experimental=False)
	if loader.load_program(example_folder, which + ".sg"):
		return loader
	else:
		report.complain_to_console()
		assert False

class ExampleSmokeTests(unittest.TestCase):
	""" Run all the examples; Test for no smoke. """
	
	def test_alias(self):
		""" The result of running a program is the value of its last expression. """
		self.assertEqual(7, _good_example("alias").run())
	
	def test_graphical_examples_compile(self):
		for name in ["turtle", "color_spiral", "simple_designs"]:
			with self.subTest(name):
				_good_example(name)

	def test_other_examples(self):
		for name in [
			"hello_world",
			"patron",
			"simple_calculations",
			"explicit_list_construction",
			"Newton",
			"Newton_2",
			"Newton_3",
			"case_when",
			"some_arithmetic",
			"Fibonacci",
			"primes",
			"generic_parameter",
		]:
			with self.subTest(name):
				_good_example(name).run()

if __name__ == '__main__':
	unittest.main()
