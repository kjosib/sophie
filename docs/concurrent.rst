Concurrent Sophie
===================

I want to reconcile *pure-lazy-functional* with pervasive concurrency.
This has been a tough nut to crack. Here's my current thinking:

.. warning::
    This chapter is still speculative.
    It describes an incomplete, developing idea.
    Expect change.

.. contents::
    :local:
    :depth: 3

The Functional Process Abstraction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Overview
-------------

One view of a process is a function which must wait for an input event before computing anything.
Specifically, it computes its own next state (i.e. subsequent behavior-function) and any outputs.
However, this view leaves out a lot of details. And if the process can engage in more than one
kind of transaction, then its interface to the world needs a slightly richer description.

There is an implicit other-half to a process. Specifically, some *environment* drives a process.
It does so by forcing the evaluation of functions.

* The API between process and environmental driver is given as a data-type to represent a process.
  The type is normally a record or variant.
* Function-type fields represent a process's response to some environmental event or condition.
* Arguments to those functions normally represent input-data from the environment to the process.
* Other (non-function) fields may represent output from the process back to its environment.
* The API may also include other bits of data and function. It's up to the designer's discretion.

This is a pleasantly simple and elegant way to express a process.

* To the driver, a process (along with its entire state) is just some interesting data structure.
* To the functions which compose said process, the job is simply to construct such a data structure.
* A nice side-effect: By replacing the actual driver with a test stub, you can reproduce scenarios as test cases.
  Indeed, if you play your cards just right, you could do property-based testing along interface boundaries.
  But I'm getting ahead of myself.

Onions and Cakes: Layered Architecture
----------------------------------------

No single API-type is suitable to describe every kind of process.

* A business-domain model needs an API that hews closely to a clear representation of its transactions.
* A graphical interface toolkit needs an API that represents widgets, mice, keyboards,
  and all the events that interconnect them.
* At some level, a program must interface to the operating system or hardware that runs it.

Clearly, any sizeable program will involve different API-types and different environments.
Integrating a system means crafting functions to translate between different APIs;
some closer to the problem domain, others closer to the metal.
This realizes the dream of a layered system architecture:
Each layer is clearly distinct and has a straightforward purpose.
That purpose will be easy to explain, even if the code is nontrivial.
And what's more, the distinction will be easy to see because it's manifest in the form of an API-type.

The artistry and craftsmanship is in designing the intermediary interfaces and the code to connect them.

System Integration
-------------------

Early on, Sophie had this feature that whatever type of object you construct in a ``begin:`` block
would get routed to a suitable interpretation of that type. But there were only a couple such interpreters.
One of them would print your data. The other would draw turtle graphics.

Now it's possible to add drivers, at least from native modules. But I think it should also be possible
to register a Sophie-language driver for a data type. The concept is that there's an implicit call to this driver
wrapped around a suitable expression in the ``begin:`` block. And what's more,
we can make this notion recursive, so that each driven type implicitly translates down to something
at a lower rung on the abstraction ladder. In other words, *things just work* as far as the programmer is concerned,
but if you want to replace the interpretation at some level, then you can do that explicitly without too much trouble.

Concurrency Enters the Picture
--------------------------------

At some layer between the CPU and a domain model,
there is a point where it makes sense to think about doing several things concurrently.
But that's drastically oversimplified. So let me try that a different way.

Many steps in a process can, in principle, act concurrently because they have no
functional dependencies one upon the other. Or rather, the dependency graph will
have some fan-out before some fan-in. We can design our API types to express these
opportunities for concurrency so that the *driver* has a choice to re-order or interleave
the various computations which must occur on behalf of each component.

The driver for such a process will either operate concurrently -- by delegating concurrent tasks
to its own driver -- or else it will serialize operations.

If the process is composed of pure functions, then either approach will yield a correct answer.
In that case, *actual* concurrency may be seen as performance engineering.
But the API-type that represents the concurrency inherent in the problem?
That's actually just good design. Arbitrary expressions of sequential control are now an antipattern.

Alternatively, sometimes the steps in a process have a more complicated relationship with concurrency.
We may, for instance, reach out to several remote caches for a bit of data but proceed with the first answer to arrive.
In this case, a correct driver *must* respect whatever notions of concurrency are designed into the API.
It may rely for its correctness on concurrency features in the next level down,
or it may instead be close to the bottom of that stack and thus need to express things like non-blocking system calls.
This last idea is so deep in the runtime that normal Sophie programmers should never have to worry about it.

Trouble in Paradise?
----------------------
In any case, actual concurrency will require some sort of scheduler.
And I'm having trouble figuring out the data-type of a generic task-queue structure.

Consider some sort of round-robin turn-taking adapter that interleaved the steps of a suitable API type.
That plus a way to tell if a step is ready -- i.e. its relevant inputs have arrived -- could serve as scheduler.
Problem is, you sort of need a sub-scheduler for each distinct input-type,
and some way to harmonize all their respective interfaces amongst themselves,
which -- at least in current Sophie -- it's not at all clear how to do within the confines of the type system.

Maybe I ought not worry about it right now. Maybe I ought to just build a few more native drivers
for such things as SDL and networking and let things fall out of that.

