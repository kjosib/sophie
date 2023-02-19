The Foreign Function Interface
===============================

.. contents::
    :local:
    :depth: 2

Background
~~~~~~~~~~

Sophie's core language is Turing-complete, but Sophie needs a way to plug into a larger ecosystem
and invoke code from in other languages. We call that ability a *Foreign Function Interface (FFI)*.

It also happens that an *FFI* is also a fine way to add functions to the present interpreter
for working with built-in data types. In particular, math and string processing functions
are best delegated this way. Later, the *FFI* can also provide for vector processing and
connect to interaction facilities.

Sophie provides for a particular universe of types. Anything imported from foreign lands
would need a proper introduction (complete manifest type signatures) so that other Sophie
code can use it correctly.

This facility will not spring into existence fully-formed like Venus arising from the sea foam.
It's best to take one step at a time. Right now, this section of the roadmap appears to include:

* Functions (and constant values)
* Opaque Data Types (i.e. those provided by foreign code)
* Input and Output Drivers (e.g. the turtle-graphics facility)

Because Sophie has a nontrivial type-system, it's necessary to somewhere declare the Sophie-types
of each foreign symbol. At the same time, we might specify how to bring the corresponding (foreign)
definitions into the run-time. This approach bears a vague resemblance to the Java Native Interface.

One new keyword ``foreign`` and a few new production-rules in the grammar should be enough for the Sophie side.

Recipe / How-To
~~~~~~~~~~~~~~~~~~~~~~~

In the ``import:`` section of a Sophie module, include a foreign import declaration.
The following example is taken from the standard preamble::

    import:

    foreign "math" where

        e, inf, nan, pi, tau : number;

        acos, acosh, asin, asinh, atan, atanh,
        ceil, cos, cosh, degrees, erf, erfc, exp, expm1,
        fabs, factorial, floor, gamma, gcd,
        isqrt, lcm, lgamma, log, log10, log1p, log2,
        modf, radians, sin, sinh, sqrt,
        tan, tanh, trunc, ulp : (number) -> number;

        isfinite, isinf, isnan : (number) -> flag;

        atan2, comb, copysign, dist, fmod, ldexp, log_base@"log",
        nextafter, perm, pow, remainder : (number, number) -> number;

    end;

A foreign import declaration contains:

* The keyword ``foreign``.
* A literal string (like ``"math"``) that locates the foreign code. (Presently this means a Python module-path.)
* The keyword ``where``.
* One or more *foreign-import groups,* ending in a semicolon.
* The keyword ``end``, followed by a semicolon.

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

Known Problems
~~~~~~~~~~~~~~~~~~~~~~~

Sophie does not have exceptions. If a foreign function throws one, Sophie will quit unceremoniously.
Sophie will surely soon get a `result-type similar to Rust's <https://doc.rust-lang.org/std/result/>`_
along with some handy connectors, but no single strategy is suitable to translate all exceptions from foreign code.
Binding to an exception-laden API must involve some amount of wrapper-code to deal with the semantic mismatch.

For the moment, all "foreign" functions are assumed to have strict (not lazy) semantics:
They get passed evaluated values (not thunks) as arguments.
This is fine for commandeering the pure functions from an existing ecosystem like Python.
However, if the arguments are record-types, then the fields within may contain thunks.
The current FFI does not define how foreign code might force a thunk.
It's unclear how best to address that, but it will need a solution in time.

Python's ability to find a Python module depends on its module path, which Sophie code doesn't have any control over.
Obviously built-in and standard-library modules are no problem, but random extra Python code could get weird.
Maybe Sophie's Python implementation adds a way to get Python code from relative to a Sophie module?

If Sophie grows up, we might need syntax for connecting to .dll files, a Java classpath,
or whatever else. Perhaps there will be a namespace of different linkage semantics?
Sophie's module/import system is still nascent, so a lot could still change.
