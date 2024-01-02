Garbage Collection - The Next Generation
#########################################

It's time to elevate the game.

.. contents::
    :local:
    :depth: 3

Phase One: Bog-Standard Generations
====================================

In this phase, I don't worry about threads *just* yet.

The Initial Idea
-----------------

The typical generational GC defines a *nursery,* a larger *young-survivors* zone, and a *tenured* generation.
The nursery generally uses a bump-allocator and periodically evacuates to the *young-survivors* zone.
There must be a write-barrier: Intergenerational writes incur a journal entry,
which records the address of the "older" word written into --
someplace we can find it when it's time to grey the roots of a "younger" zone.

To evacuate the nursery, it's much like a Cheney collector.
The differences are:

1. The journal entries are like a source of roots.
2. You're appending to "young survivors" instead a new flipping *to-space* every time.
3. You can re-use the nursery over and over.

The "young survivors" are considered full when the amount of room left over is less than the size of the nursery.
That triggers a gen-1 collection, which I will gloss over for the moment.

Something Astute
-----------------

Let's just define the nursery to be the second half of the unallocated space in the "young survivors" zone.
Now it's considered "full" when the nursery gets too small for comfort -- say, 16k.
At that point the allocator can briefly run in a mode to fill up the rest of *young-survivors* space,
but then must perform a tenuring collection.

It would probably also improve performance to limit the nursery to some
maximum size so that it fits in L1 cache with plenty of room left over.

Tenuring
---------

The simplest tenuring policy is to just declare a full *young-survivors* zone as promoted and allocate a new one.
The generational hypothesis holds that *young-survivors* will now contain some garbage.

The minimal viable improvement over what I had before would stop here:
A full "young survivors" would just get a complete evacuation as before.
The use of an explicit nursery would make complete collections much less frequent.
If there's a large-enough "latent" reachable set, this should still be a win -- for a given heap size.

The occasional full-heap collection won't cause serious heartburn for
jobs without hard real-time requirements. Heap-size management can just be a scaled-up
version of what I originally did for the simple Cheney-style collector.

It's normal to manage older generations with something other than simple evacuation.
But for now, I'm not going to sweat that small stuff. There are bigger fish to fry.


Phase Two: Thread Safety
=========================

It's pretty standard to give each thread its own nursery.
What happens next is a deeper question.
Can threads also have their own young-survivors?
Actors can get tenured, but we don't want bad interlocks between them.

Minimizing Contention
----------------------

Let us assume a *young-survivors* zone per-thread, with the same design as before.

A nursery collection is fairly straightforward:
You move a small collection of objects and you know where all the references are.
As long as nothing older *moves* then it should be relatively safe.
The obvious hazard would be conflicting updates from different threads to the same word in gen-2 storage.

For actor contents, that can't happen because actors are in at most one thread at any given time.
Also, let's say that before an actor can migrate to a new thread, you have to clear it out the nursery.
Let's say that we run a nursery-collection after each *round* of messages,
along with any collections that might have naturally run otherwise.

Stopping Work Migration
------------------------

Laziness presents a problem. If the content of a message includes thunks,
then possibly those thunks could get inter-thread references. Although by definition
the answer to snapping a thunk is deterministic, it nevertheless requires synchronization.
What's worse, it can make trouble by, for example, causing a U/I thread to block on a heavy computation.

The obvious solution is not to let messages contain thunks, even indirectly.
(A lazier approach is to force the matter just as a message actually gets sent.)

That isn't easy.

Suppose records had an accurate flag indicating whether they can reach (even indirectly) a thunk.
(The constructor could easily supply such a flag.)
Then some sort of flood-fill algorithm could run on message arguments.
The trick is coordinating that flood-fill so as not to run out of stack in the process.
This will take more brain than I can devote to the problem right now.

Stopping the World
-------------------

Full-heap collection normally involves a stop-the-world phase so the
collector can safely finish its job without mutators making trouble.

The standard solution to this problem is to sprinkle
`yield points <https://www.researchgate.net/publication/292669501_Stop_and_go_understanding_yieldpoint_behavior>`_
in key places. Each thread periodically checks a flag -- somehow.
Canonically you check at some combination of function-entry, function-exit, and top-of-loop.
**Sophie** has no explicit loops, so just function-entry should be enough.

The easiest design presumably uses a volatile global variable.
That would work fine on Intel machines, but others might need an explicit memory barrier.
Another choice is to press page-table mappings into service.
That has less overhead in the common case, but longer time-to-yield
and also requires writing a signal handler.

Coordinating Collections
-------------------------

A nursery-collection will not take any locks.
I must arrange that the nursery cannot contain data that any other thread could see.
Therefore, each thread must have an "out-box" for inter-thread messages.
Only after a nursery-collection can messages be actually sent.

I'm assuming that *young-survivors* zones can possibly refer to each other.
This makes sense: Suppose actor A composes a large structure and sends it to actor B
serviced by another thread. Unless the runtime copies all that data from one zone to
the other (which seems wasteful) then actor B will read from some other thread's gen-1.

In this world, when a *young-survivors* zone fills up,
we just mark it as promoted and grab a new one.
After experiencing genuine memory pressure,
the run-time can stop the world and scan everything.
These should not happen too frequently.

How do we decide what's "memory pressure"? Well, one option is a slow-growth policy.
Perhaps an environment variable can set the maximum allowed heap size. 
But those are questions for a later date.
