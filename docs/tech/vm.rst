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
making a Sophie-specific bytecode VM at that point.

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

25 September 2023
-----------------
Added the bit about call frames, mostly cribbed from CLOX with suitable adjustments for what else I've changed.
I don't like the indirection to get at the IP, and there's still no way to define or call a function,
but at least this lays down a conceptual framework in C.

I glanced ahead at how CLOX handles defining functions.
I plan to diverge, because Sophie knows everything ahead of time. 

Suppose a simple global function ``double`` with the obvious definition.
I could write::

    { "double" PARAM 1 PARAM 1 ADD RETURN }
    
Statically, the ``{`` should be enough to make the pseudo-assembler construct a function,
name it ``double``, and arrange to begin assembling into that new function.
There should be a context stack because the ``}`` should send work back to the prior function.

If the ``{`` happens at global scope, then I can treat this like assigning a global variable.
If it happens at local scope, then it's a little more complicated.
First, the current function gets a reference to a child function.
I can keep these references in a vector attached to the function-definition object.
At run-time, there must be some instruction suited to composing a closure over a function.

I'd like not to repeat work evaluating non-parametric functions, but I can solve that problem later.

26 September 2023
-----------------

Later on last night I got the itch to make the pseudo-assembler actually build function-objects.
Now I think it does, but I still have no way to call them.
It's probably time to implement a ``call`` instruction.
For now, I'll just call whatever's at top-of-stack and rely on the callee to interpret parameters.
That breaks a common pattern in half, but it's the fully-general solution.
I can worry about super-instructions later.

CLOX goes to great pains to worry about things like a function's arity and what the parameters are called.
I won't have to worry about that: It's all done in the Sophie front-end. Sophie can emit numeric offsets
from the stack base. Which reminds me: I'll want to have a base-pointer in the call-frame.

In any case, since defining a function effectively just sets a global, I'll have to implement that "global"
instruction as well if I want to actually call said function.

I'm not going to worry about thunks right this minute.
I feel like it should be *at least possible* to add later.
Similarly, I'll not worry about tail-calls just yet.
Those are definitely easy but they *are* a distraction for now.

29 September 2023
-----------------

I got function calls basically working. There's also most of support for native functions,
but I don't have any examples yet.

I'd been reading about dispatch loop performance. Apparently the very latest generations of
CPUs have such excellent branch-predictors that they even deal well with switch-case dispatch loops,
but if you're running on consumer-grade silicon then you're probably still at least a little
bit better off with the distributed indirect-goto pattern.
And anyway, it doesn't hurt anything on monster CPUs.

Trouble is, sources I've found suggest MSVC does not support the technique.
It might be premature optimization but I've gone ahead and made a ``NEXT`` macro anyway,
which for now is just ``continue``.
That's handy because it jumps out of potentially-nested ``switch`` statements.
And I do have such a thing in the bit that interprets a ``CALL`` instruction.

For the moment, this code::

    { "X" CONSTANT 1 DISPLAY CONSTANT 2 DISPLAY } GLOBAL "X" CALL GLOBAL "X" CALL

writes ``1212`` to the screen. (Obviously ``DISPLAY`` is a temporary hack.)

In the next increment I'll probably change the function declaration sequence to start with the function's arity.
Also, I'll probably want to change the operand-mode signature to pass in the whole function for sanity checks.
That suggests unifying functions with chunks. The only place chunks appear so far is in functions. Time will tell.

30 September 2023
-----------------

Returning Values
................

I changed ``RETURN`` to return the topmost stack value past whatever arity of functions.
This creates a subtlety: if the function has no stack-effect,
then ``RETURN`` ends up duplicating whatever happens to the be at the top -- even if that means underflow.
Evidently I shall want an instruction that does not do this, for use with procedures.
The compiler will deal with this sensibly because function and procedure calls are clearly distinct in Sophie.
For the time being, ending a function inserts a ``RETURN`` instruction -- and maybe this is just good insurance.

Parameters
............

I have decided to implement parameters today.
For now that means adding an instruction to read a parameter.
I'll call it ``PARAM``. It will take an immediate byte to indicate which parameter.
This will motivate smartening up the assembler so as not to accept out-of-range bytes.
Or I could save the p-code trust problem for later. After all, an ``.EXE`` file is just as dangerous
if you don't know where it came from.

OK, that seems to work. This code::

    { 1 "double" PARAM 0 PARAM 0 ADD } CONSTANT 21 GLOBAL "double" CALL DISPLAY

now emits ``42``.

Control Flow
..............

Control-flow is next. I'll start with simple selection via forward jumps.
The pattern in FORTH is ``<condition> THEN <consequent> ELSE <alternative> IF``,
and this reflects the compiled structure of such code. The equivalent of *else-if*
is to just nest another *then-else-if* structure inside the *<alternative>* part,
which means several ``IF`` words in a row. This means perfect nesting, and it's fine.

So, let's suppose a stack of nested conditionals.
At any given time, there's at most one pending back-patch per such.
Here's how that works:

* ``THEN`` assembles a conditional forward jump and pushes the address of the operand on a stack.
* ``ELSE`` assembles an unconditional forward jump,
  resolves a back-patch to the address after the jump,
  and pushes its own operand-address.
* ``IF`` simply resolves one back-patch.

Now, there's this trick where you thread the back-patch addresses through the code-under-construction.
It's actually quite nice, and it means I won't need to worry about explicit labels.

Sophie also features multi-way branching based on the tag of a variant-type.
The plan is to index into an array of destination addresses -- which means tags are small unsigned integers.
The back-patching gymnastics are more complicated for jump-tables, but I'll figure something out.

Consider shortcut logic. ``X and Y`` is isomorphic to ``X then Y if``.
In fact, I may as well just call the ``then`` operator ``and`` instead. 
The shortcut ``or`` operator just branches on true instead of false,
yielding a pleasing symmetry.

One must carefully consider the stack effects of conditional branching.
Well, it turns out that a branch-not-taken is always followed by popping the stack. *Always.*
I'll encode that in the VM's interpretation of these instructions.
There are fewer dispatch cycles when individual instructions do more work, which usually leads to a faster VM.
The *branch-or-pop* approach seems to strike a sensible balance.

In summary, here's the plan so far:

* ``JF`` and ``JT`` instructions jump on falsehood and truth, respectively, or otherwise pop the stack.
* ``JMP`` instruction is unconditional branching.
* There will eventually be some sort of jump-table for type-matching, but not today.

These will be assembled directly in the compiler, taking advantage of the back-patching mechanism.
I shall want a small dictionary of compiling words. Probably lower-case to distinguish from P-ASM instructions.

Rejiggering the Compiler
........................

I'm now taking further advantage of the hash-table module. Rather than a linear search for instructions,
I've arranged a hash table containing all the raw assembly instructions and also the higher-level
compiling words like ``and``, ``or``, ``else``, and ``if``. The mechanism vaguely resembles a FORTH interpreter.
In fact, I could probably simplify the scanner considerably if I went the rest of the way with that.
Someday I may pursue that idea.

Also, that word ``CONSTANT`` is too long. I'll just go with ``CONST`` for now.

A Recursive Program
...................

The test-case for today is::

    { 1 "factorial" PARAM 0 CONST 2 LT and CONST 1 else PARAM 0 CONST 1 SUB GLOBAL "factorial" CALL PARAM 0 MUL if }
    CONST 5 GLOBAL "factorial" CALL DISPLAY

I expect the thing to produce the number ``120``. And it works!
