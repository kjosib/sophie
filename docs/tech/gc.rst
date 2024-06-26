Garbage Collection
###################

Sophie's VM-in-progress has garbage collection. *Nice.*

.. contents::
    :local:
    :depth: 3


Garbage Collected Memory Allocation for Sophie VM
===================================================

Phase One: Semi-Space with a Snap
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This was the VM's garbage collector until 10 May 2024.
It was not too hairy to get right, and plenty fast enough for the circumstances.
It did incorporate exactly one industrial-strength idea,
which is different treatment for objects in different size classes.

Concept of Operation
----------------------

The main cool-factor with this collector is that it handles large and small objects differently.
It uses compacting collection for small objects and non-moving collection for large ones.
The goal is minimal overhead and minimal fragmentation.

The text below assumes some general familiarity with garbage-collection theory.

Small objects
..............

**Small objects** -- smaller than a few K -- live in an arena with a simple bump allocator.
Whenever this fills up, the system will run a full collection.
The arena itself is allocated out of the C/``malloc`` heap.
This collector does not simply divide a large extent into semi-spaces.
Rather, it allocates a fresh arena for ``to_space`` at the start of each collection.
At the end, it releases the old arena back to the C heap.
This allows the size of the arena to adapt to the needs of the program,
which should help it play well with others in a modern operating system.

Copying/moving collectors need to determine the size and layout of each heap object.
To that end, all garbage-collectable objects begin with a header consisting of a single pointer.
Most of the time it points to a descriptor, which is a structure containing function pointers.
If this sounds like a reinvention of C++, that's because it kind of is.
But writing in C this way allows at least one cool trick:
To represent a "Broken Heart" (the forwarding pointer for an object evacuated from ``from_space``)
just point the object's header at the newer copy of the object in to_space.
The mutator can never observe this, and it's easily detected in the collector.


Large objects
..............

**Large objects** (and non-movable ones) live on the C heap with two extra pointers for bookkeeping.
One pointer forms a linked list of all large-objects, and another pointer called ``mark`` determines color.
In white objects, the ``mark`` is ``NULL``. Otherwise, it's one part linked-list and one part set-membership.
There is a work-list called ``grey_lobs`` which points at (wait for it...) grey large-objects.
So, any object reachable via that origin is grey. Other marked large-objects are black.
This needs to work even for the tail of the list, so there is a designated sentinel instead of NULL.


The String Table
..................

Sophie's VM keeps all strings interned. (Why? Because Robert Nystrom did it that way in CLOX is why.)
Anyway, this means there's a table of weak references to string objects.
Naively you'd simply delete entries that didn't get marked at the end of a collection.
But since the table itself is never grey, the references still point into ``from_space``.
So you must determine color not by *where* the reference points, but *what* it points to:
A broken heart means update the key to follow the forwarding pointer!
Otherwise you end up with multiple copies of the same string running around causing problems for pointer equivalence.
(Yes, this bug happened.)


The Root-Darkener List
........................

The VM initializes different subsystems in stages,
and those stages allocate garbage-collectable objects.
The collector must not try to darken roots from subsystems that aren't
properly initialized yet. That would pick up nonsense and tends to result in a crash.
In fact, when the collector runs in *stress-test* mode (small arenas, frequent collection)
it triggered this problem reliably until I added a solution.
The collector now has a list of function pointers for darkening the roots.
One a subsystem's root data structures are at least safe to darken,
it calls ``gc_install_roots`` with a root-darkener for that subsystem.

Oh, and the subsystem responsible for the string table gets to go first.

Phase Two: The Next Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In early May 2024, I upgraded **Sophie**'s garbage collection system.

Concept of Operation
----------------------

This is possibly the simplest imaginable way to add generational collection.
The big idea is to partition the active allocation arena into a *nursery* and
a *survivors* zone. This allows for many small "minor" collections -- which
visit only a fraction of the reachable set -- in between full collections.

I've taken some (ad-hoc, informal) measurements which suggest that overall,
this is a net win on both latency *and* throughput.

Finally, if Sophie's VM is ever to get threaded, then I'll need a way to
minimize contention for the allocator. The usual plan is a nursery per thread.
This change moves the VM in the right general direction for that.

