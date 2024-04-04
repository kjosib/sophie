Actors and the Virtual Machine
##############################

Sophie's VM now (*) supports pretty much the full range of pure-functional features,
at least in some form. (Optimizations are certainly possible.) So next up is actor-model support.
That means message-passing and procedure-semantics.

* As of 4 November 2023.

.. contents::
    :local:
    :depth: 2


Phase One Requirements
=======================

In the first increment, I'll want:

* A message queue
* A driver loop to handle messages
* A built-in "console" actor to handle messages
* The ability to send messages from procedural contexts.

There's a subtlety: What exactly counts as a procedural context?
And what influence does that have on the compiling/translation procedure?

I think pretty clearly the content of a ``do`` block is procedural.
It must be evaluated strictly, and with the tail-call guarantee.

The present VM encodes non-parametric functions as thunks.
This requires careful consideration.
Consider a word that invokes two or three other words inside of a do-block,
and the last of these evaluates to a single message or task.

I think a workable design returns the VM's internal ``NIL_VAL`` which prevents the forcing
mechanism from doing wrong things with non-parametric procedures (a.k.a. subroutines).


Basic Mechanics
=================

First, let the VM support the general case. Efficiency comes later.

Compiling ``do``-Blocks
-------------------------

This is a puzzle. Here are the pieces:

* A *statement* like ``! do ... end;`` should cause the ``do ... end;`` part to become a scheduled message.
* That means a ``do ... end;`` thing is a value that resembles a zero-argument closure.
* Inside of ``do ... end;`` the ellipsis elides a sequence of statements.
  Each *statement* is to evaluate an expression into an effect and then perform that effect.
