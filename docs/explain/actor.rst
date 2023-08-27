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

Encapsulated Referential Opacity
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The *spawn-actor* operation is at loggerheads with the notion of referential transparency.
And what's more, actors mutate their own state. So we need a clear firewall between actor operations
and the part of Sophie which *is* referentially-transparent, pure, lazy, functional.



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

Encapsulated Reliability Domains
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
