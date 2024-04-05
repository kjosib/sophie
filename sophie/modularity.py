"""
Here find the module system -- such as it is.

The present state of affairs is loosey-goosey with parent-directory access.
"""
from pathlib import Path
from typing import Optional

from .diagnostics import Report
from .front_end import parse_text
from .ontology import Expr
from .syntax import Module, ImportModule

class SophieParseError(Exception):
	pass

class SophieImportError(Exception):
	""" As distinct from a Python import error """

PACKAGE_ROOT = {
	"sys" : Path(__file__).parent/"sys",
}

class Program:
	"""
	Focus very specifically on getting to a dictionary from
	absolute paths to syntax.Module objects and their order.
	In other words, this particular class interprets imports.

	# Weird observation: Dealing with the preamble is mildly weird.
	"""

	def __init__(self, main_path:Path, report: Report):
		def require(path:Path, cause:Optional[Expr]) -> Module:
			""" This function may raise an exception on failure. """
			abs_path = path.resolve()
			if abs_path not in parsed_modules:
				self.module_sequence.append(miss_cache(abs_path, cause))
			return parsed_modules[abs_path]

		def miss_cache(abs_path: Path, cause: Optional[Expr]):
			if abs_path in construction_stack:
				depth = construction_stack.index(abs_path)
				report.cyclic_import(cause, construction_stack[depth:])
				raise SophieImportError
			else:
				return load_module(abs_path, cause)
			
		def load_module(abs_path: Path, cause: Optional[Expr]):
			report.info("Loading", abs_path)
			try:
				with open(abs_path, "r", encoding="utf-8") as fh:
					text = fh.read()
			except FileNotFoundError:
				report.no_such_file(abs_path, cause)
				raise SophieImportError
			except OSError:
				report.broken_file(abs_path, cause)
				raise SophieImportError
			if text is None:
				assert report.sick()
			else:
				enter(abs_path)
				module = parse_text(text, abs_path, report)
				if module:
					report.assert_no_issues("Parser reported errors but failed to fail.")
					module.source_path = abs_path
					chase_the_imports(abs_path.parent, module.imports)
					parsed_modules[abs_path] = module
				else:
					assert report.sick()
					raise SophieParseError
				leave()
				return module

		def enter(abs_path):
			construction_stack.append(abs_path)
			report.set_path(abs_path)

		def leave():
			construction_stack.pop()
			if construction_stack:
				report.set_path(construction_stack[-1])
			else:
				report.set_path(None)

		def chase_the_imports(base, directives):
			""" Interpret the import directives in a module... """
			for im in directives:
				assert isinstance(im, ImportModule)
				import_path = root_for_import(base, im) / (im.relative_path.value + ".sg")
				self.import_map[im] = require(import_path, im.relative_path)

		def root_for_import(base: Path, im: ImportModule):
			if im.package is None:
				return base
			else:
				try:
					return PACKAGE_ROOT[im.package.text]
				except KeyError:
					report.no_such_package(im.package)
					raise SophieImportError

		construction_stack = []
		self.import_map:dict[ImportModule,Module] = {}
		parsed_modules:dict[Path,Module] = {}
		self.module_sequence:list[Module] = []
		preamble_path = (PACKAGE_ROOT["sys"] / "preamble.sg").resolve()
		self.preamble = load_module(preamble_path, None)
		self.main_key = require(main_path, None)

