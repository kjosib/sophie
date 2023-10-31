Laziness and the Virtual Machine
###################################

.. contents::
    :local:
    :depth: 2

Overview
===========

The simplest effective lazy-evaluation scheme:

* The elementary grammar forms have strict and permissive slots.
* Formal parameters to user-defined things are lazy. Actual parameters are permissive.
* Literal constants (and certain other things) are eager.
* When something (potentially) lazy goes in a strict slot, a FORCE instruction makes it eager.
* When something eager goes in a permissive slot, there is no problem.
* The return-value of a function is a strict position.
* A *thunk* is the elementary unit of laziness.

The Run-Time Representation of a Thunk
=========================================

A thunk is an anonymous niladic closure with a memo-ized result.

It has to be a closure because it could mention formal parameters to the function that contains it. 
Because it's anonymous, it cannot be captured, and so it's safe to build these in arbitrary sequence.
Because it's niladic, its ultimate value is completely determined at the instant of its creation.

The consequence of running the closure should be to compute the result of its
expression and then update the value of the thunk.

Reserve capture-slot zero to represent the value of a snapped thunk.
Perhaps it starts as ``NIL_VAL`` (not Sophie's ``nil``). This requires coordination.

It seems worthwhile to tag ``Value`` structures as containing a thunk.
Thus, the ``ValueType`` enumeration gets a new entry ``VAL_THUNK``.
To keep the GC fast I arrange that every value-type >= ``VAL_GC`` is considered a GC-able pointer.
What was an equality comparison becomes a simple inequality:
Either way it's one instruction and presumably one machine cycle.

Creating Thunks...
===================

at Run-Time
-------------

The VM will need something like:

.. code-block:: C

    case OP_THUNK: {
        push(CONSTANT(READ_BYTE()));  // Push, because the next step allocates...
        convert_to_thunk(&TOP);
        NEXT;
    }


at Compile-Time
-----------------

I'll use square brackets to delimit the code of a thunk.
Most of the internals are very similar to those of a named function.

The pseudo-compiler ``intermediate.py`` must be adjusted.
All uses of ``self.visit(subexpression, ...)`` which can possibly be in lazy position
perhaps call ``self.lazy(subexpression, ...)`` instead.
And eventually that method must respect strictness analysis.


Eliminating Thunks
===================

Some expressions statically cannot yield thunks. These include literal constants,
names of data types, the results of logical operators, and (at least for now) arithmetic.
Some other expressions might be proven eager, but that's a future problem.

Other expressions potentially could yield thunks, but they're in a position where a thunk
is not sufficient. In those cases, ``intermediate.py`` can emit a ``FORCE`` instruction.

Anyway, I posit a couple of VM instructions along these lines:

.. code-block:: C

    case OP_FORCE: {
        if (IS_THUNK(TOP)) {
            Closure *thunk = TOP.as.ptr;
            if (IS_NIL(thunk->captives[0])) { // Thunk has yet to be evaluated.
                vm.frame->ip = vpc;     // Standard calling sequence.
                thunk->header.kind->call();
				vpc = vm.frame->ip;
            }
            else TOP = thunk->captives[0];
        }
        NEXT;
    }
    
    case OP_SNAP: {
        assert(! IS_THUNK(TOP));  // Compiler should put a FORCE instruction before a SNAP if appropriate.
        assert(IS_THUNK(vm.frame->base[-1]));
        vm.frame->base[-1] = vm.frame->closure->captives[0] = TOP;
        vm.stackTop = vm.frame->base;
        vm.frame--;
        vpc = vm.frame->ip;
        NEXT;
    }

Observation
-----------

No function ought to ever *return* a thunk. It wouldn't make sense!
A function's return value is only computed if it's needed,
but thunks are only appropriate when the need isn't yet clear.
