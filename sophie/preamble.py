"""
# Built-in / primitive definitions and types.

# For the moment, I mainly need a definitions for a (lazy) linked-list,
# which the interpreter can make instances of directly via syntax sugar.
# That means a constructor (presumably called "cons")
# and it needs to be connected with a suitable definition of a cons-cell.

# The interface to types is just nascent and will change much.

type:

list[x] is { nil | cons(head:x, tail:list[x]) };

begin: 1; end.

"""

class NativeType:
	pass

def _init():
	from boozetools.support.symtab import NameSpace
	from . import front_end, compiler
	primitive_root = NameSpace(place=None)
	primitive_root['flag'] = NativeType()
	primitive_root['number'] = NativeType()
	primitive_root['string'] = NativeType()
	preamble = front_end.parse_text(__doc__, __file__)
	issues = compiler.resolve_words(preamble, primitive_root)
	if issues:
		front_end.complain(issues)
		raise ValueError()
	else:
		return preamble.namespace

static_root = _init()

