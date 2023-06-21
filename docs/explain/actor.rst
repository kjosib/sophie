The Procedural / Impure Parts
==============================

.. warning::
    This chapter describes a feature which is under construction.
    It sketches out a design, but nothing in here is guaranteed to work just yet.

.. contents::
    :local:
    :depth: 2

The Paradigm
~~~~~~~~~~~~~

The general idea is:

* A pure functional realm on the one side.
* A pure object-oriented / asynchronous message-passing realm on the other.
* An message/event queue that respects causality.
* A harmonious integration between the two realms.

Each aspect has its own mantra:

* Functions: *Referential transparency with immutable data and lazy evaluation.*
* Objects: *Ask not for data, but for help. Share no state.*
* Messages/Events: *The world is asynchronous, but nothing can be in two places at once.*
* Harmony: *Action is data. You can return it, compose it, select it, etc.*

Within those confines, I aim to start with something simple and grow features later.
For example, I'll eventually want

* global procedures
* mutable arrays and dictionaries (in objects)
* code-block literals with static nesting scope
* multiple-dispatch (both for procedures and functions)
* partially-applied procedures (and functions)
* random other things to be determined

but none of these need be in the first iteration.

Finally, I have a few health-and-comfort standards in mind for the procedural bits.
I'll describe these in the relevant section, but chiefly they include:

* Local Single Assignment with Implicit Phi.
* Tail-Call Elimination

Some Semantics (and Syntax)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Probably the firmest foundation comes from the notion that action is a (special) kind of value.
So, if a function evaluates to an action, then it reflects the performance of precisely that action.
Or, more to the point, it *can result* in that performance -- if and only if the action ever makes it to the scheduler.

For the purpose of type-checking, we can say that ``action`` is an opaque type.
On the inside, it must of course contain everything necessary for the scheduler to do its thing.

As a result, we don't need separate control-flow grammar per-se.
Instead, we simply extend the existing expression grammar.

Grammar for Action
---------------------

The first order of business is to add some new kinds of expression to the language::

    expr -> SKIP                             :skip
          | SELF                             :SelfReference
          | MY name                          :SelfField
          | expr ':' name                    :BoundMethod
          | NEW name round_list(expr)        :NewActor
          | '{' semicolon_list(command) '}'  :Action
    command -> expr | assign
    assign -> name ':=' expr                 :SetLocal
            | MY name ':=' expr              :Mutate

This will create a new phylum of expressions that create actions, messages, and related intermediaries.

The Impurity Problems
------------------------
Now immediately I see two possible problems:

* One could possibly store a thunk that refers to a self-field,
  which may mutate before the thunk gets forced.
* One could possibly store a thunk that creates a new actor,
  and then the thunk gets forced more than once in a multi-processing system
  due to races.

These both fall under the category of something with identity existing in two places at once, which is a known sin.

There are two possible resolutions.

One is to keep old versions of the self around so that the thunk trivially refers to a particular point in time.
This strategy can generate a lot of garbage-data, which I'd rather avoid if it's convenient to do so.
It also means you can't get away from thinking about persistent data structures, which I'd also rather not deal with.

The other resolution says no thunk can refer to a field of the self, or to a new-actor expression,
so any such expression must be reduced eagerly before it can escape.
This actually makes more sense because it specifically respects and reflects the privacy of object fields.

This preferred solution changes the evaluation strategy in subtle ways.

Perhaps Sophie needs a pass to mark expressions that (transitively) contain *this.someField* as volatile.
Then, when the evaluator goes to delay an expression, if that expression is marked (transitively) volatile,
then instead of making a thunk, the expression gets evaluated immediately in applicative order.

But that's not quite exactly right. There must be an exit strategy. For example,
suppose the expression ``yonder:contemplate(cycle([transform(my navel)]))``
which represents sending an infinite list of belly-button lint. What happens?

Well, we can't make a thunk right away, because the outermost expression contains volatile components.
What we can do instead is construct a new form at run-time that represents
the expression ``yonder:contemplate(cycle([transform($$$)]))`` where the ``$$$`` is a lifted copy of ``my navel``.
Of course doing that quite explicitly would be expensive and confusing.
More generally, the idea is to dissect expressions into subtrees that can be delayed and subtrees that must not be;
then to treat that second category similar to how case-of expressions work:
a local symbol gets computed first, and stored in the activation record.
When it comes time to "delay" either of these kinds of expressions,
the proper behavior is then to simply read the appropriate local symbol out of the activation record
instead of genuinely delay a (now-inappropriately-repeated) computation.

* For that dissection, it might help to have an explicit ``new`` keyword to construct objects.
  It would be *possible* to cope without it, but then the type-checker would be working overtime.
* In a global function, there is no ``self`` or ``my`` anything in scope.
  But suppose ``NewActor`` expressions can happen anywhere a pure expression can.
  It must, in some sense, evaluate not to the new actor itself, but to the *idea* of a new actor.
  One could even imagine sending this new actor a message in the same expression.
  Once again, it's just a plan. The plan does not become real until the plan hits the scheduler.

.. admonition:: The difference between planning and execution

    Forcing a thunk that refers to a plan *does not carry out the plan!*
    It is safe to force such thunks multiple times; this part is idempotent.
    The pluripotent part is when an actor gets hold of such a thing *for execution.*
    If that happens in multiple threads, it is because multiple actors are meant to perform the same action.

* With that in mind, we can borrow from SmallTalk the notion that message-sends evaluate to the receiver.
  This yields convenient syntax to send several messages in sequence to the same receiver.

More New Grammar
~~~~~~~~~~~~~~~~~

Roughly the following new production rules would presumably join the fray::

    class -> CLASS name round_list(parameter) ':' semicolon_list(method) END name
    method -> TO name optional(round_list(parameter)) body
    body -> JUST command | 'do' sequence END name
    sequence -> SKIP ';' :empty |
    command -> let_binding | mutation | send | case_stmt | if_stmt
    let_binding -> name ':=' expr
    mutation -> MY '.' name ':=' expr
    send -> expr payload
    payload -> round_list(expr) | '(' ')' :empty


Additionally, the following change::

    define_section  -> DEFINE ':' semicolon_list(code)         | :empty

and a couple additions::

    code -> function | method | class
    expr -> MY '.' name       :self_field
    expr -> expr ':' name     :message
    expr -> do-block

This is probably near-minimal for interesting applications.


Critique
----------

In principle we can do without:

* The ``if_stmt`` but it's trivial to desugar.
* The ``let_binding`` but it's hard to imagine living without it.
* The global method but the implementation can wait.

It still needs:

* a way to express the concept of a bound method.
* nested procedures -- which might turn into a procedural ``where``-clause.

Some things feel a bit rough around the edges:

* I'm not sure about that ``:`` for a message-send operator. Dot would be conventional.
  This eliminates the ambiguity with field-access though, and it's not hard to type.
* I'm worried about the size of argument lists. That be less of a problem than I fear.
* This still lacks a *copy-with* operator. It can wait, but should not wait forever.

So, this stuff isn't finalized yet. But this will do for now.

More Semantics
~~~~~~~~~~~~~~~~

To be elaborated

An Implementation Plan
~~~~~~~~~~~~~~~~~~~~~~

The minimum viable:

* scheduler: a single-threaded queue.
* procedure: sends messages. (Sequence is trivial enough to support right off the bat.)
* runtime: provides an object that interprets messages a'la the teletype driver.

Let's say for temporary scaffolding, I put a global object called ``tty`` in scope
in the ``begin:`` section.
