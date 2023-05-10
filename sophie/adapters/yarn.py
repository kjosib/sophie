"""
A host module for Sophie's nontrivial intrinsics, such as string functions,
which have some impedance mismatch between the Sophie and Python conceptions.
"""

nope = {"":"nope"}

def mid(aString, offset, size): return aString[max(0, offset) : max(0, offset+size)]
def val(aString):
	try: answer = float(aString)
	except ValueError: return nope
	else: return {"":"this", "item":answer}