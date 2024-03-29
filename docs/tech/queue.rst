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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Running in a single thread, Sophie uses a ``collections.deque`` as a simple global message queue,
for its ``.append(...)`` and ``.popleft()`` methods are highly optimized for this sort of thing.

Even though ``deque`` is thread-safe, it is not a complete solution for a threaded queue.
This is because ``deque`` provides no means for a consumer to wait for a producer.

The Obvious, But Incomplete, Next Step
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Python's standard ``queue`` library provides a compact if less-efficient solution for
the standard multi-threaded producer/consumer problem in the form of ``SimpleQueue``.
The pure-Python reference version is just a ``collections.deque`` fronted by a ``threading.Semaphore``
but it is supposed to come with a native-code implementation.

Great! Now threads can yield the CPU while waiting for messages.

Actors Are Not Threads!
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~~

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

Object Pools? Profile First!
-----------------------------

A truism in performance tuning is to try not to allocate.
But when it comes to performance, we should take nothing on faith.
So I ran some experiments with ``python -m timeit``.
It turns out that Python's reference-counting GC is more efficient than I gave it credit for.
Using a ``deque`` as a ``deque``-pool turns out to be about 2-3% *slower* on my system
than simply allocating a fresh ``deque`` every time an actor needs one.
And furthermore, allocating a plain empty list is much faster still,
as well as having much less memory overhead.

How Many Threads?
------------------

I mentioned the heuristic of one thread per CPU core::

    POOL_SIZE = cpu_count()

However, this is not always best.

For one thing, ``cpu_count()`` is defined to return ``None`` when it can't count.
That would probably only apply to relatively old hardware, but still::

    POOL_SIZE = cpu_count() or 3

And for another, some systems let you restrict processes to certain CPU cores::

    POOL_SIZE = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count() or 3

Jobs that perform a lot of I/O may be best served with more threads,
some fraction of which will be waiting most of the time.
For these, the optimal number of threads *just barely* keeps the CPU cores busy.
Then again, if you have a good non-blocking I/O support library,
this is less of a problem: The system just adapts.

Finally, the end-user may wish to limit the job's level of concurrency,
perhaps to guarantee resources for some other process.

Oh, one last thing: Until the GIL's no longer a concern, I'll just go with three::

    POOL_SIZE = 3

Shutting Down
~~~~~~~~~~~~~~

There are basically two circumstances in which a program should quit:

1. Some kind of overt shut-down signal arrives.
2. The system runs out of work to perform.

A special "shut-down" message in the task queue could stand for the first case.
(The proper response is for the thread to re-enqueue the message and then quit.) 

Detecting the second case is rather less trivial.

Suppose every time a worker-thread goes idle, it first decrements a
busy-workers counter in the thread pool object.
Thereafter, at its next incoming task, it must increment that same counter.
When this count reaches zero, the pool has run out of work to perform.
It can notify a special system-management queue of this fact.

Let the main thread consume messages from yonder system-management queue.
At first it can hand out tasks in sequence from Sophie's ``begin:`` block,
When that's finished, it is finally time for the thread-pool to shut down.

Pinning Actors to Particular Threads
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

There is one tricky bit: Dedicated-thread workers must still properly
announce their idle/busy transitions to the main scheduler,
lest the system incorrectly decide to shut-down too soon.

... to the Main Thread
------------------------

It turns out ``tkinter`` is designed to only run correctly on the main thread.
There's a straightforward solution: Run a dedicated work-queue on the main thread,
and arrange a *Turtle-Graphics* actor pinned to that queue.
This can then dispatch to finicky subsystems like ``tkinter``.

This means that ``class DedicatedThread`` must take special care with the ``ALL_DONE`` sentinel-object
that represents shut-down time, but that's an insignificant price to pay. 

I have done this. It works fine. But by itself, it's nothing to write home about.

