"""
Main driver for Sophie semi-langauge
"""
from pathlib import Path
from .front_end import sophie_parser

def main(pathname):
	"""Read file given by name; pass contents to next phase."""
	with open(pathname, "r") as fh:
		text = fh.read()
	return compile_sophie(text, pathname)

def compile_sophie(text:str, pathname:Path):
	""" Submit text to parser; submit the resulting tree to subsequent pass """
	return sophie_parser.parse(text, filename=pathname)