Nursery Rhymes
................

The GC now allocates small objects in a nursery. A full nursery triggers a collection.
The collector decides between a minor and a major collection based on the pessimistic
assumption that everything in the nursery will be reachable. This sets a threshold
because there is a minimum tolerable size of nursery. (That size is presently 8k.)

The nursery occupies the higher portion of free space in the survivors zone:
at least the minimum, but up to half. (One must be careful not to round the wrong way.)
Generally, only about 10% or less of the nursery actually survives that initial collection,
so that ordinarily you can get quite a large number of minor collections between major ones.

The Write Barrier
...................

The classic challenge with generational collection is mutating objects outside the nursery.
(This supports lazy evaluation, actor field assignment, and other VM internals.)
If you write into an older object, linking it to a younger one, then how will the VM
know to treat that younger object as reachable?

My solution is inspired by the Squeak VM: Keep an array of pointers to "dirty" words.
These are specifically places in the *survivors* space that refer to younger objects.
If this table ever fills up, that becomes another way to trigger a collection.

All writes (after the first initial set-up) into a heap object *must* now go through
the write-barrier code in function ``gc_mutate(...)``. Additionally, since this can
cause a collection, I've had to make a bit more use of the VM stack to avoid holding
direct pointers on the C stack where the GC can't find and update them.

Large Object Changes
.....................

Large objects now have an extra field in their header to indicate which generation
they belong to. This lets the GC avoid pointlessly marking and scanning older LOBs
during minor collections.



Things not done
~~~~~~~~~~~~~~~~~

There is a small infelicity:
Presently the ``gc_mutate(...)`` function only checks the assignment target against the
boundaries of the nursery. That means updating a LOB will always generate a "dirty words"
journal entry. In practice this minor loss of efficiency should not cause major trouble.

Many generational-GC designs have more generations. I might consider it one day.

It's still too soon to worry about threads just yet. (Threads are hard.)



Hairy Design Journal
======================

.. warning::
    Speculative Design Ahead. Proceed with caution.
    Code snippets found here are not the final form of anything.
    You have been warned.

I'd like something nicer than the CLOX approach to GC.
I may start with a Cheney-style semi-space collector.
Why? Because it's just as well.

Allocation is relatively fast: mainly a pointer bump.
Compaction is stop-the-world and famously unfriendly to caches,
but then any sort of full-scan has some of that problem.

Eventually it should be easy to incorporate a nursery,
and maybe a card-marking write-barrier or some such.
Since mutations should be relatively rare,
the cost of a write-barrier should be small.

There is one other consideration: "large" objects
are not really suitable for a copying collector.
It's reasonable to treat these with a different strategy.

-----

.. code-block:: C

    #define TOO_BIG 32700

    void *next_ptr = NULL;  // Initialize -- somehow...

    static GC *small_alloc(size_t size) {
        size_t allotment = allotment_for(size);
        if (next_ptr + allotment > threshold) collect_garbage();
        GC *object = next_ptr;
        next_ptr += allotment;
        return object;
    }

    GC *gc_allocate(size_t size, int kind) {
        assert(size > 0);
        GC *object = (size > TOO_BIG) ? large_alloc(size) : small_alloc(size);
        object->size = size;
        object->kind = kind;
        return object;
    }

This implies a few things. First, the standard header looks something like:

.. code-block:: C

    typedef struct {
        int size;      // The user-size, not including the header.
        int kind;      // Useful for deciding how to scavenge.
    } GC;

Notice the lack of explicit color information.
That's OK, because the grey/white/black distinction is implicit.

We also need broken hearts:

.. code-block:: C

    typedef struct {
        GC header;
        GC *forwarding_pointer;
    } GC_broken_heart;

This means we can't have objects smaller than a pointer.
In fact, pointer alignment is often beneficial for speed.

.. code-block:: C

    static size_t aligned(size_t size) {
        return (size + 7) & (~7);
    }

    static size_t allotment_for(size_t size) {
        return aligned(size + sizeof(GC));
    }

This makes a few assumptions. I expect they're quite reasonable in practice. 

Now, I've neglected to mention what's up with large allocations.
Well, objects in the 32k and up club can be *mostly* delegated to the system.
But we do need a way for GC to find them. A few reasonable approaches come to mind.

