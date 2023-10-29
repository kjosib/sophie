Sophie's Future Virtual Machine
#################################

I've started implementing a virtual machine for Sophie in C,
borrowing liberally from the code and ideas
in `Crafting Interpreters <https://craftinginterpreters.com/>`_

I am not planning to translate the whole of Sophie into C.
Rather, the plan is for Sophie to be able to emit an intermediate
representation which a separate VM can interpret at a respectable speed.

The intermediate representation is made of plain (UTF-8) text.
I originally thought to make it look like classical assembler input,
but then realized a structure reminiscent of FORTH would be preferable:

* FORTH-like languages are really easy to parse and compile.
* The (first) VM will be a stack machine, which maps perfectly to FORTH's agglutinative nature.


.. contents::
	:local:
	:depth: 3

Quick Demo
============

Here's an example:

.. code-block:: text

	D:\Playground>sophie -x d:\GitHub\sophie\examples\mathematics\Newton_3.sg > newton
	
	D:\Playground>d:\GitHub\sophie\vm\out\build\x64-release\svm.exe newton
	1.41421
	1.41421
	4.12311
	4.12311
	412.311
	412.311

Source Code
============

The VM source code is in the same GitHub repository as the rest of Sophie.
Look under the ``/vm`` folder.
There, you will find a build set-up that works for me on Windows and MSVC '22.
If you're running on Linux or a Mac, then ... well ... it's a C program.


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

7 October 2023
--------------

Another week's gone by! Here's what's up that's been going down:

Bench-Marketing
................

Early in the week, I messed around with the inefficient-Fibonacci benchmark::

    > { 1 "fib" PARAM 0 CONST 2 LT and PARAM 0 else PARAM 0 CONST 1 SUB GLOBAL "fib" CALL PARAM 0 CONST 2 SUB GLOBAL "fib" CALL ADD if }
    > GLOBAL "clock" CALL CONST 39 GLOBAL "fib" CALL DISPLAY GLOBAL "clock" CALL SUB
    6.3246e+07          [ -8.466 ]

Racing against this equivalent Python::

    Python 3.9.7 (tags/v3.9.7:1016ef3, Aug 30 2021, 20:19:38) [MSC v.1929 64 bit (AMD64)] on win32
    Type "help", "copyright", "credits" or "license" for more information.
    >>> def fib(n): return n if n < 2 else fib(n-1)+fib(n-2)
    ...
    >>> import timeit
    >>> timeit.timeit(lambda:fib(39), number=1)
    13.519206900000086

On a release-build in MSVC, my VM so far computes the result in about two thirds of the time it takes Python 3.9.
That's nothing to sneeze at! Performance will fluctuate as the system matures, but this is an encouraging start.

A Start on Lowering
.....................

Having a VM that could keep up, it became time to think more about translating Sophie ASTs into
something this VM could load. Lowering is a tree-walk. Or at least the first stage is.

I began to flesh out ``intermediate.py``. Now typing ``sophie -x program.sg``
will translate *program.sg* into instructions for the VM. Let me be clear: It's far from ready.
In fact it only copes with a few forms, and imperfectly at that.

I am setting a goal to be able to translate this Sophie code::

    define: fib(n) = n if n < 2 else fib(n-1) + fib(n-2);
    begin: fib(39); end.

For today I'm not going to worry about lazy evaluation or memoization.
I will have to come back to it very soon, but I do have a strictness-analysis pass in mind that would
recognize this function as strict in its argument.

Aside: I will not have the patience to run this in the simple Python-based run-time.
I extrapolated from the behavior at ``fib(29)`` that the simple runtime is about 100x slower.
(Then again, it also emulates call-by-need here... But still... 100x.)
If nothing else, this is a strong incentive to get the VM to a respectable place.

And that worked.

Maybe tomorrow I'll solve closures. The Newton's-Method demo would be a good test-case.
And speaking of, it's not too soon to want some automated tests. But what to assert?
Especially at this early stage, the requirements are going to keep shifting.

Closures Partially Solved
..........................

I've decided to start with the CLOX / LUA design for closure-capture.
A closure-object will contain a copy of its captured values rather than a static link.
It seems to be well-suited to modern architectures, and it means no need for escape analysis.
A VM instruction ``CAPTIVE n`` will push the ``n`` th captured value onto the stack.

Figuring out the proper ``n`` is the tricky bit.

The ``Translation`` visitor now passes around some context -- an object responsible for
working out the particulars of closure capture and proper initialization of closures.
In concept, each stack frame will have some space analogous to "local variables",
but they're to be filled with closures as needed. It will also refer to a closure
object in memory (not just the raw function) which will provide the values for
the ``CAPTIVE`` instruction.

Some child-functions only come into scope in some branches of a parent function,
such as if they're attached to a particular match-case construction.

