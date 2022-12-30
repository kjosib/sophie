Mechanics of Sophie
====================

This chapter contains notes on the design of nontrivial subsystems in the implementation.
I'll add notes as they seem necessary while the overall system fills out.

.. contents::
    :local:
    :depth: 2

Resolving Imports
~~~~~~~~~~~~~~~~~~~~

Up-front design for the algorithm to resolve imports,
and for the ways in which it might reasonably be expanded later.
This is probably a pretty common approach, but it's worth repeating here.

Algorithm One: Simple Recursive Import
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

Avenues for Extension
-----------------------

URI-Like Paths
...............

The algorithm above implicitly relies on a filesystem-like API.
It presumes to use absolute paths as keys, to deal suitably with relative paths,
and to read the contents of a file given a path.
Let's replace all that with a composite driver.
Suppose Sophie interprets the "path" component as similar to a URI.
The URI-schema provides a natural and extensible way to tie into
both a "standard-library" notion and more general configuration-management.

A first iteration of the "URI-paths" idea would *mostly* be about configuring
the location(s) of installed libraries. That's a minor design problem.
The main idea is to use the schema in the sub-procedure "Figure out how to load the module".

Native Modules
...............

Right now the primitive-root namespace gets a bunch of math functions.
It would be nice to allow more "foreign" import modules.
Some general facility to marshal and unmarshal data may one day come out of this,
but in the meanwhile it seems the natural path to embrace existing ecosystems.

The natural approach here (for now) is to add a schema-driver that imports Python modules instead,
and maybe calls some expected module-attribute to make it prepare itself as a namespace.
Details of precisely what objects to put in that namespace are left for later.

Un-Bundling The Turtle
..............................

Presently, the run-time looks at the type of an object to decide how to interpret its contents.
For example, if it sees a list, then it tries to manifest and print that entire list.
If it sees a ``drawing`` record, then it does the turtle-graphics thing.
I'd like to have a scenario in which (at least) system-level modules can install drivers.
Considering also that native modules might need to interact with the laziness inherent in the system,
there could be some challenges in the modular structure of the overall Sophie interpreter.
But I think it will work out.

Object-Code Cache
...................

In any case, this doesn't make any sense until there's a notion of bytecode at least.

The sub-procedure called "Actually load the module" would obviously be affected.
But there is something else: Object-code might presume things about the dependencies.
Some sort of cache freshness-test is important both for cached object-code and its dependencies.
Then, a caching loader would need to make sure the dependencies are as-expected before yielding from the cache.
This would mean the return-value from ``need`` would have to contain a suitable input to that freshness test.
That could be a cryptographic hash of the module's source text.
