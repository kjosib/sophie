How the Runtime Casts Actors
=============================

Sophie now has syntax for user-defined actors. The resolver passes also (seem to) pass muster on actors.
I'm anxious to see this work, so I'll skip type-checking for the moment and start with the runtime.
I will come back to check the types of actors some other time.

.. contents::
    :local:
    :depth: 2

Recap of the Runtime
----------------------

Sophie's interpreter is currently a super-simple tree-walk.
The file ``runtime.py`` has the following major sections:


* A bunch of ``_eval_this`` and ``_eval_that`` which express the operational semantics of evaluating expression.
* The functions ``force`` and ``_strict``, along with ``class Thunk``, most of the mechanism of lazy-evaluation.
* Classes ``Closure``, ``Primitive``, and ``Constructor``, all subclassing ``Function``,
  which represent the runtime manifestation of callable values that take at least one parameter.
* Classes ``Nop``, ``CompoundAction``, ``BoundMessage``, and ``TaskAction``,
  implementing ``Action`` by way of the ``.perform()`` method.
  These provide operational semantics for observable behavior.
  These are considered runtime values in a certain sense.
* Subclasses of ``Message``: ``ClosureMessage`` and ``BoundMethod``.
  These provide ``apply`` as in you'll provide some arguments and then get something ready to send.
  The last doubles as an ``Action`` for when the underlying method (behavior?) does not take arguments.
  So again these are run-time values, and may be seen structurally as ``Function``.
  Indeed, ``Message`` does inherit from ``Function``.
* The structures by which to interface with the multithreading runtime:
  ``PlainTask`` and ``ParametricTask`` are already well-used.
  In contrast, ``UserDefinedActor`` is partially sketched out but needs a bit more work.
* And a few bits of glue-code to tie it all together.

The first hint that this was going to be confusing came from the names ``BoundMessage`` and ``BoundMethod``.

Creating Instances
---------------------
The semantics around creating an actor-instance are that there are *new-actor* phrases
(joining a name to a template-expression) which may be found as part of a *do-block*.
The current ``_eval_do_block`` returns a ``CompoundAction`` because there's a phase
difference between figuring out what work to do, and actually doing the work.

.. note::
    This phase-difference allows one to treat an action as data without any special syntax.
    Some languages require an explicit call-procedure form, such as the empty parens.
    In Sophie, it's meant to be clear from context.

So that means I'll have to look at how ``CompoundAction`` behaves.
Its ``perform`` method presently uses the passed-in ``dynamic_env`` which reflects the
local static scope wherever the do-block actually appeared.

I'll adjust ``CompoundAction``::``perform`` to create a subordinate activation-record
and therein assign names per its ``NewAgent`` entries -- if it has any.
Thanks to the possibility of shadowing, I cannot simply use the outer activation record.
(Maybe I should disallow shadowing? But that issue should be about ergonomics, not hacks.)

The idea is to evaluate the *template-expression* in the scope
given by ``CompoundAction``'s ``self._dynamic_env``,
use the resulting template to create an instance, and assign the instance to the name.

New Run-Time Types
--------------------
I'll need to distinguish actor-instances from actor-templates and actor-classes.

An actor-instance must have a private copy of local state, a vtable.
Both can just be dictionaries.

An actor-template must have the information necessary to create an actor-instance.
However, it lacks a mailbox or any of the interface necessary to participate in
the message-passing and task-scheduling machinery.

An actor-class is sort of a function that creates actor-templates.
If *syntactically* the actor is stateless, then the actor's name should bind
directly to a suitable template that just doesn't define any special state.
But if the actor expects private state, then we must bind the name to something
akin to a record-constructor. When called with arguments, it produces a template.

Executive Adjustments
-----------------------
There is a function ``_prepare`` in ``executive.py`` which must be adjusted.
Previously it only *declares* a placeholder slot for ``UserAgent`` symbols.
It should rather *assign* either class or template as appropriate.
This could in principle also be solved in ``runtime.py`` : ``_eval_lookup``,
but I'd rather deal with it in the same place as record-constructors.

Early on I'd considered allowing actor-templates to be defined anywhere,
rather than only as top-level declarations. If I'd done that,
then adjusting ``_eval_lookup`` would be more appropriate,
and also actors would require a static-scope pointer.

You can make a case for doing it either way, but right now, this is the way.

Strictness and Volatility
--------------------------

Probably, neither the state of an actor nor the content of a message should be a thunk directly.
This is easy to accomplish by forcing the arguments before constructing actors and messages.
(Indeed, the runtime already does this.) However, there's also the possibility to pass records around.
In this case, it's probably not practical to require strictness all the way down.

There is a tricky other side to the strictness coin.
Actor state is mutable, so when you write down an expression involving that state,
you want to know which version of the state you're writing about.

Hazard
    Suppose we pass current state into a function that builds a structure from its arguments.
    And suppose we either store that structure into a message or update state based upon it.
    If that structure contains a thunk which refers back to mutable parts of ``self``,
    then the ultimate reader could get the wrong data. That would be a pernicious data race.

Chosen Solution
    I shall add a bottom-up pass over the syntax of value-expressions.
    The idea is to mark them as being "volatile" if they contain a volatile sub-expression,
    with any reference to ``self`` being the base case of volatility.
    
    The ``delay`` function then gets modified so that it never makes a thunk of a volatile expression,
    but rather evaluates it eagerly.

Consequence
    This will appear much like having strict/eager evaluation within the scope of actor behaviors.
    It's a subtle difference, but I think it will work out sensibly.
    There can be non-volatile sub-expressions to a volatile expression,
    and these may still get the laziness treatment.

    Furthermore, expressions outside of an actor's behaviors cannot be volatile,
    so Sophie remains lazy in all the pure-functional parts.

Alternative Idea
    I could instead give actors a "become" operation and forego assignment to fields.
    The only sensible conception would be if every behavior "returns" the next subsequent
    state of the actor. And frankly, that gets tiresome.
    
