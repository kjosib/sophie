Plugging Sophie into the World
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

Because Sophie has a nontrivial type-system, it's necessary to somewhere declare the Sophie-types
of each foreign symbol. At the same time, we might specify how to bring the corresponding (foreign)
definitions into the run-time. This approach bears a vague resemblance to the Java Native Interface.

Approach
~~~~~~~~

Phase One: Pure Functionality
--------------------------------

My first goal was to support arbitrary constants and functions.
To that end, one new keyword ``foreign`` and a few new production-rules in the grammar
were enough to let Sophie say what needs to be said.

The changes to Sophie's implementation were roughly:

* ``syntax.py`` got some new AST node-types.
* ``class Module`` filters imports into Sophie-imports and foreign-imports.
* In the name-resolution machinery, ``class WordDefiner`` does the magic to import Python objects
  and install them as global Sophie symbol definitions. Other passes in the same file handle ancillary details.
* ``type_evaluator.py`` and ``simple_evaluator.py`` both got minor updates to deal with foreign symbols.

This enabled a quantum leap in what Sophie could do.

Phase Two: Native "Actors"
---------------------------

.. epigraph::

    All the world's a stage,
    And all the men and women merely Players.

This part's going to be a bit more step-by-step. (There's a conceptual pun in there somewhere...)

The plan is to use native (Python) objects to stand in for the kind of system services that,
in other languages, might result in an IO monad or an algebraic effect system.
So that means I need to be able to import both single objects and also constructors.

* The present goal is to import a console driver as a native actor.

By this point, the mechanics of *importing a thing* are well-established.
The new challenge is explaining how Sophie should treat the imported thing.
So this is partly an exercise in tweaking the type system to respect actor-ness.

There is an ``opaque`` type keyword, but it is not appropriate.
Opaque types are types you can't do *anything* to except pass them to functions that accept them natively.
But there's one *more* thing you can do with an actor, which is to send messages to it.

I believe messages should be as well-typed as function-calls.
But at this point, perfection is the enemy of progress.

* It's time for a shortcut!

One thing's clear: I'll end up with at least one more keyword to introduce actor-definitions.
I might just as well proactively commandeer that keyword for use with the imported native actors.
And I suppose that keyword must be ``actor``.

Let me adjust Sophie's grammar to allow ``actor`` in a type-expression.
Eventually I'll want to specify that actor's interface somehow,
but remember that shortcut I mentioned? Now I know what the shortcut needs to be!

The short-run get-something-going version of this will not bother to type-check actor interactions.
Actors are still under development. Let it crash! It's only Python underneath. It won't reformat your water heater.

* What have I procrastinated?

I haven't yet decided how I want to type-check actors.
Messages are a straightforward extension of functions,
but generally when you take an actor as a parameter you're planning to send it some set of messages.
Probably there will be something called an ``interface`` but that could go in 20 directions.

* This section will move once I make some decisions.
* What if interfaces were also be name-spaces?

Known Problems
~~~~~~~~~~~~~~~~~~~~~~~

Sophie does not have exceptions. If a foreign function throws one, Sophie will quit unceremoniously.
Sophie will surely soon get a `result-type similar to Rust's <https://doc.rust-lang.org/std/result/>`_
along with some handy connectors, but no single strategy is suitable to translate all exceptions from foreign code.
Binding to an exception-laden API must involve some amount of wrapper-code to deal with the semantic mismatch.

Python's ability to find a Python module depends on its module path, which Sophie code doesn't have any control over.
Obviously built-in and standard-library modules are no problem, but random extra Python code could get weird.
Maybe Sophie's Python implementation adds a way to get Python code from relative to a Sophie module?

If Sophie grows up, we might need syntax for connecting to .dll files, a Java classpath,
or whatever else. Perhaps there will be a namespace of different linkage semantics?
Sophie's module/import system is still nascent, so a lot could still change.