Here's the idea: I'll want some other VM instruction to initialize closures
at exactly the right times and places.
Now suppose I nest their definitions in the IL that goes to the VM.
I can, at the point of definition, emit an IL instruction to capture that closure.
Later, a ``LOCAL n`` instruction can push the closure on the stack, ready to call.

That's close, but imperfect: Peer functions can see each other.
That means that I'll need a phased approach: First allocate all the closures,
and then initialize them.

The real plan is to have an instruction that takes a count followed by some
constant numbers, where these constants are function objects.
Then the VM's job is to perform the above two phases.

Correspondingly, I can make the pseudo-assembler emit a single instruction for a
batch of functions all defined together.

This has an interesting side-effect: Sub-functions no longer need names!
This is because all the p-code will refer to them programmatically by their ``LOCAL`` numbers.
But it's probably still nice to include the name for more than just the aesthetics:
Debugging symbols are important, and if the runtime ever hits a panic then it's nice
to be able to follow the dump.

Things on the Horizon
......................

In some particular order:

* The VM supports line number information, but the P-ASM doesn't yet, and neither does the translator.
* Records will be heap-allocated arrays of values with a pointer to their type declaration.
* Type-case matching will be a decent-sized project.
* Record-constructors can be trivial functions that contain a special opcode, which can be inlined.
* Or, they can be a special kind of callable object. Either way, they act like functions.
* Strictness analysis, which can also apply to the simple run-time.
* Thunks in the VM.
* Actors.
* Garbage Collection.

8 October 2023
--------------

Messing around with closures. I find myself adjusting details of the IR stream to reflect
the order in which information becomes available in the translation process.
The obvious other choice would be to write a translation-planning pass first to
gather all relevant measurements in advance, but then there's the problem to keep it
organized from one pass to the next.

12 October 2023
---------------

Did battle with C today and made UpValues basically work.
The details are rather different from CLOX.
Sophie's analogue is by value rather than by reference, since values are immutable.
The run-time details of the corresponding instructions are different also,
to make mutual-recursion do all the right things,
as functions might need to capture their peers mutually.

For the moment I've added a value-type to represent the capture-instructions associated with a function.
I can see the attraction of keeping such information in the bytecode stream, but this works for now.

It still doesn't quite run the Newton's method thing, but it's getting a lot closer.

14 October 2023
---------------

Closures work in the VM now, along with a couple of standard math functions::

    D:\Playground>sophie -x d:\GitHub\sophie\examples\mathematics\Newton_3.sg > newton
    D:\Playground>d:\GitHub\sophie\vm\out\build\x64-release\svm.exe newton
    1.41421
    1.41421
    4.12311
    4.12311
    412.311
    412.311

