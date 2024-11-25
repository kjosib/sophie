Factoring out Non-Local Capture
===============================

.. note:: This chapter describes Sophie internals. Most users won't care. But language hackers might be interested.

.. contents::
   :local:
   :depth: 3

The Situation
--------------

November 2024

The different parts of Sophie's implementation have grown organically and, in many respects, independently.
But now I see a bit of information several phases use (implicitly or otherwise) but they all calculate it
in their own special way. Specifically, that's the set of non-local variables/parameters which each scope
uses, either *directly* by mentioning the symbol, or *implicitly* where a sub-function mentions the symbol.

The ``translate.py`` module builds and uses this information as a side-effect of performing the translation,
since the VM is designed to use the *upvar* method of capture rather than maintaining linked lists of scopes.
Its *method* is a model of simplicity: easy to explain and obviously correct. However, its *code* is
intertwined with other aspects of the translation to VM-food.

The ``type_evaluator.py`` module came before the VM or trying to generate code for such a thing.
However, it also used an idea of non-local capture for an aspect of the type-checking architecture.
(It takes note of the known result of applying a function to a given set of types.)
It currently has ``class DependencyPass`` which calculates a similar result, but in an over-complicated way.

The ``runtime.py`` module in fact works with a linked list of scopes, but it might be nice to mirror the
approach of the VM here. Simplifying the correspondence between the two would probably be a good thing.

I'd like to factor out the problem to determine non-local capture for functions,
and then give the information a standard representation in the symbol table.
This should reduce the total amount of work done to translate code.


The Plan
---------

The simplest version of a capture map probably adds a list of non-local captures to every symbol that
can represent a closure. That means functions, procedures, and lambda-forms. Conveniently,
these all fall under the base ``class Subroutine`` in the syntax, so there's a nice place for it.

One representation is just a list of non-local symbols. However, there's a complication:
The translator needs to know if that symbol is *directly* or *indirectly* imported from
the immediately-containing subroutine. (Direct imports are found on the stack,
but indirect imports are found in the surrounding function's own closure.)

One solution would be to associate every symbol with the function in which it's declared/created.
This makes the information available to the translator at the cost of an odd comparison.
The other solution is to store captures as pairs containing a symbol and a flag.
That is what the VM uses anyway, and it works well enough. So I'll do it that way.

In principle it can be done early, perhaps even as early as symbol resolution.
In fact, that's exactly the right time/place to do it.

Phases
.......

1. Modify the resolver to build the import-map as it goes along. Use the ``(symbol, is_direct)`` pairing.
2. Simplify ``translate.py`` to rely on this new mechanism. Check everything.
3. Change ``runtime.py`` to follow the VM's lead on the *upvar* mechanism, using the capture-map.
4. Finally, ``type_evaluator.py`` drops the ``DependencyPass`` and relies on the capture-map instead.

