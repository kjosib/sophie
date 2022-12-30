Complete Speculation
=====================

This chapter is a stream-of-consciousness about uncertain design questions.

.. contents::
    :local:
    :depth: 2

Module System
-----------------

Stage One
............
The simplest imaginable "module system" would simply allow something like::

    import:
    "path/to/feline" as cat;
    define:
    foo = tabby@cat(123);  # expression must explicitly qualify cat-module reference

and then ``cat`` shows up as a named-namespace from which you can draw qualified-names.
Probably these names ought to be mentioned in the target module's ``export:`` list,
but enforcing that stricture can come later if at all.

To implement this, perhaps a module-object gets a name-space of imports.
I add grammar to represent a qualified-name and hook it into the right places::

    qualified_name -> name | name '@' name

Hurdles:

* Currently, ``TypeCall`` and ``Lookup`` assume exactly a name-token. Their handlers would need an update.
* The import mechanism would need to take control at a specific point in processing.
* Presumably, relative paths should be interpreted relative to the script using them.
* The import mechanism must not get into a loop. This means keeping track of active absolute paths.
* Error reports currently don't track which file is relevant. That mechanism would completely change.
* Type-checking should take place module-by-module, so that's another update.

One point of possible aggravation: Right now match-patterns are just constructor names,
but they necessarily must form cohorts according to the variant-in-common.
If that variant is in an imported module, but the constructors are not brought into the local namespace,
then today the patterns would need to mention the same module over and over again, which is bananas.
It should be possible to just once hint at where to find a variant's definition,
and then not mention it again.


Stage Two
...........
Almost from day one, some sort of shortcut for the qualified-names will be desired.
There's a trade-off between being terse and being stable:
If you add a name to a module, does that change the meaning of programs which import it?
Arguably it should not.
One option is to explicitly list identifiers to import from the module::

    import:
    "path/to/cat/in/hat" (thing_one, thing_two);

The semantics would be to import ``thing_one`` and ``thing_two`` to the current module's own global name-space.
That's well enough for a few things at a time, but not well suited to larger lexicons.

We could combine the forms::

    import:
    "path/to/cat/in/hat" as cat (thing_one, thing_two);

semantics being that you get ``thing_one`` and ``thing_two`` as global names, but can also
reference ``worried_goldfish@cat`` if you need it.

Another idea is wildcards::

    import:
    "path/to/cat/in/hat" as cat (*);

Here, presume you get all the exports as global names.
This brings with it the likelihood of a name conflict.
One resolution is to declare an error,
but it would be better to emit a warning instead and then mark conflicted names as ambiguous.
Attempting to actually *use* the (unqualified) name might result in a proper error,
or it might later be resolved with the aid of type-checking.

    A third option would treat the wildcard as just another

Also, if an implicitly-imported name is later defined, it should probably shadow the import.
Conversely, if an explicitly-imported name is later defined at top-level, that *is* a naming conflict.
So it's important to track the "strength" of an imported name.

(One approach: have an ``implicit`` namespace between ``static_root`` and module-globals.)

The last idea is to do some sort of scope-zone thing::

    import:
    "path/to/cat/in/hat" as cat;
    define:
    foo = tabby@cat(123);  # expression must explicitly qualify cat-module reference

    with cat:
        bar = tabby(456);  # expressions have access to all cat-exports
        baz = manx(789);   # without repeatedly mentioning the cat module
    end with;
    ...

The notion here is that at most one import is in the implicit scope at any given place,
so you can't really have a naming conflict.
Although that raises a question: Should the standard preamble get special status
to remain in-scope behind ``with cat:``? Probably yes, all things considered.


Stage Three
.............

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
----------------------------------
One view of a process is a function which must wait for an input event before computing anything.
Specifically, it computes its own next state (i.e. subsequent behavior-function) and any outputs.

Independent of any concurrency model, I can explore what types might be involved using a simplified model.
So, let's consider what would be involved in a simple text-based game.
Quite likely the simplest would be "guess-the-number" style game in which the human player picks a number
and the computer makes "guesses" following a binary-search strategy.


Holes in the Code
-----------------

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
--------------------------------

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
-----------------------------

Allegedly, C++ got operator overloading so that complex-number arithmetic would look nice.
And of course it's nice to be able to support complex numbers nicely.
But what about matrices? Quaternions? Octonions? Arbitrary vectors?

