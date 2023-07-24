Representing an AST Efficiently
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::
    This technical note describes something I may end up implementing
    in a future version, when I've run out of more important problems to solve.
    It does not reflect current Sophie.

I ran across an article that rebooted my thinking on syntax-tree representation.
I probably won't place too high a priority on this in the short run,
but who knows? That day may come.

    TL;DR:
        Dr. Sampson's article_ explained a special case of arena-allocation that improved the
        space and time performance in tree operations. He gave a rationale roughly as follows.

        * A 32-bit index is half the size of a 64-bit pointer on modern architectures. Textbook-style syntax-trees are heavy on pointers.
        * Packed-array structures require less overhead in the memory allocation subsystem than allocating each node separately.
        * Packed structures have excellent locality-of-reference, which is favorable to a modern CPU cache.
        * Nodes are allocated later than their children: He evaluates expressions by processing the array left-to-right, with a parallel array of values.
        * *Hey, doesn't this vaguely resemble bytecode?*

.. _article: https://www.cs.cornell.edu/~asampson/blog/flattening.html

I began to think about some further implications. And that's when I realised:

**We don't even need the index links!**

* The array of "operators" (i.e. node-types) alone constitutes a Reverse-Polish Notation (RPN) expression.
  If you process the array strictly left-to-right, and you know how many children each type of node has,
  then you can run any bottom-up pass you like, with roughly logarithmic extra storage,
  simply by maintaining a stack of child-nodes and referring to the operator-table as you go.
* LR parsing is almost exactly this: You can think of it as filtering out the uninteresting tokens from scanner,
  and then inserting the parse-rules where they go from that stream to make an RPN expression of the AST.
  It's just that in a traditional parser, the RPN never exists per-se: instead, it's "executed" immediately
  in the form of parse-actions.
* In general, these separate arrays make it easy to allocate *uncoupled* space for different compiler activities.
  It would be much less convenient if all the pass-specific data were attached to the AST nodes directly.
* The same array processed right-to-left is effectively a top-down walk.
  A stack with counters can track where the parents were, so information can trickle down this way.
* Some operators (e.g. literal values, identifiers) will refer to ancillary information.
  These can fit in a parallel list: Just keep a cursor for this and advance it as appropriate.

Not everything fits in a neat little box yet.
Some of Sophie's parse-actions re-arrange their subtrees slightly.
I'm sure re-writes are feasible, but I'll need to revisit the problem.

In any case, *some* linkage structure is probably nice to have around.
Leaf nodes need at least an external index to their semantic value.
(For example, maybe you have a table of identifiers, and a table of quoted strings, and of literal numbers...)
That makes room for an index associated with each operator too.
One interesting candidate would be the node's leftmost leaf.
Intrinsically a node's left-sibling occupies the index just before the node's leftmost leaf.
This allows a reasonable-compromise means to navigate the tree directly.
