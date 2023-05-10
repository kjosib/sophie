Complete Speculation
=====================

This chapter is a stream-of-consciousness about uncertain design questions.

.. contents::
    :local:
    :depth: 2

Package System
~~~~~~~~~~~~~~~~~~

Inherently, a language is going to have several sources of "batteries" that it might include or support.
These include standard libraries, system-internal/reflective things,
bits you downloaded, bits you share between projects, and various other administrative divisions.

I don't want to have to embed absolute paths in an import section.
So instead, suppose import-paths are implicitly composed of a domain and a path,
split by a colon. Suppose that two domains are predefined: ``std`` and ``sys``.
Along with that, maybe the installation configuration allows to define a few more, like ``site`` and ``contrib``.
But suppose further we define a convenient way to do this on a per-project basis.

It can be as simple as a set of *name=value* pairs in a ``Sophie.ini`` file in the root folder of a project.

Now, if you wanted to import your modules from something not-exactly the filesystem,
that's fine. You'd just need to define a way to interpret those *value* components,
and plug that into the import mechanism, or replace the importer altogether.
That's not something a typical end-user would do, but it could solve some enterprisey thing.

Input and the Process Abstraction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
One view of a process is a function which must wait for an input event before computing anything.
Specifically, it computes its own next state (i.e. subsequent behavior-function) and any outputs.

Independent of any concurrency model, I can explore what types might be involved using a simplified model.
So, let's consider what would be involved in a simple text-based game.
Quite likely the simplest would be "guess-the-number" style game in which the human player picks a number
and the computer makes "guesses" following a binary-search strategy.


Holes in the Code
~~~~~~~~~~~~~~~~~~

Suppose that ``??`` can stand in for an expression or type annotation without blocking the parser.
Treat it like a bit of the program that's yet to be decided.
It could get as far as the type-checker and maybe yield suggestions for things that might go there.
It's better than an unbound name because it's clearly not misspelled.

Suppose (in some mode) we speculatively interpret the code until it hits a hole,
and then drop into a monitor which summarizes the context both static and dynamic.
It's no good in production, but it's fine for research and general poking around.

Suppose this "monitor" continues automatically, using the "holey" result with defined propagation rules.
One could imagine seeing not just what *creates* the hole, but also what *consumes* it,
which could be valuable for understanding a system.

Dimensions and Units of Measure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

I'd someday like Sophie to track dimension and units, so that we don't accidentally add apples and oranges.
Presumably, type-objects would drag along some additional bits of information.
How shall that extra information interlock with arithmetic?
What about user-defined functions?

The normal approach is to have some sort of guard-syntax that makes and breaks the encapsulation around a ``newtype``.
However, I'd also like to see normal arithmetic work on encapsulated quantities without *too* much extra effort.

Nine times in ten, the *vector space* interpretation of add/subtract/scalar-multiply is fine.
Outside that, the benefits of dimension-checking seem to require explicit annotation.

I have no clear picture in mind for any of this.

Alternate Rings/Fields/Etc.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Allegedly, C++ got operator overloading so that complex-number arithmetic would look nice.
And of course it's nice to be able to support complex numbers nicely.
But what about matrices? Quaternions? Octonions? Arbitrary vectors?

It sounds nice for the arithmetic operators to work naturally for structured values,
but it's hard to define what "naturally" means.
General operator-overloading requires a number of decisions I'd rather put off.

Interfaces / Type-Classes
~~~~~~~~~~~~~~~~~~~~~~~~~~

Sooner or later, the generic-programming bug will bite.
The Haskell approach seems to be that a given identifier is tied to a particular interface.
For example, ``==`` always means the arguments are in (the same instance of) the ``Eq`` class, not any peer.

At this point, it's too soon to worry about this. The type-checker doesn't even grok onions yet.

Longer-term, I have my reservations.
Lots of things have interesting mathematical structure and we should exploit that,
but I don't think you ought to have to spell your "group operator" the same for everything that,
if you squint hard enough, sort of looks like a group.
After all, it might look like a group in more than one way.
I'd rather build my high-order-functions in such a way that you pass in the component operators.
This way, you can use whichever group-like characteristic is relevant in the context.

Monads and Functors and Maps, Oh My!
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Simple rule: Keep it simple.**
You shouldn't need a degree in category theory to get full use of a powerful, expressive language.
(Although it might not hurt.)
This means eventually I'll want to solve certain problems.

Partial Functions
------------------

Probably the grammar will look like a function-call but with a slash before the closing parenthesis.
That makes it clear what's going on exactly and where, while still catching broken call-sites in meaningful ways.

Starmap
---------

I want to be able to express lock-step parallel decomposition and recomposition of different kinds of recursive data structures,
possibly while accumulating something in the process.
The language should not constrain how many or what kind of structures are involved.

Haskell does make those constraints: it has for instance zip2 and zip3 and maybe a few more, but there's certainly no zip17.
I can't personally imagine the utility of a 17-argument zip, but that's quite beside the point.

