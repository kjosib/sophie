"""
Here find the module system -- such as it is.

The present state of affairs is loosey-goosey with parent-directory access.
"""
from pathlib import Path
from typing import Optional
from .diagnostics import Report
from .front_end import parse_file
from .syntax import Module, ImportModule
from . import resolution
from .type_evaluator import DeductionEngine

class SophieImportError(Exception):
	""" As distinct from a Python import error """

class _CircularDependencyError(SophieImportError):
	""" This can only happen during a nested recursive call, so the exception is private. """

class _NoSuchPackageError(SophieImportError):
	""" This can only happen during a nested recursive call, so the exception is private. """

PACKAGE_ROOT = {
	"sys" : Path(__file__).parent/"sys",
}

class Loader:
	def __init__(self, report: Report, experimental:bool= False):
		self._report = report
		self._on_error = report.on_error("Loading Program")
		self._loaded_modules = {}
		self._construction_stack = []
		self.module_sequence = []
		self._experimental = experimental
		self._deductionEngine = DeductionEngine(report)
		self._preamble = self._load_preamble()
	
	def need_module(self, path:Path) -> Optional[Module]:
		""" This function may raise an exception on failure. """
		abs_path = path.resolve()
		if abs_path not in self._loaded_modules:
			self._loaded_modules[abs_path] = self._cache_miss(abs_path)
		return self._loaded_modules[abs_path]
	
	def _cache_miss(self, abs_path):
		if abs_path in self._construction_stack:
			depth = self._construction_stack.index(abs_path)
			cycle = self._construction_stack[depth:]
			raise _CircularDependencyError(cycle)
		else:
			self._enter(abs_path)
			self._report.info("Loading", abs_path)
			module = parse_file(abs_path, self._report)
			if module:
				self._interpret_the_import_directives(module)
				self._prepare_module(module, self._preamble.globals)
				self.module_sequence.append(module)
			self._exit()
			return module
	
	def _enter(self, abs_path):
		self._construction_stack.append(abs_path)
		self._report.set_path(abs_path)
	
	def _exit(self):
		self._construction_stack.pop()
		if self._construction_stack:
			self._report.set_path(self._construction_stack[-1])
		else:
			self._report.set_path(None)
		
	def load_program(self, base_path:Path, module_path:str):
		module = self.need_module(base_path / module_path)
		if module and not module.main and self._report.ok():
			self._on_error([], str(module_path)+" has no `begin:` section and thus is not a main program.")
		return self._report.ok()
	
	def run(self):
		from .simple_evaluator import run_program
		return run_program(self._preamble.globals, self.module_sequence)
	
	def _load_preamble(self):
		from pathlib import Path
		from . import primitive
		preamble_path = PACKAGE_ROOT["sys"]/"preamble.sg"
		self._enter(preamble_path)
		module = parse_file(preamble_path, self._report)
		self._prepare_module(module, primitive.root_namespace)
		self._report.assert_no_issues()
		primitive.LIST = module.globals['list']
		self._exit()
		return module
	
	def _prepare_module(self, module, outer):
		"""
		If this returns a string, it's the name of the pass in which a problem was first noted.
		The end-user might not care about this, but it's handy for testing.
		"""
		if self._report.sick(): return "parse"
		assert isinstance(module, Module)
		
		resolution.WordDefiner(module, outer, self._report)
		if self._report.sick(): return "define"
		
		resolution.StaticDepthPass(module)  # Cannot fail
		
		alias_constructors = resolution.WordResolver(module, self._report).dubious_constructors
		if self._report.sick(): return "resolve"
		
		resolution.AliasChecker(module, self._report)
		if self._report.sick(): return "alias"
		
		resolution.check_constructors(alias_constructors, self._report)
		if self._report.sick(): return "constructors"

		resolution.check_all_match_expressions(module, self._report)
		if self._report.sick(): return "match_check"
		
		resolution.build_match_dispatch_tables(module)  # Cannot fail, for checks have been done earlier.
		
		self._deductionEngine.visit(module)
		if self._report.sick(): return "type_check"
	
	def _root_for_import(self, base:Path, im:ImportModule):
		if im.package is None:
			return base
		else:
			try:
				return PACKAGE_ROOT[im.package.text]
			except KeyError:
				self._on_error([im.package], "There's no such package. (At the moment, there is only sys.)")
	
	def _interpret_the_import_directives(self, module:Module):
		""" Interpret the import directives in a module... """
		base = module.path.parent
		for im in module.imports:
			assert isinstance(im, ImportModule)
			import_path = self._root_for_import(base, im) / (im.relative_path.value + ".sg")
			try: im.module = self.need_module(import_path)
			except _CircularDependencyError as cde:
				cycle_paths = map(str, cde.args[0])
				cycle_text = "\n".join(["Confused by a circular dependency:", *cycle_paths])
				self._on_error([im.relative_path], cycle_text)

