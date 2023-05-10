Reference Manual
==================

    Obviously a work in progress...

.. contents::
    :local:
    :depth: 2


Grammar
-------------

The primary authority is at `the literate grammar file <https://github.com/kjosib/sophie/blob/main/sophie/Sophie.md>`_
which -- despite reading mostly like a reference document -- is actually what the implementation uses internally.
(If you must know, it's input to `this system <https://pypi.org/project/booze-tools/>`_.)

Sophie is not exactly *block-structured:* module files have sections dedicated to:

* Exports
* Imports
* Type definitions
* Function definitions
* "Main-Program" Behavior

Every section is optional, but if it appears, it must appear in exactly that order.

Within each section but the last, there is no ordering constraint.
There is neither the need for, nor any concept of, *forward-declaration* of any kind.

Semantics
-----------

* Function application is call-by-need, except for primitive functions which are strict in every argument.
  Thus, if the value of a particular argument does not contribute to evaluating the body of a function,
  then the argument itself never gets evaluated (in the context where it appears). However, no single expression
  gets evaluated twice in the same (dynamic) scope.

* Data structures are lazy, meaning that you're welcome to express an infinite list as long as you don't consume it all.

* The logical connectives ``and`` and ``or`` use short-cut logic:
  if the expression on the left side determines the result,
  then the expression on the right side never gets evaluated.

* ``case ... when ... then ... else ... esac`` branching clauses apply tests strictly in order,
  and evaluate only enough to decide which branch (``then`` or ``else`` clause) to take.

* Explicit lists like ``[this, that, the, other]`` are internally translated to nested ``cons(...)`` constructions.

* Strings are considered atomic: they will not participate in a sequence protocol.
  However, functions may be provided to examine individual characters, take substrings, or iterate through characters.

* The run-time is free to adjust the order of evaluation or internal representations of things,
  so long as it preserves the outwardly-observable behavior.

* Right now, the ``begin:`` clause lists expressions and the run-time prints the value of the expressions.
  However, if an expression is a ``turtle`` record, then the result is a turtle-graphics drawing. (See below.)

* Module imports may not form a cycle.

Intrinsics
------------

Predefined type names include ``flag``, ``number``, ``string``, and ``list``.
That last has the pre-defined constructor ``cons``, which takes fields ``head`` and ``tail``.
The implementation of explicit lists like ``[this, that, the, other]`` is in terms of ``cons``.
The Boolean truth values are called ``yes`` and ``no``.

There are also predefined bits for working with turtle graphics.
(See the chapter on turtle graphics.)

Predefined functions include:

* ``id(x)``: Return ``x`` as-is.
* ``any(xs)``: True when at least one member of an input list evaluates to true. (Otherwise false.)
* ``all(xs)``: False when at least one member of an input list evaluates to false. (Otherwise true.)
* ``map(fn, xs)``: Produce a list by applying ``fn`` to all members of ``xs``.
* ``filter(predicate, xs)``: Returns a list composed of those elements from ``fn`` such that ``predicate(fn)``.
* ``reduce(fn, a, xs)``: Produce a single element by applying ``fn`` repeatedly to rolling pairs of arguments:
  first ``a`` and the head of ``xs``, then that result with the next entry in ``xs``, and so forth.
  If ``xs`` is empty, it returns ``a`` without ever calling ``fn``.
* ``expand`` is not currently a thing. When it becomes a thing, this page will update.
* ``cat(xs, ys)``: Return a list composed of the elements of ``xs`` followed by those of ``ys``.
* ``flat(xss)``: Given a list of lists, return a single list composed of the elements of each input list in sequence.
* ``sum(xs)``: add all the numbers in the given list and return their sum, or a if the list is empty.
* ``take(n, xs)``: return a list composed of the first ``n`` elements of ``xs``.
* ``skip(n, xs)``: return the remainder of list ``xs`` after skipping the first ``n`` elements.


* Python's math library of functions and constants are also installed, with two caveats:
  * ``log`` becomes two functions: ``log(x)`` and ``log_base(x, b)`` because Sophie does not deal in optional arguments.
  * ``hypot`` is re-implemented in Sophie because the python version takes a variable number of arguments, which is currently too hard to deal with more directly.

If you'd like to see how that's all been done,
you can find the standard preamble `here <https://github.com/kjosib/sophie/blob/main/sophie/sys/preamble.sg>`_.


Modularity, Imports, and Exports
--------------------------------

Sophie has nothing to say about how you name your module files.
They're yours to name and organize as you wish.
If you want spaces in your filenames, that should be no problem at all.
So Sophie separates the notion of *where to find the module's code*
from the notion of *how to refer, in code, to the module.*

Simple Whole-Module Imports
............................

You can import a module *as a name*.

Suppose we have a module called ``path/to/feline.sg`` which defines a function called ``tabby``.
And suppose further that you wish to call ``tabby`` from some other module.
Then, you can first import the module, perhaps assigning it the (local) module-identifier ``cat``::

    import:
    "path/to/feline.sg" as cat;  # Assume this cat-module defines a function called "tabby";

Now ``cat`` shows up as a named-namespace from which you can draw qualified-names.
You can refer to the aforementioned ``tabby`` function as follows::

    define:
        kitten = tabby@cat(123);  # We can use the word "tabby" but must mention where it came from.

Note that the module-identifier ``cat`` comes *after* the function name.
This works like an internet e-mail address: You specify just enough to find the thing in context.

Benefits:
    * You can see at a glance where everything's definition comes from, wherever the word may be used.
      This can be helpful in a large file that orchestrates several other modules.

Drawbacks:
    * Tagging every mention of an imported symbol with the name of its origin can get tiresome and distracting.

Importing Specific Symbols
...........................

You can import specific words from a module::

    import:
        "path/to/cat/in/hat.sg" (thing_one, thing_two);
    define:
        big_mess = thing_one + thing_two;

In this case, ``thing_one`` and ``thing_two`` behave exactly as if you had defined them yourself.
You cannot separately define another ``thing_one`` or ``thing_two`` in the same file,
because you've already assigned those words via the ``import:`` declaration.

Benefits:
    * Code might read more naturally when not splattered with ``@this_module`` and ``@that_module`` all over.
    * You retain a quick-reference to where imported words come from.

Drawbacks:
    * Different import-modules might define the same name to mean different things, both of which you need.

Some of Column A, Some of Column B
.......................................

You can combine the above techniques::

    import:
        "path/to/cat/in/hat.sg" as cat (thing_one, thing_two);
    define:
        even_bigger_mess = thing_one + thing_two + worried_goldfish@cat;

The situation here is that, although ``thing_one`` and ``thing_two`` are available directly,
you can also pick up extra bits from the ``cat`` module as you need them. That's a handy
middle-ground if there are a few imported words you use frequently and others you mention only once or twice.
It also solves the problem of what if you need ``worried_goldfish`` from more than one import-module.

Importing with Local Renaming
..............................

You can import specific symbols with alternative local names::

    import:
        "path/to/famous/people.sg" (Lincoln as President);
        "path/to/Nebraska/cities.sg" (Lincoln as Capitol);

This style of import can also deal with the problem of homonyms, but use this with care.
It's probably OK for a short, self-contained program,
but it can lead to confusion in a large system with many people working on different parts at different times.

Importing from a Package of Shared Code
........................................

**Code you did not write yourself** is probably part of a package.
Sophie's package system is still in its infancy. For now, there is only one pacakge, called ``sys``.
You can import a module *from a package* by specifying the package's *symbol* before the import path::

    import:
        sys."turtle.sg" (drawing, forward, reverse, left, right);

.. note:: This is only the second version of the modularity system. In time, it may get a few more features.

