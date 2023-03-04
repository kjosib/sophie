"""
A host module for Sophie's nontrivial intrinsics, such as string functions,
which have some impedance mismatch between the Sophie and Python conceptions.
"""

def mid(aString, offset, size): return aString[max(0, offset) : max(0, offset+size)]