* Thus, the ``! foo`` syntax creates an effect from a closure called ``foo``,
  and that effect is to bind ``foo`` into a message for the ambient background.
  (Or, if ``foo`` happens to name a bound-method or existing 

My current plan is to make a ``do``-block represent a zero-argument closure.
Because that's not the same as a thunk, forcing it has no effect.
The bytecode within such a closure will force, then perform, each step.

That works, but leaves performance on the table. Suppose one block is inside another,
perhaps controlled by a conditional. Then it need not be a separate closure,
but could be inline byte-code instead.

This results in a few minor inefficiencies, but in the name of progress I shall tolerate them for now.
Perhaps a new compiling inflection (beyond ``delay``, ``force``, and ``tail``) would
decrease cases of constructing a closure only to call it in the very next instruction.

Compiling Actors
------------------

An actor definition requires something like a vtable.
This is very similar to the way data constructors currently work,
but where the keys resolve to methods.
These are separate name-spaces.
It might suffice to share a common data structure between record and actor constructors.

One major semantic difference is that actor fields are not allowed to *directly* contain thunks.
This is not a problem, though. There's a ``cast`` step which builds actors from templates.
The difference is enforced in the type-checker, so the run-time need not track it.
(Instead, an ``OP_CAST`` instruction can make a forced copy.)

Oh, I forgot: Actor-instances need an extra field for an in-box and a spinlock.
Normal records don't need this.
Fortunately the syntax distinguishes actor-fields from record-fields,
so corresponding pseudo-opcodes can deal with an actor having a different layout from a normal record.

Something along these lines for the data structure:

.. code-block:: C

    typedef struct {
        GC header;
        String *name;
        Table field_offset;
        Table msg_handler;
        byte nr_fields;
    } ActorDef;

    typedef struct {
        GC header;
        ActorDef *actor_dfn;
        Value fields[];
    } ActorTemplate;

    typedef struct {
        GC header;
        ActorDef *actor_dfn;
        ValueArray message_queue;
        byte spin_lock;  // Not strictly necessary before threads.
        Value fields[];
    } Actor;

In practice that ``ValueArray message_queue`` is a place-holder. It will get something going,
but it's a bit bulky when not in use. A garbage-collected vector might be more apropos,
but that implies creating a vector type -- which is not necessarily a bad thing.
I will probably want those at user-level eventually.

Also, that ``byte spin_lock`` is but window dressing until threads happen.

Compiling Methods
------------------

When a method or message is running, a reference to the ``self`` object must be in a well-known location.
It's fairly normal to treat it as an implicit first parameter, so I'll start with that approach.

There is an important new pass I'll have to add to the compiler.
I've been putting it off, but it's time.
Any expression that reads a field of ``self`` (directly or indirectly) is volatile,
and thus cannot be contained in a thunk.
To get this right, the ``delay(...)`` method in ``intermediate.py`` must be able to check a volatility flag.

It's a simple bottom-up tree-walk to generate this flag correctly.
In principle it could be done during parsing.
However, I'd rather break it out into its own pass.
The AST generation is relatively simple and I'd like to keep it that way.
In fact the need for volatility is restricted to actor-code.
Normal functions and global procedures can't mention ``self`` in the first place.

Oversimplified Message Queue
------------------------------

The model is to be shared-nothing-mutable and no thunks in messages.
So part of dispatching a message must be to force all the thunks.
For the moment, that can be a simple depth-first operation.
(If it runs out of stack, the message is too big anyway.)
I want to go ahead and handle this part now, because it attributes computation to the correct actor.
Also, the day will come when it's a necessary condition for proper thread synchronization.

I'll need something to act as a queue.
For now a simple circular buffer of ``Value`` objects in ``malloc`` space should be fine.
If it proves too small, then I'll follow a doubling strategy.
It can't be a simple ``realloc()`` but it *can* be a ``realloc`` followed by a ``memmove``
to put the gap in the right place.

Oh, and that means another ``grey_the_...`` for the GC. 

.. code-block:: C

    typedef struct {
        GC header;
        Actor *self;
        Value *callable;
        Value payload[];
    } Message;

This can work either for bound-methods or populated messages.
The GC header field will indicate which is which, enabling GC to work correctly around it.
Conversely the only way this gets dispatched is if it has the *correct*-sized payload,
so the worker thread can simply assume ``message->callable`` encodes the arity
either as a ``Closure`` or as a ``Native`` structure.

Oversimplified Driver Loop
----------------------------

At simplest, this can be a ``while``-loop that crunches through messages one-by-one.
Assuming a message is much like a record:

1. Copy its ``self`` and payload to the stack.
2. Call the associated closure.

Shall I look up the correct closure at the time the message is bound,
or keep it symbolic until the actor handles the message?
Most times it probably won't make much difference.
My instinct says the first way is probably slightly more efficient.

The Console: A "System" Actor
-------------------------------

I expect the simplest approach is to install native functions as message handlers
in what's otherwise a perfectly ordinary actor of anonymous "class".
The part that "calls" messages can be made to cooperate.


Threads
==========

Threads are hard. Deal with this later.

In broad brush-strokes the Python thread-pool scheduler should be a reasonable template,
but coordinating actual OS-threads with proper synchrony is most definitely for the future.
However, the Python code has little to say of GC.

In-Boxes
----------

Each actor has its own queue in ``scheduler.py`` partly to avoid contention for a global lock on every message.
The other reason is to prevent any single actor from running concurrently on more than one thread of control.
Message delivery itself (not counting overhead) in most cases is probably just a few instructions,
but the overhead around reclaiming and reusing many small message queues may be significant.
I have an idea to address this which I'm calling "car-pooling" but that will be the subject of a separate document.

Garbage Collection
--------------------

GC in a threading context will require some changes.
I shall have to revisit concurrent GC when the time comes.
The actor-model's invariants may make the GC problem a bit easier,
or at least change the shape of the playing field.

Meanwhile, it's not (yet) a real-time system.
Stop-The-World *is* a viable short-run solution.


Phase Two: Snapshot Semantics
===============================

As of 3 April 2024, I have decided I'll try snapshot semantics to bridge the gap
between lazy and mutable computation. This will require a plan.

VM Changes
------------

The VM implementation concept might be to first push copies of all the fields that *any* local closures depend on,
then perform closure-capture out of the stack instead of by reference to the actor-record.
A reasonable alternative would be to invent a new type of capture that pulls right from the actor.
The former has a nice advantage: even non-nested member-references pull from stack,
meaning that the remainder of the code is free to scribble on the actor record
with no separate "commit" phase, which seems like probably a win.

Compiler Changes
------------------

To make this work, I'll want to treat member-references as *completely and obviously* distinct from
ordinary field references. (Perhaps a change to the syntax is in order.)
The point is to resolve members as *symbols in scope* rather than waiting for the type-checker to complain.
I can even load each behavior with its set of used members (recursively) during reference resolution,
which solves a problem of how to code the snapshot.

Tree-Walker Changes
---------------------

Once the behavior has a *set of used symbols* attached to its syntax-object,
the tree-walker can copy corresponding values into the stack frame for a behavior.
Thenceforth, member reads need not go indirectly via the "self" object.

Caveats
---------

One idea is to henceforth use undecorated names for members.
It is concise and comes with a potential ergonomic benefit around *case-of* expressions.
But I'm leery of this: It seems consistent *to a fault.*
On the other hand, forms like ``self.foo`` make it *locally* clear which namespace ``foo`` comes from.

