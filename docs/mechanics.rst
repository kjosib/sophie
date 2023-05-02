Mechanics of Sophie
====================

This chapter contains notes on the design of nontrivial subsystems in the implementation.
I'll add notes as they seem necessary while the overall system fills out.

.. contents::
    :local:
    :depth: 2

Representing an AST Efficiently
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is a technical note on something I may end up implementing.

I ran across an article that rebooted my thinking on syntax-tree representation.
I probably won't place too high a priority on this in the short run,
but who knows? That day may come.

    TL;DR:
        Dr. Sampson's article_ explained a special case of arena-allocation that improved the
        space and time performance in tree operations. He gave a rationale roughly as follows.

        * A 32-bit index is half the size of a 64-bit pointer on modern architectures. Textbook-style syntax-trees are heavy on pointers.
        * Packed-array structures require less overhead in the memory allocation subsystem than allocating each node separately.
        * Packed structures have excellent locality-of-reference, which is favorable to a modern CPU cache.
        * Nodes are allocated later than their children: He evaluates expressions by processing the array left-to-right, with a parallel array of values.
        * *Hey, doesn't this vaguely resemble bytecode?*

.. _article: https://www.cs.cornell.edu/~asampson/blog/flattening.html

I began to think about some further implications. And that's when I realised:

**We don't even need the index links!**

* The array of "operators" (i.e. node-types) alone constitutes a Reverse-Polish Notation (RPN) expression.
  If you process the array strictly left-to-right, and you know how many children each type of node has,
  then you can run any bottom-up pass you like, with roughly logarithmic extra storage,
  simply by maintaining a stack of child-nodes and referring to the operator-table as you go.
* LR parsing is almost exactly this: You can think of it as filtering out the uninteresting tokens from scanner,
  and then inserting the parse-rules where they go from that stream to make an RPN expression of the AST.
  It's just that in a traditional parser, the RPN never exists per-se: instead, it's "executed" immediately
  in the form of parse-actions.
* In general, these separate arrays make it easy to allocate *uncoupled* space for different compiler activities.
  It would be much less convenient if all the pass-specific data were attached to the AST nodes directly.
* The same array processed right-to-left is effectively a top-down walk.
  A stack with counters can track where the parents were, so information can trickle down this way.
* Some operators (e.g. literal values, identifiers) will refer to ancillary information.
  These can fit in a parallel list: Just keep a cursor for this and advance it as appropriate.

Not everything fits in a neat little box yet.
Some of Sophie's parse-actions re-arrange their subtrees slightly.
I'm sure re-writes are feasible, but I'll need to revisit the problem.

High-Order Type Checking (HOT)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note:: This feature is under development, so the precise details may change.

> And at one point while working on the type checker, I had the provenance epiphany.
> The objects we pass around to represent types should include both the
> type per-se (i.e. calculus.SophieType) and also the provenance,
> or why the computer judged a particular type. Provenance can be
> nontrivial -- maybe even recursive -- but traces a path of reasoning.

I would like a rather precise up-front analysis phase based on what we can infer about the types of variables,
but I do not mean to impose burdens normally associated with *dependent-type* systems.

In concept, my approach is to just run the program as-is, but in the realm of types rather than values.
This is a whole-program approach to the question type-correctness:
The same function might be safe-or-not depending on how you call it.

Type Numbering
---------------------
Types can be nontrivial recursive objects.
We need a quick way to tell if we're looking at two instances of the same type.
Something akin to value-numbering will do nicely.
For the Python implementation, I'll use the booze-tools ``EquivalenceClassifier``
and make ``SophieType`` objects define ``__hash__`` and ``__eq__`` suitably.

Dynamic Type Dependency Front
------------------------------
Formally, this is the set of parameters upon which a function's type may depend.
We want that so that the evaluator can *properly* memoize the results of its type computations.

Naively this would be the set of all parameters that the function's body mentions.
However, that's not quite right:
If function A calls function B, and function B mentions parameter P (or match-subject id) not its own,
then the type of P influences the type of B which in turn influences the type of A.

This is another data-flow problem. Start by associating all the non-local data dependencies,
then flow these through that partial call-graph consisting of calls to non-global functions.

Finally, add the local variable dependencies specifically if they are mentioned.
(This is because a function ``(a,b)->b`` does not depend on the type of ``a``.)

The type-dependency front will inform the memoization layer.

Evaluate the Type-Program
---------------------------
The structure of ``sophie.hot.type_evaluator`` should bear a striking resemblance to that of ``sophie.simple_evaluator``.
However, I intend some different semantics. The type-evaluator can use memoization with eager/strict evaluation.
It will also need a way to detect recursion, and a sensible theory of how to close such loops.

    The usual approach is a *mu*-type, but that's only relevant if I bother with the optional simplification feature.

On entry to a function, I take note of the fact it's been entered with these (type-)arguments.
Using a scheme like value-numbering (but applied to types) it's easy to notice a recursive call.

Dealing with Recursion
.......................

Having reached a recursive call, there is a least-fixpoint problem.
One idea is as follows:

At first, hypothesize that the function returns *nothing.*
Not a *maybe-monad* style ``nothing``, for that would be *something.*
I mean more like a *Never-Ending Story* kind of nothing.
(See the film with your kids, if you haven't already done.)

In the land of type theory, the *nothing* has a type and that type is called "Bottom".
Note in particular the following algebraic **laws of Bottom:**

1. Bottom is a universal *subtype:* ``union(X, Bottom) => X``.
2. Bottom is a universal *intersection:* ``Bottom.foo => Bottom``.
3. Bottom is a universal *argument:* ``(A->B)(Bottom) => B``.
4. Bottom is a universal *function:* ``Bottom(foo) => Bottom``.

    Each of these laws also corresponds to a constraint about a particular bottom-typed value.
    It's *mostly* pointless to chase that rabbit. Rather than, for example, discerning
    that *X* must be a record (or a function, respectively), we can rely on the type-evaluator
    to get around to that point with a specific *X* type.

At the end of this preliminary round of inference,
we have a sensible lower-bound return-type for the function *as it was actually called.*

If that preliminary lower-bound is *Bottom*, then the function's induction lacks a base-case,
which is an error. Otherwise:

* Put this lower-bound return-type in the cache line for this type-context.
* Mark the entry as *provisional*.
* Later, work to solve the provisions.

Solving Provisional Types
..........................

Any expression whose type depends on a provisional type is itself provisionally-typed.
In fact, the provisionality of types forms a directed dependency graph.
To handle this on the level of individual expressions might be too much detail,
but we can create a provisionality graph between function result-type cache entries.

With that graph, we can work in SCC order to finalize the types of functions.

Take a leaf-cycle in this graph: Some function's type depends upon itself, or there's a mutual dependency.
Make progress by running the basic algorithm on that cycle.
If all the result-types *and provisions* stay the same, and restricted to the SCC,
then that SCC has reached its least-fixpoint, so drop all provisions pointing at its members.

Implementation Phases
----------------------

1. Tag what's out there as a release.
2. Turn off the existing type inference engine.
3. Interpret the run-time semantics of nontrivial type-case expressions.
4. ???
5. Profit!

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
