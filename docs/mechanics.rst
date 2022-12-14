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

Delaying the Semantic Checks
.............................

Should the loader delay name resolution and type-checking until after all modules are parsed?
Some people might prioritize knowledge of problems with the import-graph over other issues.
Also, such a change could interact with an object-code cache.

Tree-Walking Evaluation with Modules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The original simple evaluator could work given only a (main/only) module-object.
Once module-qualified references enter the picture,
it seems to need the complete set of loaded modules.
Things get even weirder with specific imported names.

How to resolve a reference dynamically
--------------------------------------

The original (simplistic) way
..............................
The original evaluator used a chain-of-dictionaries to represent the dynamic environment.
Every name-lookup was just a probe into this structure.
That had two important consequences:

First, each time it applied a user-defined function,
it had to eagerly create ``class Closure(Procedure)`` objects for all possible sub-function
calls to guarantee that look-up would succeed, and in the right place,
for expressions within that scope. (This also took care of static-linkage.)

Second, it had to fill an outer dynamic environment with thunks for module-level globals.
Even outside that, it filled another environment from built-in and preamble elements.

The chain-of-dictionaries worked, but it didn't play well with the idea of inter-module references.
At least, not by itself. Also, all that searching seems inefficient.

A bit smarter way
..................
If a name refers to a (lazy) parameter or local sub-procedure,
then the dynamic meaning of that name refers to a thunk bound to an enclosing activation record.
The original interpreter used a hack: Assuming all scopes nest perfectly,
it could construct (dynamic-style) thunks once for global names into an outermost dynamic environment.
Then during evaluation, all names are simply look-ups into the current dynamic environment.

There is already a static definition associated with every reference:
Class ``WordDefiner`` creates the static-scope symbol table(s),
and class ``WordResolver`` associates definitions accordingly to each and every reference.
In principle, the evaluator could use a different strategy depending on
whether the name *statically* refers to a parameter, a sub-function, a global function,
a data constructor, or indeed even a native-function binding.

Although parameters, functions, and data-constructors are easily distinguished syntax objects,
the situation *within* the realm of functions is a bit more complicated.
Syntax alone does not distinguish global functions (which close over nothing)
from nested functions (which close over the *current* dynamic scope) or "uncles"
which close over some outer dynamic scope -- findable only by traversing static links.

There is a straightforward *partial* solution to this smaller problem:
Decorate each function-definition with its numeric nesting level,
each parameter-definition with the level corresponding to (the inside of) its owning function,
and finally each name-reference to the nesting level at which it actually appears.
Then, to resolve a (non-global) name dynamically,
simply walk back the indicated number of static-pointers to find the correct dynamic environment.

.. note::
    Once it's clear which activation record is the proper host for each name,
    there is no more need for search and so closures can be built only at need.
    This might mean a simpler (and maybe faster) evaluator.

The last bit of the puzzle is this:
Inter-module references are all to global objects.
Global objects do not need a static link.
(Or rather, their thunks can have a null static link.)
The evaluator does not specifically need to know which module a global lives in,
so long as it finds globals directly by their definition link.

Dealing Well with Global References
....................................

The evaluator builds different kinds of run-time proxies for
data constructors, user-defined functions, and native functions.
These provide for a nice consistent internal API,
so they're still important even in a module-aware system.
Thus, it still needs a notion of global scope.

Do we store the proxies:
    1. Attached as an attribute to global-object definitions?
       This certainly works for user-defined things, but might be iffy with native functions.
       It has the somewhat icky property of "monkey-patching" objects defined elsewhere,
       which seems like a terrible habit.
    2. In a separate global dictionary?
       This is no friend to embedded interpreters running concurrently,
       but it's fine for a stand-alone scenario.
    3. In a global dictionary passed around with the local environment?
       This seems to add lots of overhead.
    4. In an outermost static scope?
       This seems like a slower option.

Do we build the proxies in advance or as needed?
    As-needed adds an avoidable test for every call.
    In-advance means needing to know the complete set of modules up front.

The decisions currently are:
    * Use a global dictionary, keyed for now to the corresponding definition-object.
    * Prepare in advance.

This will mean changing function ``run_module`` but it's only used in a few places.
It can take the list of loaded modules in topological order straight from a ``Loader`` object.
