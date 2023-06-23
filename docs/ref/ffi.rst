The Foreign Function Interface
===============================

.. contents::
    :local:
    :depth: 2

Importing Foreign Code
~~~~~~~~~~~~~~~~~~~~~~~

In the ``import:`` section of a Sophie module, include a foreign import declaration.
The following example is taken from the standard preamble::

    import:

    foreign "math" where

        e, inf, nan, pi, tau : number;

        acos, acosh, asin, asinh, atan, atanh,
        # ... bunch of more functions... #
        tan, tanh, trunc, ulp : (number) -> number;

        isfinite, isinf, isnan : (number) -> flag;

        atan2, comb, copysign, dist, fmod, ldexp, log_base@"log",
        nextafter, perm, pow, remainder : (number, number) -> number;

    end;

A foreign import declaration contains:

* The keyword ``foreign``.
* A literal string (like ``"math"``) that locates the foreign code. (Presently this means a Python module-path.)
* Optionally, an *initializer*. More about that later.
* And then usually:

  * The keyword ``where``.
  * One or more *foreign-import groups,* ending in a semicolon.
  * The keyword ``end``.
* and finally, a semicolon.

A foreign-import group consists of:

* A comma-separated list of names (but see note),
* A colon,
* A *simple* type annotation: named-types (including those defined in the same module) and function-types are fair game.
* The semicolon at the end.

.. note::
    Occasionally a foreign-symbol's true name will differ from how you want to call it from Sophie.
    This example mentions ``log_base@"log"``, which means that the Python symbol is ``log`` but
    we want to use the name ``log_base`` in Sophie code for this instance of the import.
    In this case, the feature allows Sophie to expose the same underlying bit of Python
    with two different signatures. Python's ``math.log`` takes an optional argument for the
    base of the logarithm (defaulting to ``e``), but Sophie functions do not play that game.

Calling Conventions
~~~~~~~~~~~~~~~~~~~

Initializing a foreign (Python) module
---------------------------------------

The Basics
.............

A foreign import-module can supply an initialization function called ``sophie_init``.
This is how you might write that::

    import:
    foreign "something.something.something" () where
        ...
        ...
    end;

Note the empty pair of parenthesis after the foreign (Python) module-name.
If these are present, the **Sophie** runtime will attempt to call an initialization function
in the ``something.something.something`` module.
The name of that function is always ``sophie_init``.
``sophie_init`` will receive, as first argument,
a forcing function which turns thunks into normal values but returns all other values as-is.

Exporting **Sophie** symbols to the foreign module
....................................................

The foreign import-declaration can specify Sophie objects to pass in to said function, like so::

    import:
    foreign "sophie.adapters.turtle_adapter" (nil) ;

Note the parentheical ``(nil)`` here.

You can supply any comma-separated list of identifiers here.
These can refer to any name that would be visible to the ``begin:`` section.
In this case, the ``sophie.adapters.turtle_adapter`` module's ``sophie_init`` function will receive,
as second and subsequent arguments, a reference to the run-time representation of the corresponding symbols.

.. note::
    It may be handy to pass in ``nil`` if your Python functions will do much with Sophie lists.
    ``nil`` is a variant-case which takes no arguments, and therefore it is guaranteed to be a singleton object.
    Using an ``is`` test on the Python side is probably slightly faster than inspecting ``nil``'s subtype-tag.


Sophie calls a foreign function
---------------------------------

Foreign functions are assumed to have strict (not lazy) semantics directly at the level of their parameters:
They get passed evaluated values (not thunks) as arguments.
This is fine for commandeering the pure functions from an existing ecosystem like Python.
However, if the arguments are record-types, then the fields within likely contain thunks.
If you need to force those thunks, recall that ``force`` argument to the initializer.
Maybe stash a reference as a module-global variable.

Python calls back into Sophie code
-----------------------------------

On the Python side, a **Sophie** function appears as an object with an ``.apply(...)`` method.
You can call that method with ordinary Python values as arguments, and the Sophie run-time will do the rest.
What you get back may need ``force``-ing. *Perhaps it ought not. But that's a deep subtlety I have not pondered sufficiently.*

.. caution::
    Although **Sophie**'s evaluator is re-entrant,
    nothing stops you from running out of stack space (recursion depth) on the Python side.

Providing Interaction (I/O Drivers)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The result of a Python module's ``sophie_init`` function can specify linkages to I/O drivers.

For each expression in the ``begin:`` section,
the run-time looks at the type of an object to decide how to interpret its contents.
The ``sophie_init`` function in ``sophie.adapters.turtle_adapter`` binds a little
something to the to ``drawing`` type::

    def sophie_init(force, nil):
        ... # save nil for later # ...
        return {'drawing':do_turtle_graphics}

These driver-functions generally need to interact with the laziness inherent in the system.
Continuing the turtle-graphics example, the driver's prototype is::

    def do_turtle_graphics(force, drawing):
        ...

The text of ``do_turtle_graphics`` can call ``force`` on a Sophie-object to get
a strict-object. Now if that strict-object happens to be a record-like thing,
then its fields may also be lazy / thunks, and so ``do_turtle_graphics`` is
responsible to call ``force`` responsibly.

*One last thing:* I've passed Sophie's ``nil`` into the turtle driver's initializer
because I know it will be a singleton object and I can thus use an ``is`` test
in Python to detect the thing. That may make list-processing loops a hair faster.

