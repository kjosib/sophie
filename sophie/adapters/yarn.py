"""
A host module for Sophie's nontrivial intrinsics, such as string functions,
which have some impedance mismatch between the Sophie and Python conceptions.
"""

from ..runtime import iterate_list, as_sophie_list

nope = {"":"nope"}

def mid(aString, offset, size):
	return aString[max(0, offset) : max(0, offset+size)]

def val(aString):
	try: answer = float(aString)
	except ValueError: return nope
	else: return {"":"this", "item":answer}

def identity(x):
	# This one's just for messing around with the type system.
	# Something in the zoo-of-ok imports it across the FFI.
	return x

def join(xs):
	return "".join(iterate_list(xs))

def is_match_at(offset, needle, haystack):
	return offset >= 0 and needle == haystack[offset:offset+len(needle)]

trim = str.strip
ltrim = str.lstrip
rtrim = str.rstrip

def split_lines(s:str):
	return as_sophie_list(s.splitlines(keepends=True))

