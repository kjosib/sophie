Resolving Imports
~~~~~~~~~~~~~~~~~~~~

Up-front design for the algorithm to resolve imports,
and for the ways in which it might reasonably be expanded later.
This is probably a pretty common approach, but it's worth repeating here.

.. contents::
    :local:
    :depth: 2

Simple Recursive Import Algorithm
---------------------------------------

A runtime must contain:

* a dictionary of prepared modules,
* a stack of modules under construction, and
* a list representing the set-up and shut-down order of modules.

A procedure *need(absolute base-path, URI to the desired module)* does this:

* Based on the module URI, figure out how to load the module.
* Based on the loader and the base-path, figure a distinctive *key* for the desired module.
  The *key* must work like an absolute path and make sense to a Sophie-programmer.
* If the *key*:

  * is in the *prepared-modules* dictionary, return the found module-object as-is.
  * is on the *under-construction* stack,
    declare an import-loop (from top-of-stack to the occurrence of this path) and fail.
* Otherwise: Put the *key* on the top of the stack.
* Actually load the module:

  * Assuming it's a normal file, if it:

    * doesn't exist, declare that and fail.
    * doesn't load, declare that and fail.
    * doesn't parse, declare that and fail.
  * Apply all of the target-module's own needs, recursively (or fail on failure).
  * If the module under construction:

    * doesn't resolve, declare that and fail.
    * doesn't type (and we're in type-checking mode), register a failure.
* Remove the entry from the *under-construction* stack.
* Enter the module-object into the *prepared-modules* dictionary.
* Schedule the module for set-up (and perhaps eventually, take-down) activities.
* Return the newly-constructed module-object to the caller.

In a sense, this is just transitive-closure.
But there are important bits of information to string up along the way.

Ancillary Procedures
---------------------

To "Apply all of the target-module's own needs" is *almost* a straightforward
loop through that module's list of *import* syntax-objects.
The caveat is that a failed ``need`` fails the loop in a way the caller can recognize.
Presumably that failure resulted in a suitable error report,
so it's unnecessary to recapitulate the cause of failure,
but it's probably worth noting the location of the failure.

To kick this whole process off, the main entry-point can simply ``need`` whatever module is on the command line.
If that fails, then presumably the appropriate error reports are scheduled.
Otherwise, it can proceed to run the activity schedule.

A Rudimentary Package System
------------------------------

The algorithm above implicitly relies on a filesystem-like API.
It presumes to use absolute paths as keys, to deal suitably with relative paths,
and to read the contents of a file given a path.

Sophie now supports a rudimentary notion of "package". You can do something like::

    import:
        sys."turtle" as t;

The ``sys.`` here means to look in the package called ``sys`` for the file ``"turtle.sg"``.
(The ``.sg`` extension is implied.)
This provides a natural way to tie into both a "standard-library" notion and more general configuration-management.
Something somewhere must map package symbols back to filesystem paths.
Then we can again rely on the *absolute-path* thing.

For the moment, there is only the one package called ``sys``.
Code in ``modularity.py`` wires it up to a sub-folder relative to the location of that file.
It's crude but effective at meaning I can in principle run Sophie code from anywhere in the filesystem
and yet retain access to import shared doodads.

Bringing this to the next level must involve some concept of *installing* the Sophie ecosystem.
As long as Sophie remains but a disconnected Python program,
that notion may be a pre-equine renaissance natural philosopher:
Descartes before the horse.

Avenues for Extension
-----------------------

Object-Code Cache
...................

In any case, this doesn't make any sense until there's a notion of bytecode at least.

The sub-procedure called "Actually load the module" would obviously be affected.
But there is something else: Object-code might presume things about the dependencies.
Some sort of cache freshness-test is important both for cached object-code and its dependencies.
Then, a caching loader would need to make sure the dependencies are as-expected before yielding from the cache.
This would mean the return-value from ``need`` would have to contain a suitable input to that freshness test.
That could be a cryptographic hash of the module's source text.

Delaying the Semantic Checks
.............................

Should the loader delay name resolution and type-checking until after all modules are parsed?
Some people might prioritize knowledge of problems with the import-graph over other issues.
Also, such a change could interact with an object-code cache.
