"""
Built-in / primitive definitions and types.

For the moment, I mainly need a definitions for a (lazy) linked-list,
which the interpreter can make instances of directly via syntax sugar.
That means a constructor (presumably called "cons")
and it needs to be connected with a suitable definition of a cons-cell.

The interface to types is just nascent and will change much.
"""

from collections import namedtuple
from boozetools.support.symtab import NameSpace
from . import type_algebra

static_root = NameSpace(place=None)
static_root['cons'] = type_algebra.ProductType(['head', 'tail'])