It sounds nice for the arithmetic operators to work naturally for structured values,
but it's hard to define what "naturally" means.
General operator-overloading requires a number of decisions I'd rather put off.

Interfaces / Type-Classes
--------------------------

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
---------------------------------------

**Simple rule: Keep it simple.**
You shouldn't need a degree in category theory to get full use of a powerful, expressive language.
(Although it might not hurt.)
This means eventually I'll want to solve certain problems.

Partial Functions
..................

Probably the grammar will look like a function-call but with a slash before the closing parenthesis.
That makes it clear what's going on exactly and where, while still catching broken call-sites in meaningful ways.

Starmap
.........

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

Error Messages?
----------------

This is an issue on several levels.
Each represents an interesting problem to solve.

Parse Errors
..............

In the initial version, parse errors yield an arcane report.
I can't expect a new learner to figure out what they mean.
I need a better solution.
And I don't want to pollute the grammar specification.

If the parser blocks, I get back a picture of the parse stack
in terms of which symbols have been pushed so far, and what token is "next".
I can imagine writing (something like) a regular-expression over those symbols
and attaching that regex to a rule about which message to display.
This has a few interesting sub-problems.

Probably the patterns should be:

* structured like filename globs.
* validated internally against the parse tables.
* ranked from most to least specific.
* exhaustive in covering the entire space of possible situations.

I will want a way to display a diagnostic of how the reporter
decided which message to display.

Possibly, I might want patterns that include more right-context.
In that case, it should be possible for the error handler to pull some more tokens.

Scan Errors
.............

The answer to a blocked scan is to present the next character as a token
and let the parse-error machinery deal with it.

Error Context Displays
.......................

The bit that displays excerpts is presently too dumb:
It can possibly display the same line more than once,
and it repeats the file-name every time.
It ought to sort and group this information to present a nicer excerpt.
Also, some ansi color would be nice.
(Incidentally, what if input source contains terminal control codes?)

Concurrency
-------------------------------------

I'm sold on the virtues of the *actor-model* of concurrency roughly as Erlang exemplifies it.
However, Sophie will need a few adjustments to mix with pure-lazy-functional.

* The *spawn-process* operation is fundamentally a nondeterministic action with environmental side-effects.
  (It invents a different *PID* each time.) It cannot be a (pure) function, so it should not look like one.
  It's effectively an I/O operation in its own right. You cannot have a (pure) function which, when called,
  does something, because you do not get a concept of *when called* -- except in the case of actors.
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
------------------------

These are the canonical not-referentially-transparent mutation-focused structures.
There are so-called "persistent" data structures which can achieve array-like or dictionary-like
behavior within a constant factor of amortized performance, but the constant is not small.

There's a nice side effect of the functional-process-abstraction:
You can have all the *internal* mutable state you like, so long as no references to it escape the process.
The trick is how to represent the update semantics.
The textbook example here is a *proper* quick-sort: in-place
Compound or abstracted updates seem to require something akin to borrow-checking.

Tail Calls?
-------------

The simplistic tree-walking interpreter is not exactly clear about the fate of whatever
counts as a tail call in the lazy/by-need model of computation.
That's probably not important at this stage, but at some point it will be nice to
convert to an (abstract/virtual) instruction set with a simple stackless iterative interpreter.
When that day comes, it will be nice to also not make a mess of whatever counts as the stack.
The issue probably boils down to smartly managing thunks so they don't pile up in long chains,
but snap their pointers ASAP.

Unreliable Input Data e.g. JSON
--------------------------------

Simply put, I was not impressed with the ELM approach to JSON.
It felt like such a fight to wrap my head around their JSON combinator library.
There was no intuitive way to understand it, so it was hard to compose bits.

If the language has a generic ``result[x,y]`` type ( ``case: ok x; fail:y; end;`` )
then we should compose with that for all the sorts of things where things go wrong.
Incidentally, different applications might want/need more or less detail about failures.
So an application should be able to provide and use its own *bind* operator
comfortably with ``result`` types.

Stronger Guarantees
---------------------

Right now, Sophie has a traditional H-M generic type inference engine under construction.

Partial Evaluation
....................

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
.......................................

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
.....................................................

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
