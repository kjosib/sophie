Reference Manual
==================

    Obviously a work in progress...

.. contents::
    :depth: 2


Grammar
-------------

The primary authority is at `the literate grammar file <https://github.com/kjosib/sophie/blob/main/sophie/Sophie.md>`_
which -- despite reading mostly like a reference document -- is actually what the implementation uses internally.
(If you must know, it's input to `this system <https://pypi.org/project/booze-tools/>`_.)


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


Intrinsics
------------

Predefined type names include ``flag``, ``number``, ``string``, and ``list``.
That last has the pre-defined constructor ``cons``, which takes fields ``head`` and ``tail``.
The implementation of explicit lists like ``[this, that, the, other]`` is in terms of ``cons``.
The Boolean truth values are called ``yes`` and ``no``.

Predefined functions include:

* ``any(xs)``: True when at least one member of an input list evaluates to true. (Otherwise false.)
* ``all(xs)``: False when at least one member of an input list evaluates to false. (Otherwise true.)
* ``map(fn, xs)``: Produce a list by applying ``fn`` to all members of ``xs``.
* ``reduce(fn, zero, xs)``: Produce a single element by applying ``fn`` repeatedly to rolling pairs of arguments:
  first ``zero`` and the head of ``xs``, then that result with the next entry in ``xs``, and so forth.
  If ``xs`` is empty, it returns ``zero`` without ever calling ``fn``.
* ``filter(predicate, xs)``: Returns a list composed of those elements from ``fn`` such that ``predicate(fn)``.
* ``sum(xs)``: add all the numbers in the given list and return their sum, or zero if the list is empty.
* ``take(n, xs)``: return a list composed of the first ``n`` elements of ``xs``.
* ``drop(n, xs)``: return the remainder of list ``xs`` after skipping the first ``n`` elements.
* Python's math library of functions and constants are also installed, with two caveats:
  * ``log`` becomes two functions: ``log(x)`` and ``log_base(x, b)`` because Sophie does not deal in optional arguments.
  * ``hypot`` is re-implemented in Sophie because the python version takes a variable number of arguments, which is currently too hard to deal with more directly.

If you'd like to see how that's all been done,
you can find the standard preamble `here <https://github.com/kjosib/sophie/blob/main/sophie/preamble.py>`_.
