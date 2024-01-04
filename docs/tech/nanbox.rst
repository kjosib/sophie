NaN Boxing
##########

Tagged unions are OK, but NaN boxes are twice as nice.

.. contents::
    :local:
    :depth: 3

Preliminaries
==============

The main concept is to exploit the fact that IEEE-754 NaN values can have a payload,
but the hardware generates a fixed and well-known payload for genuine NaN values.

https://cdrdv2-public.intel.com/786447/floating-point-reference-sheet-for-intel-architecture.pdf

If I'm reading this right, then:

* A NaN has all of bits 52-62 set, and at least one of bits 0-51 set.
* A quiet NaN has bit 51 set. With zero-payload (and negative?) it means "real-indefinite".
* A signalling NaN has bit 51 clear. But if the payload is zero, then it represents +/- infinity.
* Computing with NaN can give you a quiet version of the same NaN.
* A NaN with bit 50 set will not arise in the ordinary course of floating point operations,
  so that pattern can represent something else.
* I can probably exploit both the signalling and quiet version of this pattern.

The Plan
=========

Thus::

    #define BOX_BITS 0x7ff4000000000000
    #define TAG_BITS 0x800b000000000000
    #define SIGN_BIT 0x8000000000000000
    #define GC_MASK (BOX_BITS|SIGN_BIT)
    #define IS_NUMBER(v) ((v.as_bits & BOX_BITS) != BOX_BITS)
    #define TAG(v) (v.as_bits & TAG_BITS)
    #define IS_GC_ABLE(V) ((v.as_bits & GC_MASK) == GC_MASK)
    
This reserves bits 48, 49, 51, and 63 for the tag.
This allows sixteen non-contiguous categories of thing (besides numbers).
The sign bit indicates a nice 48-bit GC-able pointer.
I don't actually need that many categories, but it's nice to know it would work.

These tags seem necessary:

* Enum, which does double-duty for the Booleans and since types are strong.
* GC-able things like records, strings, messages, etc.
* Thunks.
* *Probably* closures separately from thunks, to make the VM's call/exec stuff work better.

These, I can do without:

* Opaque non-collectable pointers don't actually need to be distinguished from numbers,
  since the runtime guarantees not to change them. For these, just mask off the uppermost byte.
  (There's no good way to dynamic-dispatch on a truly-opaque type anyway.)
* I don't *really* need a special nil value. The Boolean False would serve just fine.
* The Boolean tag may just as well overlap with enumerated values more generally.
* The ``FN`` tag may be replaced with a kind-check, since it's only tested in the bit that snaps global references.
* The global-reference tag always points to a string, and only applies during assembly.
  I could alternatively keep a list or vector of linkages. It's a little more space during assembly,
  but potentially easier and faster to fix up later. It would also eliminate the ``IS_FN`` special-case.

That potentially leaves room in the representation for short strings.
However, that opens questions of hashing. I suspect these are hard.
So in the short run I won't mess with a short-string optimization.