This business of "lock-step parallel decomposition and recomposition" partly depends on the nature of the structure involved,
but also partly depends on the ability to express the relevant *tuple-of-arguments* forms.

Assuming a collection of lists, one can imagine filing off a tuple of heads to some plug-in function,
and accumulating the result as a new list. Now there's a question: What to do if the list sizes differ?
Classically the answer was to stop when any input did, but maybe that's not the only possibility.

I think there's room for some sort of telescoping operator that helps build lock-step parallel functions,
but I don't have a clear plan yet.

Error Context Displays
~~~~~~~~~~~~~~~~~~~~~~~

The bit that displays excerpts is presently too dumb:
It can possibly display the same line more than once,
and it repeats the file-name every time.
It ought to sort and group this information to present a nicer excerpt.
Also, some ansi color would be nice.
(Incidentally, what if input source contains terminal control codes?)

I stumbled on a nice Python library for this sort of thing,
but I forgot to write down the reference.

Concurrency
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

I'm sold on the virtues of the *actor-model* of concurrency roughly as Erlang exemplifies it.
However, Sophie will need a few adjustments to mix with pure-lazy-functional.

* The *spawn-process* operation is fundamentally a nondeterministic action with environmental side-effects.
  (It invents a different *PID* each time.) It cannot be a (pure) function, so it should not look like one.
  It's effectively an I/O operation in its own right. You cannot have a (pure) function which, when called,
  does something, because you do not get a concept of *when called* ~~ except in the case of actors.
  Actors have a (local) time-line, so the *syntax to construct an action* needs to support spawning.

* Sophie's current simplistic interpreter won't get preemption,
  but an event-driven model makes a decent *(and reproducible)* proxy for exploring language semantics.
  Later, we can *have nice things* if Sophie plays by the right rules.

I don't want to include any implicit meta-information along with the messages on channels.
If you need a time, accept a clock as part of an input. A behavior-function should have no way to tell
whether it's connected to real resources or test doubles.

The model is that a process receives one event at a time and handles that event before getting the next.
There is no such thing as "simultaneous" when more than one input channel is involved.
Message delivery is best-effort, and semantically call-by-copy.
(Referential transparency minimizes *physical* copying.)

This all suggests a run-time responsible for scheduling computation to ready processes.
It also suggests room for drivers or adapters suited to different operating-system services.

Sophie needs some sensible syntax for declaring, defining, spawning, and combining processes.
(They look a lot like functions from a distance, but the differences are in the details.)
A *tree-of-supervisors* concept may fall out of the *spawn* syntax and semantics.

Briefly (and with much waving of hands) an actor is approximately a function from *input-message* to *action*.
An *action* clearly includes the next state of the actor, which can either be *finished* or another actor.
An *action* also must be able to send messages.
It's nice if those messages are statically typed, but I anticipate corner-cases.

One approach to static-typed spawn is to make the spawn-operation

Arrays and Dictionaries
~~~~~~~~~~~~~~~~~~~~~~~~

These are the canonical not-referentially-transparent mutation-focused structures.
There are so-called "persistent" data structures which can achieve array-like or dictionary-like
behavior within a constant factor of amortized performance, but the constant is not small.

There's a nice side effect of the functional-process-abstraction:
You can have all the *internal* mutable state you like, so long as no references to it escape the process.
The trick is how to represent the update semantics.
The textbook example here is a *proper* quick-sort: in-place
Compound or abstracted updates seem to require something akin to borrow-checking.

Tail Calls?
~~~~~~~~~~~~~~

The simplistic tree-walking interpreter is not exactly clear about the fate of whatever
counts as a tail call in the lazy/by-need model of computation.
That's probably not important at this stage, but at some point it will be nice to
convert to an (abstract/virtual) instruction set with a simple stackless iterative interpreter.
When that day comes, it will be nice to also not make a mess of whatever counts as the stack.
The issue probably boils down to smartly managing thunks so they don't pile up in long chains,
but snap their pointers ASAP.

Unreliable Input Data e.g. JSON
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Simply put, I was not impressed with the ELM approach to JSON.
It felt like such a fight to wrap my head around their JSON combinator library.
There was no intuitive way to understand it, so it was hard to compose bits.

If the language has a generic ``result[x,y]`` type ( ``case: ok x; fail:y; esac;`` )
then we should compose with that for all the sorts of things where things go wrong.
Incidentally, different applications might want/need more or less detail about failures.
So an application should be able to provide and use its own *bind* operator
comfortably with ``result`` types.

Stronger Guarantees
~~~~~~~~~~~~~~~~~~~~~~

Right now, Sophie has a traditional H-M generic type inference engine with let-polymorphism.
I'm in the middle of adding row-polymorphism so that you can write functions that access fields generically.

Partial Evaluation
---------------------

Initially I thought to use true partial-evaluation:
Run the code on the types instead of the data.
It's quick, precise, and feasible for some scenarios, but it's a strange work-flow:
Partial evaluation works top-down rather than bottom-up (same as a normal evaluator),
so you often can't tell if a function is well-typed in the abstract.
You can only tell if the *application* of a function is well-typed in context.
So if something doesn't type out, the whole call stack is potentially to blame.

