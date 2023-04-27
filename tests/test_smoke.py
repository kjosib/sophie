from pathlib import Path
import unittest
from sophie import modularity, diagnostics, syntax

base_folder = Path(__file__).parent.parent
example_folder = base_folder/"examples"

def _good_example(which, experimental) -> modularity.Loader:
	report = diagnostics.Report()
	loader = modularity.Loader(report, verbose=False, experimental=experimental)
	if loader.load_program(example_folder, which + ".sg"):
		return loader
	else:
		report.complain_to_console()
		assert False

class ExampleSmokeTests(unittest.TestCase):
	""" Run all the examples; Test for no smoke. """
	
	def test_other_examples(self):
		for name in ["some_arithmetic", "primes", "Newton", "Newton_2", "Newton_3", "case_when", "Fibonacci"]:
			with self.subTest(name):
				_good_example(name, False).run()
	
	def test_alias(self):
		""" The result of running a program is the value of its last expression. """
		self.assertEqual(7, _good_example("alias", True).run())
	
	def test_graphical_examples_compile(self):
		for name in ["turtle", "color_spiral", "simple_designs"]:
			with self.subTest(name):
				_good_example(name, False)

	def test_examples_that_should_type(self):
		for name in ["hello_world", "patron", "simple_calculations", ]:
			with self.subTest(name):
				_good_example(name, True).run()

if __name__ == '__main__':
	unittest.main()