-----

One common solution to software design problems is a layer of indirection:

.. code-block:: C

    typedef struct {
        GC header;
        void *large_object;
    } LOB;

This also conveniently handles (PUN!) another problem,
which is what to do about pinned memory in an FFI.
However, it suddenly means that lots of places must be prepared for the possibility of indirection.

-----

I'd rather have direct-pointers to all objects regardless of size,
so that the mutator need not worry about GC peculiarities.
Suppose the extra bits go *before* what the mutator sees:

.. code-block:: C
    
    #define GC_WHITE 0;
    #define GC_GREY 1;
    #define GC_BLACK 2;
    #define GC_KEEP 3;

    typedef struct LOB LOB;
    
    struct LOB {
        int color;
        struct LOB *next;
        GC header;
    };

    static LOB *all_lobs = NULL;

    GC *large_alloc(size_t size) {
        LOB *lob = malloc(size + sizeof(LOB));
        lob->color = GC_WHITE;
        lob->next = all_lobs;
        all_lobs = lob;
        return &lob->header;
    }

    static LOB *lob_from_gc(GC *object) {
        void *address = object;
        return address + sizeof(GC) - sizeof(LOB);
    }

Large objects thus participate in an explicit linked list,
whereas smaller objects are packed in with comparatively less overhead.
A couple more improvements are possible: For many objects,
the kind alone will tell how big the object is and from there
the size need not be part of the header. Also, it may be safe to assume
the system ``malloc`` returns only word-aligned pointers, in which case
the bottom few bits would be available for GC color marking.
However in this latter case, it isn't really worth worrying about.

-----

The "sweep" phase might have better cache locality if LOBs were
enumerated in a vector rather than a linked list.
However, that means being able to map from LOB-pointer back to vector-index.
It's reminiscent of tail-chasing at this point. No more.

-----

One clever thing about a Cheney collector is that the grey set is determined by a couple of pointers.
But with LOBs in the mix, things get a bit more complicated.

The classic Cheney scavenge operation looks something like::

    grey_ptr := next_ptr := bottom of to-space 
    evacuate all roots
    while grey_ptr < next_ptr:
        blacken the object at grey_ptr (i.e. evacuate every value it contains) 
        advance grey_ptr past the object it points to

The subtlety of evacuation is that it needs to work on a ``Value`` structure *by reference*
because it's updating pointers from *from-space* to *to-space* as it goes along.
It's something like:

.. code-block:: C
    
    static void break_heart(GC *object) {
        if (BROKEN_HEART == object->kind) return;
        GC *forward = small_alloc(gc->size);
        memcpy(forward, object, gc->size + sizeof(GC));
        object->kind = BROKEN_HEART;
        ((GC_broken_heart)object)->forwarding_pointer = forward;
    }

    static void evacuate(Value *value) {
        if (value->type != VAL_OBJ) return;
        GC *object = AS_OBJ(*value);
        if (in_from_space(object)) {
            break_heart(object);
            value->as.obj = ((GC_broken_heart)object)->forwarding_pointer;
        }
    }

To integrate this with a LOB system, insert this at the end of that last function:

.. code-block:: C
    
    ...
        else mark_grey(object);
    }

The remaining adjustments should be pretty straightforward:
The scavenging algorithm must be adjusted to account for an explicit grey-list,
and the finally there is an explicit sweep of the LOBs.

-----

After some reflection, a few refinements suggest themselves:

Drop the ``size`` field
    The ``kind`` field will provide enough information to advance the pointer.
    We'll need to dispatch based on ``kind`` just to blacken (i.e. select values to evacuate),
    so we might as well leave it to that same polymorphism to return the point *after* the object.
    An explicit "next-object" field is still necessary for *large* objects.
    Meanwhile, strings and vectors can contain their own size -- and perhaps also, capacity.

Treat ``kind`` as like a vtable pointer
    I've done something similar in the pseudo-assembler.
    That drops the average overhead to a single pointer.
    It's difficult to do a whole lot better.
    It could be a single byte index into a small table,
    but in practice I'll want word-aligned access to pointers within heap objects.


