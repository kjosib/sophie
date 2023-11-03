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

It seems worthwhile to tag ``Value`` structures as containing a thunk, as distinct from an ordinary closure.
Thus, the ``ValueType`` enumeration gets a new entry ``VAL_THUNK``.
To keep the GC fast I arrange that every value-type >= ``VAL_GC`` is considered a GC-able pointer.
What was an equality comparison becomes a simple inequality:
Either way it's one instruction and presumably one machine cycle.


Compiling with Thunks
=======================

I've taken a surprisingly straightforward adaptation of the semantics in the Python-based runtime.
The new ``intermediate.py`` translator has three new interesting methods: ``delay``, ``force``,
and ``tail_call``. Each performs gentle introspection on the syntactic category of an expression
before deciding how to compile said expression.

The ``delay`` operation compiles literals and look-ups for eager evaluation.
Everything else gets wrapped up as a thunk. Textually in the pseudo-assembly code,
that looks like a regular function but inside square brackets instead of curlies,
and with no explicit name or arity.

* A call-expression compiles its actual-parameters using the ``delay`` form.

The ``force`` operation compiles a syntax form for eager evaluation,
expecting more instructions to follow in the same function's code vector.

* Most other things are compiled in ``force`` mode, because generally they're needed.

The ``tail_call`` operation is similar to ``force`` but with an implied return after evaluation.
That means ``CALL`` turns into ``EXEC`` and also prevents jumps to ``RETURN`` instructions.

* Forms that can do something special in tail-call position take a ``tail`` flag in their
  *visit_Foo* methods. They use this to decide how to compile the relevant parts.

.. note::
    No function can *return* a thunk. It wouldn't make sense!
    A function's return value is only computed if it's needed,
    but thunks are only appropriate when the need isn't yet clear.
    So any return-value that *might* be a thunk, *must* be forced.

Run-Time Operations on Thunks
===============================

Creating Thunks
----------------

The VM has a ``THUNK`` instruction, which works roughly like...

.. code-block:: C

    case OP_THUNK: {
        push(CONSTANT(READ_BYTE()));
        convert_to_thunk(&TOP);
        NEXT;
    }

The constant is a ``Function`` object.
The ``convert_to_thunk`` operation is basically closure-capture,
but leaving a ``NIL`` in place at capture-slot zero.

Eliminating Thunks
-------------------

The VM has an instruction like this:

.. code-block:: C

    case OP_FORCE: {
        TOP = force(TOP);
        NEXT;
    }

And yes, this means the VM is reentrant.
Anything can call ``force(a_value)`` and get back a non-thunk.
The code looks like:

.. code-block:: C

    Value force(Value value) {
        if (IS_THUNK(value)) {
            if (IS_NIL(AS_CLOSURE(value)->captives[0])) {
                // Thunk has yet to be snapped.
                push(value);
                Value snapped = run(AS_CLOSURE(value));
                AS_CLOSURE(pop())->captives[0] = snapped;
                return snapped;
            }
            else return AS_CLOSURE(value)->captives[0];
        }
        else return value;
    }

.. note::
    There is a small infelicity here.

    This design prevents re-evaluating the same thunk twice,
    but it tends to keep the original thunk data-structure around
    because the ``FORCE`` op-code works on the top-of-stack.
    Normally we'd like to force either parameters or fields,
    and update the original source if possible.

    So at some point, I may change that.
