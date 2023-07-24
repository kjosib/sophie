The Message Queue
==================

Now that Sophie is developing actor-oriented characteristics, she'll need proper concurrency.

.. contents::
    :local:
    :depth: 2

.. note::
    I'm deliberately ignoring the GIL and associated problems for now.
    Modern Python threading isn't so disastrously bad as it used to be,
    and anyway the present implementation is about exploring semantics,
    not performance bench-marketing. Maybe one day I re-write it in C#.


The Original and Current Naive Message Queue
---------------------------------------------

Running in a single thread, Sophie uses a ``collections.deque`` as a simple global message queue,
for its ``.append(...)`` and ``.popleft()`` methods are highly optimized for this sort of thing.

Even though ``deque`` is thread-safe, it is not a complete solution for a threaded queue.
This is because ``deque`` provides no means for a consumer to wait for a producer.

The Obvious, But Incomplete, Next Step
----------------------------------------

Python's standard ``queue`` library provides a compact if less-efficient solution for
the standard multi-threaded producer/consumer problem in the form of ``SimpleQueue``.
The pure-Python reference version is just a ``collections.deque`` fronted by a ``threading.Semaphore``
but it is supposed to come with a native-code implementation.

Great! Now threads can yield the CPU while waiting for messages.

Actors Are Not Threads!
---------------------------

Conceptually, each actor has its own message queue and handles messages in arrival order.
It would be straightforward to have a thread per actor in a loop around its own message queue. 
However, it's probably inefficient to have a proper (OS or POSIX) thread for each actor.
In fact, this particular claim is an article of faith in the actor-oriented programming community.

In most environments the natural way to handle threading is to have one thread per CPU core.
Naively, each thread would run a simple scheduling algorithm:
Take a message from a global queue and process it with the indicated actor.
However, this is not quite right. The biggest issue is correctness:
Messages bound for one actor must not be handled on two threads at once.
(That's the whole model, after all!)
After that, coordination overhead is a secondary concern:
A single global queue with locking operations for every single message
means a lot of contention for a single lock.

A Simple Approach:
-------------------------

Suppose we use a traditional thread-pool a'la `this article <https://en.wikipedia.org/wiki/Thread_pool>`_.
But the tasks are not messages.
Instead, tasks are whole actors which can still receive messages while waiting on a global task queue.

Suppose each actor has its own lock and an *optional* task-structure.
In principle, this admits a space-efficient representation:

* Actors with no pending messages can relinquish their task-structure to an object-pool.
* The task-structure can contain the actor's message queue and any scheduling tidbits. 
* Supposing Sophie goes native, then a simple spinlock only needs one byte.
* Thus, the storage overhead for a dormant actor may be as little as one pointer (32 or 64 bits).

We get roughly these semantics:

To deliver a message:
    | Take the lock.
    | Wake the actor if it is dormant (i.e. it has no task structure).
    | Insert the message into the task-structure's message queue.
    | Release the lock

To wake a dormant actor:
    | Fetch a task-structure from the pool and and assign it to the actor.
    | Schedule the actor.

At an actor's turn to run:
    | Consume and handle messages from the task's queue until empty or some threshold.
    | Take the lock.
    | If the queue is empty, relinquish the task structure and become dormant.
    | Otherwise, reschedule the actor.
    | Release the lock.

To schedule an actor:
    |  Append the actor to the global task queue

The scheduler on each thread in a pool looks like:
    | Try to dequeue an actor from the global work queue.
    | Run the actor.
    | Repeat.

Shutting Down
--------------

There are basically two circumstances in which a program should quit:

1. Some kind of overt shut-down signal arrives.
2. The system runs out of work to perform.

A special "shut-down" message in the task queue could stand for the first case.
(The proper response is for the thread to re-enqueue the message and then quit.) 

Detecting the second case is rather less trivial.

Suppose we define a special system-management queue with a small vocabulary.
Then, if a thread times out on the task queue, it can send an "idle" message.
Thereafter, at its next message, it will send a "busy" message.

The consumer of that system-management queue would just track the number of busy worker threads.
When that number reaches zero, it would place the "shut-down" message on the work queue.
(More sophisticated strategies are also possible, but beyond the scope of this note.)

Pinning Actors to Particular Threads
--------------------------------------

Certain system actors must be pinned to a particular thread. For examples:

* SDL (or at least PyGame) event queries must happen on the same thread that initialized graphics.
* SQLite queries must happen on the same thread that opened the connection,
  although connections need not all be on the same thread.

In a thread-pool scheduler, you have no control over which thread runs what.
A workable solution would be to devote a thread with its own scheduler to each
of these very-special actors. With polymorphism:

To schedule an actor:
    | Append the actor to the *correct* task queue, as indicated by its task-structure.

The scheduler on a dedicated thread looks like:
    | Try to dequeue an actor from the *dedicated* work queue.
    | Run the actor.
    | Repeat.

Naked Procedures
------------------

**Sophie** also supports scheduling procedures not tied to specific actors.
As far as the scheduler is concerned, this is just another task.
Interface polymorphism is the solution.

Something More Sophisticated?
-------------------------------

As long as the implementation is Python, high-performance threading is an academic exercise.
But let's do the exercise anyway.

Symmetric multiprocessing isn't really all that symmetric once caches get involved.
In a well-loaded system, we should like to keep lines of communication within the same CPU core when possible.
So we can preferentially allocate an actor to the same CPU core it's recently run on.
But if threads go idle, they can steal work.

The basic per-thread loop:
    | Try to dequeue an actor from the local task queue.
    | If that fails, ``sleep(0)`` and then try to dequeue from the task queue of a random busy thread.
    | If even that fails, we have an interesting design problem.