I also wanted to keep the user-defined computation off the main thread.
So I defined two actors: one to run in a user thread and peel off suitable
chunks of turtle instructions; another to run in the main thread and dispatch these to ``tkinter``.
Subjectively, this seems to result in a dramatic speed-up especially with the more-complex fractal designs.
(Perhaps large parts of ``tkinter`` release the GIL, since it's TCL on the inside?)

A similar concept might be relevant to SDL for emitting graphics.

Naked Procedures
~~~~~~~~~~~~~~~~~~

**Sophie** also supports scheduling procedures not tied to specific actors.
As far as the scheduler is concerned, this is just another task.
Interface polymorphism is the solution.

Something More Sophisticated?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As long as the implementation is Python, high-performance threading is an academic exercise.
But let's do the exercise anyway.

One problem is that symmetric multiprocessing isn't really all that symmetric once caches get involved.
Moving data between CPU cores costs time.
In a well-loaded system, we should like to keep lines of communication within the same CPU core when possible.

The other (and perhaps more obvious) problem is that a single global task queue represents a point of contention.
As the number of cores (and thus threads) rises, this becomes a bigger problem.

Presently, the height of fashion in thread schedulers is something called `"work-stealing" (BL94) <BL94_>`_.
The big idea is that each worker-thread has its own work queue, thus to diminish contention for a global queue.
Translated to actors, the basic rule is to schedule previously-dormant actors on the same worker-thread as the
source of the message. (This normally minimizes the amount of communication between CPU cores.)
When a worker-thread runs out of tasks in its own queue, then it "steals" tasks out of other work-queues at random.
Erlang is said to have just such a scheduler.

.. _BL94: http://supertech.csail.mit.edu/papers/steal.pdf

The design in (BL94) is carefully optimized for *throughput* in a purely compute-bound application.
That's well and good for some things, but most of us have a very different work-load.
We play games and run business systems on multitasking operating systems.
These event-driven applications must balance bursts of computation with a lot of input and output.
The more important scheduling concerns are *worst-case latency* and *good citizenship* as a process.
**Sophie** must play well with others yet still scale smoothly from idle to full-throttle and back down. 

.. note::
    The polar opposite of work-stealing is known as work-sharing,
    which proactively tries to put new tasks on idle threads.
    Apparently this pattern is counterproductive: By the reasoning in the paper,
    work-sharing causes more communication between threads than does work-stealing.

Honor Among Thieves: A Kinder, Gentler Work-Stealing Scheduler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The aforementioned paper (BL94) does not address shut-down or conditions of light load.
It assumes that an idle thread can always find something to do by grubbing around other processor's work queues.
But interactive systems often find themselves with more threads than tasks.
BL94 would have these idle threads spinning endlessly and burning up CPU.
The right thing is to yield the CPU to another program, or to the operating system's power management subsystem.

.. admonition:: Brief Digression on Lock Semantics

    Broadly speaking I know of two kinds of locks: regular and spin-locks.

    With ordinary locks, the operating system gets involved by doing gymnastics with its scheduler.
    These *wait* very efficiently but there is a smidgen of overhead associated with each operation.
    If I write "mutex" I specifically mean this ordinary kind of lock.

    Spin-locks do not yield the CPU between attempts to acquire the lock, but instead "spin" around a tight loop.
    The benefit is that when there is no contention the overhead is like two CPU instructions.
    It's a different trade-off. If I write "spin-lock" then of course that is what I mean.

    Finally, if I just write "lock" then it means I am deliberately leaving the decision for later.
    Perhaps try it both ways and see what's more efficient in practice.

The key idea at this level is to declare a mutex which a thread must hold while
trying to steal work. This means there is at most one thief active at any given time.
Any remaining idle threads are blocked on that mutex.

The basic worker-thread loop:
    | Try to dequeue an actor from the local task queue.
    | If that fails:
    |     Become Idle
    |     Take the THIEF_MUTEX
    |     "Steal" a task
    |     Become Busy
    |     Release the THIEF_MUTEX
    | Run the task
    | Lather, rinse, repeat

The other idea is that, if the thief has failed to steal work after several attempts,
it should probably yield the balance of its time-slice.

To "steal" a task:
    | Choose any worker at random from the pool.
    | Try to dequeue a task from that worker's queue.
    | If that queue was empty, try the next in round-robin style.
    | Keep this up until either success or having chewed through all possible queues.
    | If you've done checked every queue, sleep for a time-slice and go back to the beginning.

In the worst case, this could leave one thread continually sleeping one time-slice at a time
while other threads do all the work. That has some overhead. It's not much, but it's some.
We might want to eliminate it. But that's a problem for another day.

Pinned Actors and Work-Stealing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Recall the notion of having a dedicated O/S thread for certain system-level actors.
When these actors need to send messages, they may need to wake those actors onto a
different thread (i.e. worker) than what is currently running.

It turns out to be safe to wake an actor onto any work queue.
If that queue happens to belong to an idle thread, then the thief will soon find it anyway.

Proof by induction: For number of idle workers =
    | 0 -> the actor obviously lands in a queue that gets serviced.
    | N+1 -> either the thief finds this actor or the problem reduces to N idle workers. 

This is why the work-thief is defined to poll *all* work-queues, not just *avowedly busy* workers.

On this account, the locks protecting worker task queues should probably be spin-locks.
Contention should be negligible, and the critical section is but a queueing operation.

Work-Stealing and Shut-Down
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There is a peculiar subtlety to detecting termination correctly.

Suppose we have a pinned system-actor representing the SDL library.
And suppose the user performs an "end-program" action, such as clicking the red X in the corner of a window.
SDL has a "quit" event, which the binding translates into a message bound for a normal worker-thread.
And SDL meanwhile shuts down and notifies the management queue of this fact.

Now in all probability, the worker-thread pool is all idle: The management object holds
that the number of busy workers is (held to be) zero, and now there are no pinned-actors either.
On that basis alone, we might think to shut down the process.
But this would be premature. Even scanning the work queues is not enough:
The thief could be in that brief interval between collecting a task and sending a "busy" message.

Let's suppose the game means to save a player's progress when the player quits.
There could be a boatload of activity to follow.

Perhaps the thief itself is best qualified to detect termination.
Suppose it sees zero pinned and zero busy threads *before* scanning all the queues.
And suppose further that it comes up empty-handed for tasks.
In that case, and *only* in that case,
we may finally conclude that the system has entirely run out of work to perform.

Fairness in a Work-Stealing Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One other pathology may afflict a work-stealing scheduler.
Suppose an interactive system is under consistent (but not crushing) load.
Recall that busy actors tend to reschedule themselves and their conversation partners
to the same thread over and over.

It seems possible that such a system could enter an undesirable harmonic:
Some threads come to be dominated by small, insular groups of actors,
while other threads host a great many actors in a giant round-robin.
Useful work is being done on every thread, but service levels are inconsistent:
Some actors get dramatically more or less than a fair share of CPU.
This could result in widely varying latencies for different kinds of events that
ought to be serviced more consistently.

One way to address this critique is to claim that it won't be a problem in practice.
It sounds glib, but maybe it's true. In any case it's clearly fine for batch-processing.

I don't know what the right answer here is.
Maybe we don't worry about it until someone complains.
Maybe a system-management thread occasionally butts in to stir the pot.

Conclusions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The three scheduling algorithms contemplated here are basically interchangeable:
They each represent a different trade-off, but in the end they all do much the same work.

Although "work-stealing" *seems* to offer the highest levels of concurrency and performance,
it is also vastly more complex than either other approach.
It seems reasonable that a global task queue might become a point of contention,
but checking for idle workers could *also* be a point of contention ~~ depending on the memory consistency model.

Therefore, I will not bother with work-stealing, even in a properly-threading translation,
until and unless it's objectively shown to be necessary.