I noticed unused ``nil`` slots on the stack in debug mode.
I tracked this back to mismatched semantics on one of the measures the translator currently provides,
which is the number of stack slots to reserve for locals when the VM enters a function.
I was mistakenly providing the number of locals *including parameters.*
Easy fix once the cause is known, but it encourages me to want to map the stack depth
more carefully in the translator. This would both simplify the ``OP_CLOSURE`` instruction
and mean that I wouldn't need to spend time reserving stack slots.
Furthermore, a nice thing falls out: the max depth of local stack the function uses.
This statistic would allow the VM to check for adequate stack *once* at function entry
rather than on each push. (Right now the approach is to allocate an array of call-frames and
a rather pessimistic amount of stack, but in principle most functions don't use all 256 slots.)
Propeller-beanie mode would solve it with page tables and let the MMU detect stack overflow,
but that kind of arcane wizardry is a long way off. Anyway the branch will be well-predicted.

Next up: tail-calls.

Let the expression translator pass around a context bit indicating whether
the expression under translation is in tail position.
If yes, and the last instruction would ordinarily be ``OP_CALL`` followed by ``OP_RETURN``,
then it should emit an ``OP_EXEC`` instruction instead. (That is, *call/cc* if you speak Lisp.)
The VM will handle the stack gymnastics just fine. 

That bit of being in tail position can supply another (minor) optimization:
emitting ``OP_RETURN`` instead of an unconditional jump thereto.
That would have interactions with the back-patching thing.

Honestly, back-patching is a clever solution to a problem that doesn't really exist anymore.
It should go away. All jumps in this little IL are forward, and things get more complicated
once type-case matching enters the picture. Therefore, I can change the IL as follows:
Assembling a jump allocates a forward-reference in sequence. A ``come_from`` compiling word
takes the number of a forward-reference, verifies that its target has not already been set,
and then sets the target to the location of the subsequent instruction. This would mean
conditional forms must compile slightly differently depending on if they are in tail position,
but this is just fine.

Under this scheme, type-case match forms require an indirect-branching instruction that allocates
an entire array of forward references. Also: The alternatives have the match-subject in scope as
well as potentially per-alternative local functions. Therefore, a match-alternative not in
tail-call position must still clean its bit of stack before jumping out.
I'll provide a clean-and-jump instruction to handle that.

So that's the plan.

15 October 2023
---------------

Garbage Collection. 

I spent most of the evening elaborating a plan for garbage collection.

16 October 2023
---------------

Back to tail calls, then.

I briefly tried a polymorphic approach, then decided to just go with that context
flag I mentioned in the entry from two days ago.

17 October 2023
---------------

This evening, I got rid of that crazy hole-threading mechanism for back-patches.
The "compiling-words" ``and``, ``or``, ``else``, and ``if`` went away in favor of a
two words to explicitly create and fill holes: ``hole`` and ``come_from``.
Both take a hole-number. One reserves the number, and the other releases the number to be reused.
The pseudo-compiler avoids overlapping uses of the same-numbered hole.
For now there are 4096 holes, which should be way more than any practical need.
But if that should ever prove insufficient, it's just software.

I've made the pseudo-compiler track the depth of stack as it goes.
This replaces the notion of explicit space for variables on the stack.

Finally, tail-call elimination is now fully operational.
Even more: the p-code will never jump to a jump or a return instruction.
This should save a few cycles hither and yon.

18 October 2023
---------------

It's probably time to get working on garbage collection.

For phase one, I'll just implement the bump allocator.
Anything that doesn't fit becomes an ordinary ``malloc``.


22 October 2023
---------------

Garbage Collection works. Finally.

One of the best ideas in the Nystrom book is to simulate memory pressure and make the collector work overtime.
And this was definitely the right time to implement GC, because GC puts hairy tentacles into what you can do.

Now I need some more programs.

Probably I shall first add support for composite types.
Also, I have an idea how to implement thunks.

24 October 2023
---------------

I can write a meaningful program that doesn't need thunks,
but it's rather more difficult to write a program that doesn't use data.
So it's time for **composite types.**

One nice characteristic of the garbage collector is the object-kind tables.
They are essentially hand-crafted vtables. So this means also the VM's
approach to calling callable objects is to delegate this through the kind.

A suitable calling sequence to construct a record might be to just push the
field-data onto the stack, then push the runtime-object representing the record type,
and then emit a call-instruction. The call method on a record-type must simply
allocate enough space, write a tag, and then ``memcpy`` the correct
portion of the stack into the newly-allocated object.

The object needs a few extra bits of information. Now that I think of it,
basically every record needs a tag. So, what shall we find using that tag?

* The size of this class of object (for GC purposes),
* a map from field-names to slot-offsets,
* possibly a variant ordinal,
* and maybe a nice debug symbol.

This means the VM will need another instruction to look up a field on an object.
Of course it will be delegated through the descriptor, just like *call* and *exec* are done.
Short term, the normal hash-table machinery will probably be fine for finding an index.

The next topic is how to load this into the machine.

Since types are module-globals, maybe the parser loads something like:

.. code-block:: text

    (head tail : cons)
    
This should be straightforward to emit from the intermediate-form generator.

28 October 2023
---------------

I spent some time on passing constructor-definitions into the VM.
Now there's pseudo-assembler syntax for records and enumerated values.
The pseudo-compiler (``intermediate.py``) emits these.
I wanted to be able to run the ``alias.sg`` example,
but compiling it meant implementing type-case matches, field access,
and explicit lists in the pseudo-compiler.

I'm not yet emitting p-code for the preamble,
so as an ad-hoc temporary measure (that might stick around)
I've posited bytecodes ``NIL`` and ``SNOC`` for making lists.

The pseudo-assembler does not yet do anything meaningful with record constructors beyond parse them.
These should be GC-heap objects so they have a ``GC_KIND`` structure and are thus callable.
Probably the arrangement is that the payload contains a hash-table for field offsets,
as well as the total number of fields and any tag-number that may be required.
And then the first payload-word of a *record* object simply refers back to its constructor.
(After that, it's an array of values.)

Intuitively, the performance of the field hash tables seems pretty important.
Right now hash buckets involve the modulus operator.
I recall reading that modulus is slow for that purpose.
But let me not get ahead of myself.
It may be that most functions are at least shallowly monomorphic.
They can be compiled with inline-constant field offsets, making the hash table irrelevant.
Certainly it would work inside the arms of a type-case.
(Anything smarter would require more information from the type checker.)
Alright. Putting a pin in that notion.

29 October 2023
---------------

Fitting in some car-painting. I got a scratch in a weird place and I'd better at least prime it before rust sets in.

Goal for today is that record-definitions will do something useful instead of crash.
There's a small infelicity in the arrangement I presently have in mind:
The definitions go in the globals table and so presumably must be GC objects,
but they own some non-GCed memory: the contents of their individual hash tables,
which currently are not subject to GC. If a record-type ever becomes unreachable
then its hash-table becomes floating garbage on the ``malloc`` heap.

The larger pattern is that *resources* -- things the GC does not control --
may need to be finalized rather than simply forgotten.
One idea: GC objects that own resources get a weak-reference from a finalization queue.
But for the moment it's not a genuine problem:
Constructors are global and thus reachable until the VM quits.

