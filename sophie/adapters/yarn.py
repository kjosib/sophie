"""
A host module for Sophie's nontrivial intrinsics, such as string functions,
which have some impedance mismatch between the Sophie and Python conceptions.
"""

from ..tree_walker.runtime import iterate_list, as_sophie_list, sophie_nope, sophie_this

def mid(aString, offset, size):
	return aString[max(0, offset) : max(0, offset+size)]

def val(aString):
	try: answer = float(aString)
	except ValueError: return sophie_nope()
	else: return sophie_this(answer)

def join(xs):
	return "".join(iterate_list(xs))

def is_match_at(offset, needle, haystack):
	return offset >= 0 and needle == haystack[offset:offset+len(needle)]

trim = str.strip
ltrim = str.lstrip
rtrim = str.rstrip

def split_lines(s:str):
	return as_sophie_list(s.splitlines(keepends=True))

