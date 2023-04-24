""" Here find the module system -- such as it is. """
import os.path
import sys
from boozetools.support.symtab import SymbolAlreadyExists
from .diagnostics import Report
from .front_end import parse_file
from .syntax import Module, ImportModule
from .resolution import resolve_words, AliasChecker, check_all_match_expressions
from . import preamble

class _CircularDependencyError(Exception):
	""" This can only happen during a nested recursive call, so the exception is private. """

class Loader:
	def __init__(self, report: Report, verbose:bool, experimental:bool= False):
		self._report = report
		self._on_error = report.on_error("Loading Program")
		self._loaded_modules = {}
		self._construction_stack = []
		self.module_sequence = []
		self._verbose = verbose
		self._manifest = {}
		self._experimental = experimental
		if experimental:
			from .hot.ruminate import DeductionEngine
			self._deductionEngine = DeductionEngine(report)
			self._deductionEngine.visit(preamble.module)
		self._report.assert_no_issues()
	
	def need_module(self, base_path, module_path:str) -> Module:
		"""
		This function may raise an exception on failure.
		"""
		abs_path = os.path.normpath(os.path.join(base_path, module_path))
		if abs_path in self._loaded_modules:
			return self._loaded_modules[abs_path]
		if abs_path in self._construction_stack:
			depth = self._construction_stack.index(abs_path)
			cycle = self._construction_stack[depth:]
			raise _CircularDependencyError(cycle)
		else:
			self._enter(abs_path)
			module = self._load_normal_file(abs_path)
			self._loaded_modules[abs_path] = module
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
		
	def load_program(self, base_path, module_path:str):
		module = self.need_module(base_path, module_path)
		if module and not module.main and not self._report.issues:
			self._on_error([], str(module_path)+" has no `begin:` section and thus is not a main program.")
		return not self._report.issues
	
	def run(self):
		from .simple_evaluator import run_program
		return run_program(preamble.module.globals, self.module_sequence)
	
	def _load_normal_file(self, abs_path):
		if self._verbose:
			print("Loading", abs_path, file=sys.stderr)
		module = parse_file(abs_path, self._report)
		if not self._report.issues:
			self._interpret_the_import_directives(module, os.path.dirname(abs_path))
		self._prepare_module(module)
		return module
	
	def _prepare_module(self, module):
		if not self._report.issues:
			resolve_words(module, preamble.module.globals, self._report)
		if not self._report.issues:
			AliasChecker(module, self._report)
		if not self._report.issues:
			check_all_match_expressions(module, self._report)
		if self._experimental and not self._report.issues:
			self._deductionEngine.visit(module)
	
	def _interpret_the_import_directives(self, module:Module, base_path):
		""" Interpret the import directives in a module... """
		for directive in module.imports:
			assert isinstance(directive, ImportModule)
			try:
				dependency = self.need_module(base_path, directive.relative_path.value)
				if dependency:
					module.module_imports[directive.nom.text] = dependency.globals
				else:
					self._on_error([directive.relative_path], "This file did not load properly.")
			except FileNotFoundError:
				self._on_error([directive.relative_path], "Sorry, there's no such file.")
			except _CircularDependencyError as cde:
				cycle_text = "\n".join(["Confused by a circular dependency:", *cde.args[0]])
				self._on_error([directive.relative_path], cycle_text)
			except SymbolAlreadyExists:
				self._on_error([directive.nom], "This module-alias is already used earlier.")

