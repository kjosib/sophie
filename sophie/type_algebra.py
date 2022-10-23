"""
All the bits for the data typing mechanism to work.
This means:

1. Atoms, such as "flag" and "real". Maybe also "void" and "diverge"?
2. Constructors: record, union, tag, arrow
3. Operations that compute on the space of types.

A. Types are objects in their own right.
B. Type Variables are also objects, with identity.
C. Records, unions, and tags have identity. All else is structural (for now).

The type of a function-over-values is itself a function-over-types.
But only when that first function is generic does the second function look at all interesting.

The operation of the type-function is to set up a system of constraints on the type-variables
associated with the value-expressions associated with each call site.

The key to it all is the matching and unification mechanism as a critical component.
"""

class ProductType:
	# stand-in until something nicer.
	def __init__(self, slots):
		self.slots = slots

