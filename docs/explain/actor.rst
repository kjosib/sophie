Actors and Concurrency
========================

It is determined: Sophie is adopting the *actor-model* of concurrent computing via message-passing.
However, Sophie must tread carefully to mix this inherently-stateful idea with pure-lazy-functional programming.

.. contents::
    :local:
    :depth: 2

Some questions have been asked. Here are some answers:


Basics
~~~~~~~~

The model is that observable behavior all results from actors (including the main executive actor)
sending and responding to messages amongst themselves.
Inputs and outputs are exposed to Sophie programs by way of system-level actors implemented in native code.

Each actor has its own mailbox. Whenever messages arrive,
they arrive in some sequence *as observed* and this is the sequence in which the actor will handle the messages.
There are no exceptions to this rule: No way to look ahead and save the first message for later.

Message delivery is semantically call-by-value, except that actors themselves are passed by reference.
(Referential transparency and functional purity means little to no *physical* copying of other data structures.)

This means there is a run-time object to represent a message such as an actor can handle.
There must also be run-time objects to represent actors.
But perhaps confusingly, there must also be a third kind of run-time object:
The *template* from which an actor may be spawned.

No Implicit Magic
~~~~~~~~~~~~~~~~~~

I don't want to include any implicit meta-information along with the messages.
For instance if your actor needs to keep track of time, subscribe it to a clock-actor.
The general principle is to inject the dependencies into the construction of the actor.


Message Ordering
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The design guarantee is that messages are ordered according to cause and effect.
For example, messages from **A** to **B** arrive at **B** in the order **A** sent them,
but they may be delayed arbitrarily.

Sophie separates the notion of message *delivery* from message *handling*.
A message is *delivered* into a queue (or "mailbox") per receiving actor.
The recipient may not be ready to deal with the message until later.
In any case, they're dealt with in sequence and at the actor's earliest convenience.

Space-Time Ordering
-------------------------------
Within a single machine, message delivery is atomic.

Suppose actor **A** sends messages to **B** and then to **C**.
And suppose further that, as a result of these messages from **A**,
actors **B** and **C** send messages to each other.

In this case, **B** is guaranteed to have received **A**'s message before it receives **C**'s message,
because **A**'s message to **B** is *causally before* **A**'s message to **C**,
which precipitated **C**'s message to **B**.

However, **C** may receive the message from **A** and **B** in either order.
Although it was a message from **A** to **B** that precipitated **B**'s message to **C**,
the subsequent message from **A** to **C** happens concurrently with **B**'s processing.
Actors **A** and **B** are in a race to deliver their message to **C** first.

Distributed Systems are Byzantine Generals
--------------------------------------------
Right now **Sophie has no provision for distributed computing** across different machines.
But let's suppose. In fact, let's suppose much the same scenario as above,
but where each actor is on a different machine with communication links between them.

Oh, and also let's further suppose that well-meaning but misinformed construction workers
accidentally cut the link between **A** and **B** just before **A**'s first message.

Actor **A** attempts to send a message to **B**, but **B** does not acknowledge receipt.
Most likely the operating system buffers that message for retransmission.

Now we have a decision to make:

1. We can block **A**'s progress waiting for an acknowledgement from **B** which may never come.
2. We can leave the matter to the operating system. Let **A** continue the mission and drive on.

Under option one, the best we can hope for is that the network stack is able to route around the damage.
Things run slow, but they're at least consistent -- until **B** is completely cut off.
So option one is not partition-tolerant.

Shortly afterward, **A**'s message to **C** precipitates a message from **C** to **B**,
which **B** promptly receives -- if it can.

Under option two, the message from **A** to **B** is either late or lost,
depending on the extent of the damage. So option two is just a different trade-off.

This is the essential pain of distribution:
    Every brush with the slings and arrows of real-world networking concerns
    creates not mere problems but *dilemmas* of competing priorities.

It's not fair to require Sophie to solve *Byzantine Generals* just to be distributed.
Far better is to let different distributed-computing libraries supply different operating characteristics.
Maybe one among them comes to dominate.
It might even work out that the real answer is to participate in some sort of polyglot microservices
ecosystem and never mind about distributed-*Sophie*-per-se.

Private Mutable State Has Consequences
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Lazy operations on (co)data structures can yield control before they are fully evaluated.
The remainder of such evaluation must not depend on later mutations.
The intended semantics are that any suspended computation in the scope of an actor can only
access a consistent snapshot of the actor's state.

*Which Snapshot?*

One possible approach would be to take a new snapshot at each "semicolon".
This produces reasonably intuitive behavior if you're used to procedural
languages with the usual kind of assignment. However, it comes at a surprising cost.
From an implementation perspective, different references to one sub-function could
possibly end up producing different closures over different states.

.. admonition:: Hypothesis

    This implementation challenge reflects a corresponding intellectual puzzle
    to weave time and space together in procedural notation: What a name means
    depends on **when** the name means. I've gotten used to this from long practice,
    but it does not seem consistent with the *pure-lazy-functional* ideal.

An alternative model -- and perhaps a simpler one to reason about --
decrees that updates take place atomically at the end of the message.
The snapshot visible to all expressions is the state of the actor
at the beginning of processing a message. Closures can capture any
portion of that state in the natural way, but the effect of update/assignment
operations would only be visible to subsequent messages.

.. admonition:: Why not "Become"?

    There's nothing you can't accomplish in the present model.
    The ``become`` idea opens a whole new can of worms:
    What other kinds of actor might it be valid to become,
    and does this set depend on how the actor is used?
    The type-checking alone seems devilishly complicated.

    Maybe you want some sort of actor that can switch seamlessly
    between different modes of behavior. As things stand,
    you can have a ``mode`` field which each method depends on.
    Organizing that concept inside-out might be cool,
    but it's a rather low priority right now.

Encapsulated Reliability Domains
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Right. At some point, talk about Erlang-style Process Monitors.*

I think the theory goes that, if you have (a reference to) an actor,
you can sign up to get a message about its demise.
I've yet to think too deeply about the end of an actor.
Perhaps an actor should be able to declare itself finished,
and perhaps also include the payload of its parting message to its observers.
But this is all distant future stuff.

.. note::
    The standard conception of the actor-model lacks any idea of "broadcast".
    But in this scenario, I think we can get away with it.
    Mechanically, you can imagine some other system-actor responsible
    for reflecting a unicast message out to registered listener-actors.
    Since a dead actor won't be sending any new messages,
    all that's left is to ensure the usual space-time ordering
    with respect to messages previously sent.
    And this is no problem, because a death-knell is **causally** after
    an actor's last act.

