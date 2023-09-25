Sophie's Future Virtual Machine
#################################

I've started implementing a virtual machine for Sophie in C,
borrowing liberally from the code and ideas
in `Crafting Interpreters <https://craftinginterpreters.com/>`_
It's not much to look at yet, but progress takes time.

I am not planning to translate the whole of Sophie into C.
Rather, the plan is for Sophie to be able to emit an intermediate
representation which a separate VM can interpret at a respectable speed.

The intermediate representation will be made of plain (UTF-8) text.
I originally thought to make it look like classical assembler input,
but then realized a structure reminiscent of FORTH would be preferable:

* FORTH-like languages are really easy to parse and compile.
* The (first) VM will be a stack machine, which maps perfectly to FORTH's agglutinative nature.


Where's the Code?
==================

When there is something presentable, it will appear in the same GitHub repository as the rest of Sophie.


Why Not JVM or CLR?
====================

There is no fundamental reason to avoid JVM or CLR, and indeed in the long term those may be strategic.
But those both impose a certain set of arbitrary technical constraints.
Emitting either would be like being forced to write sonnets in iambic pentameter before I'd learned
basic English composition. Writing to a custom VM means I can solve implementation challenges
in C rather than by creative puzzle-solving with someone else's existing set of bytecodes.
It also means I get to avoid all the ceremony surrounding `.class` files or dot-NET assemblages.
Sure it also means being in a walled garden -- for now! But eventually I expect it will be
at least possible if not straightforward to translate Sophie's FORTH-like IR into either JVM or CLR.


Peculiar Challenges
=====================

The simplest possible first step is a tree-walk to just print some IR.
But that quickly highlights a performance issue:
Pervasive laziness is a great semantics, but call-by-need is a tax on implementation.
Therefore, it's time to solve the strictness analysis problem.
But even so, there will be a fair number of thunks.
I shall probably want an opcode to build a thunk.
That probably needs the address of the code that implements the expression corresponding to that thunk.
I should treat that expression as its own basic-block.

There will be formal parameters not statically proven strict,
but the values of which become strictly necessary.
That means I shall want an opcode to force a parameter.

Non-parametric functions one may call named-subexpressions.
These are pure by definition, so they should not be evaluated repeatedly in the same scope.
(More generally, common subexpressions may be given similar treatment, but that's for later.)
Let thunks for these subexpressions implicitly live in a surrounding function's activation context.
This is akin to having a local variable. Part of the preamble must be to prepare these.

Eventually threading concerns will be forefront. I do not now know how to program threads in C,
but I will learn. The thing I see as most potentially problematic is shared-memory messaging.
A message containing unevaluated thunks (even indirectly) represents the potential for a data race.
To prevent that, the obvious temptation is to demand messages be fully evaluated in advance.
That is, no co-data in a message. But to reconcile this with lazy semantics *is hard*. 


Design Log
==============

16 September 2023
-----------------
Felt the performance impact of Sophie's Python-based tree-walk runtime for the first time.
The example code for the 2-3 tree library completes relatively quickly,
but given a bit more input it slowed noticeably. I probably first began to consider
implementing a Sophie-specific bytecode VM at that point.

Later, I ran across an article about someone seeing a major performance boost switching
a tree-walker to a byte-code VM. And his tree-walker was probably already in C.
I asked about it.

19 September 2023
-----------------
Got a response from VM guy. Quite convincing. Got serious about making a VM.
Began by cribbing from Crafting Interpreters with intention to diverge and
produce a pseudo-assembler instead.

CI starts with the VM fetch-execute loop, a few hard-coded bytecodes, and a disassembler.
It's not much, but you have to start somewhere and this puts everything in perspective.

21 September 2023
-----------------
Got to the point where I could assemble bytecodes.
Assembler and disassembler are both driven with a table of instructions and their characteristics --
effectively "addressing modes" per bytecode. But the "constant" instruction seems needlessly verbose.
The first digression from the assembler design came when I changed the outer parse loop to
detect literal constants vs. instructions. Any literal constant gets compiled to a constant-instruction.
That's convenient for writing and running simple tests because there's less to go wrong.

It also feels a bit like FORTH.

23 September 2023
-----------------
Made the hash-table thing. The hash function (FNV-1a) is not stellar, but it will serve the purpose.
Skimmed the global-variables chapter. I will probably want a symbol table, but it won't look like this.

24 September 2023
-----------------
Looking at the local-variables chapter. It's focused on block-structure and mostly irrelevant.
I'll skim this and skip ahead to the functions chapter, for it's time to start thinking about how to
represent a calling convention and activation records.

I'd forgotten how user-hostile the C programming language is.
Every time I sneeze, the cmake configuration is haywire again.
At least with all the ``.h`` files combined together into one,
the project builds again.

Here's a general plan for functions:
I'll have some token that means to define a function.
The sequel will grab the name and a number of parameters.
It will allocate a new chunk, set a few things up including nested static scope,
and move the compiler's attention to this nested scope.
Scopes of course form a stack (implicitly because they have parent-links)
and this means there must be a corresponding end-function token.

For these scope-brackets, one option is to use curly braces.

I will deal with thunks later, after a bit more of the bytecode system comes together.

For the moment, I suppose it would be interesting to "compile" arithmetic expressions.
On the VM side, I shall keep heavy sanity checks in place for the time being.

Let the calling convention be to load the arguments in-order,
then look up the function, and then emit a ``call`` instruction.
The callee cleans the value stack, leaving the return value in place of the arguments.
The need for an explicit ``call`` comes from the ability to pass functions around as data.

For global functions, I'll just use the global-variable mechanism but use mangled names.
There will be a single "global" instruction that reads a constant from the chunk's constant table.
This is a compromise. For now, this will work. Longer-term I might prefer to make the compiler
work out a reference to the exact function and store that as an ordinary constant,
but it would require a nontrivial amount of work to represent the symbolic module import graph.

