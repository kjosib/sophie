"""
Here find the module system -- such as it is.
"""
import os.path
from boozetools.support.symtab import SymbolAlreadyExists
from .diagnostics import Report
from .front_end import parse_file
from .syntax import Module, Literal
from .resolution import resolve_words
from .manifest import type_module
from .type_inference import infer_types

class _CircularDependencyError(Exception):
	""" This can only happen during a nested recursive call, so the exception is private. """

class Loader:
	def __init__(self, root, report:Report, verbose:bool):
		self._root = root
		self._report = report
		self._on_error = report.on_error("Loading Modules")
		self._prepared_modules = {}
		self._construction_stack = []
		self.module_sequence = []
		self._verbose = verbose

	def need_module(self, base_path, module_path:str) -> Module:
		"""
		This function may raise an exception on failure.
		"""
		abs_path = os.path.normpath(os.path.join(base_path, module_path))
		if abs_path in self._prepared_modules:
			return self._prepared_modules[abs_path]
		if abs_path in self._construction_stack:
			depth = self._construction_stack.index(abs_path)
			cycle = self._construction_stack[depth:]
			raise _CircularDependencyError(cycle)
		else:
			self._construction_stack.append(abs_path)
			module = self._load_normal_file(abs_path)
			self._construction_stack.pop()
		self.module_sequence.append(module)
		self._prepared_modules[abs_path] = module
		return module
	
	def _load_normal_file(self, abs_path):
		if self._verbose:
			print("Loading", abs_path)
		module = parse_file(abs_path, self._report)
		if not self._report.issues:
			self._interpret_the_import_directives(module, os.path.dirname(abs_path))
		if not self._report.issues:
			resolve_words(module, self._root, self._report)
		if not self._report.issues:
			type_module(module, self._report)
		if not self._report.issues:
			infer_types(module, self._report, verbose=self._verbose)
		return module
	
	def _interpret_the_import_directives(self, module:Module, base_path):
		""" Interpret the import directives in a module... """
		for module_path, nom in module.imports:
			assert isinstance(module_path, Literal), module_path
			try:
				dependency = self.need_module(base_path, module_path.value)
				module.module_imports[nom.text] = dependency.globals
			except FileNotFoundError:
				self._on_error([module_path], "Sorry, there's no such file.")
			except _CircularDependencyError as cde:
				cycle_text = "\n".join(["Confused by a circular dependency.", *cde.args[0]])
				self._on_error([module_path], cycle_text)
			except SymbolAlreadyExists:
				self._on_error([nom], "This module-alias is already used earlier.")

