from pathlib import Path
import unittest
from sophie import modularity, diagnostics, syntax

base_folder = Path(__file__).parent.parent
examples = base_folder/"examples"
zoo_ok = base_folder/"zoo/ok"


def _good(folder, which) -> modularity.Loader:
	report = diagnostics.Report(verbose=False)
	loader = modularity.Loader(report, experimental=False)
	if loader.load_program(folder, which + ".sg"):
		return loader
	else:
		report.complain_to_console()
		assert False

class ExampleSmokeTests(unittest.TestCase):
	""" Run all the examples; Test for no smoke. """
	
	def test_alias(self):
		""" The result of running a program is the value of its last expression. """
		self.assertEqual(7, _good(examples, "tutorial/alias").run())
	
	def test_turtle_examples_compile(self):
		for name in ["turtle", "color_spiral", "simple_designs"]:
			with self.subTest(name):
				_good(examples, "turtle/"+name)

	def test_game_examples_compile(self):
		for name in ["guess_the_number", "99 bottles"]:
			with self.subTest(name):
				_good(examples, "games/"+name)

	def test_other_examples(self):
		for name in [
			"hello_world",
			"tutorial/patron",
			"tutorial/simple_calculations",
			"tutorial/explicit_list_construction",
			"mathematics/Newton",
			"mathematics/Newton_2",
			"mathematics/Newton_3",
			"tutorial/case_when",
			"tutorial/some_arithmetic",
			"mathematics/Fibonacci",
			"mathematics/primes",
			"tutorial/generic_parameter",
		]:
			with self.subTest(name):
				_good(examples, name).run()
	
	def test_zoo_of_ok(self):
		for name in [
			"arrows",
		]:
			with self.subTest(name):
				_good(zoo_ok, name).run()


if __name__ == '__main__':
	unittest.main()