Anyway, I got stuck part-way through designing the partial-evaluator and shifted tactics.
In retrospect, that may have been a mistake.
To bound the scope of blame, use the type annotations on functions.
A call that is consistent with its annotations cannot be blamed.

Type-Like Traits and Gradual Formality
---------------------------------------

Dependent-types are normally explained as "computing in the domain of types",
using something composed of a (normal) type and a (normal) value.
Partial evaluation seems particularly well-suited to that model.
But why stop at the one trait implied by the usual notion of dependent types?
And furthermore, why clutter a low-risk program with a mess of formal assurance?
Even if you stripped all the types out of a correct program,
it would still be correct. Let the circumstances dictate how much care
you want the compiler to take, and about which properties.

Let's suppose you want to prove your program never adds apples and oranges.
Plug in an evaluation rule that computes and checks a fruity trait on the arguments to addition.
This suggests some sort of interface or protocol by which a generic partial-evaluator framework
might call upon a trait-evaluator for help assessing the validity of some interesting property.

Any logical sub-framework will need a set of *because I said so* axioms.
In traditional type-systems, these are things like the types of primitive lexemes and platform built-ins.
The goal is to keep to a small, manageable number of manifestly-obvious axioms and inference rules.
These axioms and rules could be written as ordinary Sophie modules.
Turtles all the way down? Not entirely. Of course those modules would need their own verification,
but that's normally a much smaller problem. Eventually you have to run out of paranoia-fuel.

The call-side of the protocol would presumably resemble a visitor/strategy pattern walking an AST.
The response-side would need to reflect progress, potentially-incomplete information derived,
and the sudden relevance of unsolved variables.
The context for this would presumably contain information about everything in scope for any given call-out.

Model Checking and (randomized) Property Testing
------------------------------------------------------

These two ideas have a lot in common.

Property-based testing randomly generates screwy sequences API calls to search for minimal sequences
that violate a set of given pre- and post-conditions.
Assuming your API does not *actually* launch ze missiles while under test, this is a pretty good way to find mistakes.
Especially where there's a separate specification of how the API is meant to behave,
this also makes for a good way to divide efforts between build and test.

With model-checking, first you go and learn what properties a system ought to have,
then you cast these in terms of formal statements about a model, and finally you let a tool
search for scenarios (i.e. instances of the model) which are *possible* given the defined transactions
but *impermissible* given the check-constraints.
When it does, you clear up design mistakes before ever even looking at production code.
(Technically the model constraints are themselves a form of code, but vastly smaller than the real-life system.)

Both techniques amount to a search for ways to violate declared constraints.
On the surface, they also seem to benefit from something like reflection and run-time/dynamic types.
Yet Sophie deliberately eschews these, at least for now.
Can a language like Sophie plug into this?
The answer may change Sophie.

Integrated Development
~~~~~~~~~~~~~~~~~~~~~~~~

Sophie's surface syntax was designed with *code in notepad* in mind.
Adding syntax highlights in Notepad++, for example, might be a fun adjunct project.

Deep integration with VSCode would require constructing a language server.
That could be nice project in itself. One thing of consequence:
it pretty much requires a nontrivial approach to parse-error recovery.

.. note::
    I don't want to clutter the grammar reference with recovery heuristics.
    I have something else in mind. This fact alone may motivate me to write a new parse-engine
    based on the same tables. That could eventually feed back upstream.

Finally, Sophie's syntax was originally designed to make it easy to host code in a database
rather than files: there was a forest of functions each with a single body-expression.
*A certain uncomfortable compromise with the type system presently undermines that conceptual purity:*
*typecase alternatives can host local functions that pick up on the surrounding type hypothesis.*
*This makes portions of the translator a touch more complex: Any expression may contain function definitions.*
This, along with the unordered nature of each sort of definition (within its kind) mean that
it should be straightforward to design a browser-hosted code editor that shows everything very nicely,
similar in spirit perhaps to the Smalltalk-80 *System Browser.*

But that's not what happened. (Yet?)

String Functions and *IOlist*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The beginnings of a viable FFI (Foreign Function Interface) are now defined.
Soon enough, basic string manipulations in Sophie will be possible.
I'll probably start with substring extraction, concatenation, and garden variety transforms.

I should mention the Erlang concept of *IOList* here. Out of the box,
Erlang aims to minimize pointless copying involved in preparing nontrivial data blocks.
All of its output functions accept a branching-tree structure, the leaf-nodes of which
represent either strings or things which can coerce to strings. I really like this idea
(except for the coercion; Sophie shall have none of that) but I'm not planning to
build it straight into the very *concept* of a string type. On the contrary,
the Sophie incarnation of *IOlist* will be a distinct and proper type.
For performance reasons, the conversion from *IOlist* to *string* will not be done in Sophie.

