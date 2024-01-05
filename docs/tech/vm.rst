Sophie's Virtual Machine
#################################

Sophie now has a virtual machine written in C.
It got started with liberal borrowing from the code and ideas
in `Crafting Interpreters <https://craftinginterpreters.com/>`_

I do not plan to translate the whole of Sophie into C.
Rather, Sophie's front-end can emit a text-based intermediate representation
which the VM translates to byte-code and runs at a respectable speed.

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

Status
=======

Here are some open problems, in no particular order:

* [DONE] Pre-link global functions at load-time rather than hash look-ups during execution.
* [DONE] Message-passing -- starting with a console-actor.
* [DONE] Modules. The one global namespace is carved up with a simple name-mangling scheme.
* [DONE] Cryptographically secure random number generator. (It's based on ChaCha20.)
* [DONE] Improve how the GC treats snapped thunks.
* [DONE] Dismiss the bytecode-translator's data (including the global symbol table) before
  starting the user program. (After picking up the special-cased constants, though...)
* [DONE] SDL bindings, at least for some simple graphics and the mouse.
* Improved stack safety based on a max-depth analysis
* [DONE] ``do``-blocks should have tail-calls eliminated. (This may be trickier than it sounds. Or not.)
* [DONE] User-Defined Actors.
* [PARTIAL] FFI improvements.
* Turtle Graphics, perhaps in terms of SDL.
* Make SDL optional and load on demand.
* Source line numbers. In case of a run-time panic, a cross-reference is most helpful.
* [PARTIAL] Numeric field offsets. This could save cycles where a record-type is statically known.
  *This is done for actor fields.*
* Tuning the dial on eager evaluation. (This should further improve performance.)
* NaN-boxing.
* Short-string representation: Very short strings fit in a value (and don't benefit from interning).
  Shorter than 4gb may benefit from a smaller header. It would make the string module a bit trickier,
  but save a metric boat-load of allocations in string-heavy code.
* Thread-Safe Generational GC with Actors in mind.
* Actual threads.
* Arrays. (The semantics would be tied into the actor-oriented side.)
* (More) Useful libraries of bindings, data types, and subroutines.
* Affordances such as keyword highlighting in a few common editors.
* A more direct connection between the VM and the compiler. (Perhaps the one invokes the other?)
* Self-hosting some or all of the compiler.
* A means to install the VM as any other language runtime.
* A killer app.
* Multiple Dispatch.
* Operator Overloading.

Some ideas for bindings:

* Games. Presumably SDL.
* Typical OS and filesystem things.
* More prosaic applications. Perhaps QT.

Native FFI symbols still do not get their names prefixed with a name-space in the VM symbol table.
I've a notion to change that someday, and keep the prefixes distinct between pure and native.
(That way, native modules can just install everything without concern for name clashes.)


Source Code
============

The VM source code is in the same GitHub repository as the rest of Sophie.
Look under the ``/vm`` folder.
There, you will find a build set-up that works for me on Windows and MSVC '22.
The VM now requires SDL2, both to build and to run. If you're on Windows,
you will probably need to edit ``CMakeLists.txt`` accordingly and then
drop a copy of ``SDL2.dll`` wherever Sophie's ``svm.exe`` binary ends up. 
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

September 2023
^^^^^^^^^^^^^^

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

October 2023
^^^^^^^^^^^^

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

30 October 2023
---------------

Car painting finished up just in time, as it got cold and wet last night.

A number of basic demos now work in the VM.
In particular, the ``alias.sg`` and ``case_when.sg`` examples were my primary guinea-pigs today.
That means all immutable data types and all operations thereon do work.

I got a disturbing amount of practice with the debugger.
But in the end, most of the problems were trivial bookkeeping mistakes.
For example, there's a function in ``intermediate.py`` that takes note of a local symbol's position
within an activation record. It must be called just before computing that symbol's value,
but I'd accidentally called it just afterward in an early version of the code to build
type-case matchers. So of course that went off the rails. And as a result,
I have some more assertions in various places.

I think the next semantic to port would be :doc:`lazy evaluation <lazy>`.
Without :doc:`strictness analysis <strict>`, I expect it would slow things down considerably.
So it will soon be time to make a strictness pass.

November 2023
^^^^^^^^^^^^^

2 November 2023
---------------

Laziness works. Mostly.

There is still a small hole in the design that can sometime cause over-eager evaluation.
But the main thing is thunks do all the right things, and you can force thunks in the FFI as needed.
The ability to force thunks also means the VM becomes re-entrant:
It takes a ``Closure *`` and returns a ``Value``.
This fact will also enable call-backs from native code into Sophie code at some point.
Right now the re-entrant-ness is a bit rough-and-ready:
Each ``CALL`` instruction results in action on the C stack.

One thing may feel left out, if you're looking from the perspective of a TCL or Python background:
The VM has no way to signal errors. And for the foreseeable future, that's the answer.
The code should not generate errors: They've been mostly ruled out in the type system.
Anything left is a panic.

3 November 2023 - A Milestone!
------------------------------

Getting laziness right in the VM was rather like whack-a-mole.
I lost count of the irksome bugs and trouble-spots.
But on the plus side, I finally put together a batch testing script
to quickly run a whole bunch of things and see how they all behave.

Oh, and thunks are clearly not free.
I kept around a copy of the intermediate code for the Fibonacci benchmark
before and after thunks. The new version takes about 2.5x longer with thunks.
But it's still 100x faster than Sophie-on-Python, so it's hard to complain.

That's about it for the pure-functional core of Sophie's new VM.
There's plenty left to work on, but this represents a milestone.

7 November 2023
---------------

Something nice today. I made a small change in the VM.
It now pre-computes all the global look-ups before run-time.
This brings the thunk-less Fibonacci benchmark down to about 5.25 seconds in release mode.
That's about seventeen percent faster than before.
The thunk-ful version now comes in at 14.3 seconds, which is only about six percent
slower than Python's strictly-evaluated version.

8 November 2023
---------------

The ``common.h`` file was getting unwieldy. I tried carving out several portions.

9 November 2023
---------------

The dependencies between the various ``.h`` files are also unwieldy.
In fact, this was the reason for cramming everything into a single ``common.h`` file in the first place.
So thank heavens for version control.

10 November 2023
----------------

Time to make some forward progress on actors. I'll start with an oversimplified message queue.
It's just a vector. I *already know* that it won't be suitable once worker-threads enter the picture,
but that's not today's problem.

11 November 2023
----------------

Veterans' Day. I had breakfast courtesy of a local eatery. Not bad overall,
but if I'd been paying for it I would have asked them to warm up the andouille sausage. 

I noticed a GC bug which, by some miracle, I hadn't yet managed to trigger.
The issue was some or another function holding a reference while calling another function
that would allocate. In the world of moving GC, that's a recipe for a wild pointer.

I'd like a convention which makes this kind of problem much easier to spot.
To keep garbage-collectable objects on the VM stack as much as practical,
I choose not to pass them around as parameters or return values to C functions.
The exceptions are:

* Named intermediates, where there are no function-calls *at all* intervening.
* In the FFI, "native" bindings return a ``Value``. The VM will immediately put that value on the stack.
* Some functions construct and return a new thing. The caller must immediately put this somewhere safe.

To help this along, I've also added a few FORTH-style stack manipulation "words" (static inline void functions)
to the ``common.h`` file. And finally, the prototypes for functions that manipulate the VM stack
get FORTH-style stack-effect comments on their same line.

I'm not going on a crusade to change everything at once.
This will be a process. But for all *new* code, I'll take this approach.

This approach may seem odd, but I believe it to be worthwhile as a means to
eliminate an entire category of memory-safety mistakes.

-----

I made significant progress on actors today, at least in the VM:
It now builds and initializes a ``console`` actor of ``Console`` type.
Nothing uses it yet, but that will come soon enough.

Incidentally, the first version crashed the collector.
Eventually I tracked the problem to an (incomplete) structure-assignment into actor-class definitions.
That set the GC header to ``NULL``, with predictable consequences.
I don't know why I had that structure-assignment there, though.
My best guess in retrospect is that I was trying to assign several fields in one statement,
but C doesn't work that way. It must have been a brain-fart.

In the process, I noticed another benefit of keeping broken-hearts confined to the GC header:
Both actors and records rely on their respective definition objects (constructors,
in the case of records) to tell how big they are, which is important for GC.
Scribbling on the evacuated object's "old" data would clobber what might be needed later.
This also indicates against compaction-in-place. One alternative would be to make the length-check
sensitive to broken hearts, but that's another complication. Another would be to encode the size
of heap objects directly in the header, but that makes every object bigger and I'd rather not.

On the other hand, there are only so many object-types. A full pointer is not strictly necessary.
One could pack a tag and a length just fine in a 64-bit word.
Large objects go in the non-moving heap anyway, so this could take some indirection out of compaction.
Still, it's a question for a profiler, and likely to be lost in the noise.

-----

Also, I got tired of seeing only six significant figures in my numbers.
So I put a precision specifier in the line that prints floating-point values.

Oddly, the MS C library doesn't always come up with the same "shortest" representations
as what Python (3.9, on Windows) does for presumably the same values.
To see an example, use the number ``1e23`` which displays as all nines e+22 on the MS implementation.
Incidentally, there was a bug report on this very subject (and using this very example)
filed against an early JVM back in the day. But for the moment I'll just live with it.

12 November 2023 - A Milestone!
-------------------------------

Sophie's VM passed its first message Sunday.
It was to a system-defined `console` actor with a list of string snippets to print.
One additional case in the tree-walker sufficed to compile basic message-passing.
There was considerably more to do on the VM side, but now message-passing works!
Here's the ``games/99 bottles.sg`` example:

.. code-block:: text

    D:\Playground\sophie_test>sophie -x "\GitHub\sophie\examples\games\99 bottles.sg" > 99.is
    
    D:\Playground\sophie_test>d:\GitHub\sophie\vm\out\build\x64-debug\svm.exe 99.is
    
    5 bottles of soda on the wall,
    5 bottles of soda.
    
    If one of those bottles should happen to fall,
    4 bottles of soda on the wall,
    4 bottles of soda.
    
    If one of those bottles should happen to fall,
    3 bottles of soda on the wall,
    3 bottles of soda.
    
    If one of those bottles should happen to fall,
    2 bottles of soda on the wall,
    2 bottles of soda.
    
    If one of those bottles should happen to fall,
    1 bottles of soda on the wall,
    1 bottles of soda.
    
    If one of those bottles should happen to fall,
    no bottles of soda on the wall,
    no bottles of soda.
    
    Go to the store and buy some more!
    99 bottles of soda on the wall!

This is still a minimal example: It only passes a single message,
and to a system-defined actor at that.
But it should be downhill for a little while now.

I suppose that getting the remaining examples to run is but a small matter of programming.
But an odd pattern in this points to an implementation challenge:
I have front-end and (new) back-end as separate programs -- and in different languages.
They collaborate by way of a crufy intermediate representation with one singular virtue:
It's all text, so I can look upon it and even hack upon it with `notepad` or the like.

The challenge is ergonomics. I prefer the load-and-go feel of original Sophie.
It's two steps to run with the VM, and you have to know about redirection.
I have no desire to translate the whole shebang to a single host language if I can avoid it.

Is this vague idea **crazy** or **mad?** Could one embed a language into its own start-up sequence?
Approximately, suppose the VM runs in the first instance a self-contained IR program which
has does all the complicated front-end stuff for compiling a script into IR.
But instead of writing the IR to a file, it (normally) invokes a native API that
builds byte-code directly. And maybe with an escape hatch to dump the compiled IR to a text file instead.

13 November 2023
----------------

Added a few more native functions.
I can now *almost* run the 2-3 tree algorithm demo in the VM.
In release-mode it *does* run, but incorrectly.
In debug-mode, the problem is obvious:
The VM does not yet know how to compare strings for lexical order.

This exposes one of the core conceits of using Python as a first-cut implementation language:
I could previously cheat and define "less-than" as *whatever Python does,*
and for that reason the *type* of the relational operators is also a bit of a cheat:
I accept any two of *the same* type. But this is going to have to change.

For the specific cases of numbers and strings, I can hack together some reasonable behavior.
But right now there's nothing to stop you testing whether one *function* is the greater or lesser.
That's nonsense.

I actually intend for people to be able to define comparisons between members of derived types.
More generally, some sort of multi-method system had long been the general plan.
I just have not yet put any real thought into what that might look like.

In any case, I'm going to have a design problem.
Do I go with something like a *compare* method,
or do I go with explicit *less-than* and *equals* and so forth?
There are probably experiential lessons from Java, Python, and Ruby on this front.


16 November 2023
----------------

Not much to say about the VM right this minute.
I've taken a digression to work on multiple-dispatch.
The VM will eventually grow to support it,
but for now the first step is to flesh out the language feature.

19 November 2023
----------------

I've decided. I plan to add the spaceship operator, ``<=>``, cribbed from Ruby.
But rather than defining it to return a *number* with respect to zero,
I'll have it return a member of an enumeration: ``less``, ``same``, or ``more``.

What else is cool about having a decision is that it clarifies how to approach
string comparisons in the VM. So I got that done, and now the 2-3 tree demo works.
Perhaps after I add corresponding syntax, I'll convert the tree code to use it.

Incidentally, I'm not planning to use the normal relational operators for
partial orders like the subset relationship. Instead, for the short term
normally-named functions will work.

21 November 2023 - A Milestone!
-------------------------------

Milestone: The VM can play simple text games!

.. code-block:: text
    
    D:\Playground\sophie_test>sophie -x \GitHub\sophie\examples\games\guess_the_number.sg > guess.is

    D:\Playground\sophie_test>\GitHub\sophie\vm\out\build\x64-release\svm guess.is
    I have chosen a random number from 1 to 100.
    
    What is your guess? 50
    Too high. Try a lower number.
    What is your guess? 25
    Too high. Try a lower number.
    What is your guess? 12
    Too high. Try a lower number.
    What is your guess? 1
    Too low. Try a higher number.
    What is your guess? 6
    Too low. Try a higher number.
    What is your guess? 9
    You win after 6 guesses!

So that's cool.

On the other hand, I've noticed some problems. For one thing, ``nan`` trivially wins:

.. code-block:: text
    
    D:\Playground\sophie_test>\GitHub\sophie\vm\out\build\x64-release\svm guess.is
    I have chosen a random number from 1 to 100.
    
    What is your guess? nan
    You win after 1 guesses!

And for another, non-numeric strings evidently fail to set errno:

.. code-block:: text
    
    D:\Playground\sophie_test>\GitHub\sophie\vm\out\build\x64-release\svm guess.is
    I have chosen a random number from 1 to 100.
    
    What is your guess? California
    Too low. Try a higher number.
    What is your guess?
    Too low. Try a higher number.
    What is your guess? ^Z
    Too low. Try a higher number.
    What is your guess? ^D
    Too low. Try a higher number.
    What is your guess? Too low. Try a higher number.
    What is your guess? ^C
    D:\Playground\sophie_test>

One solution to both problems is a better-behaved pair of floating-point conversion functions.
Maybe something simple will come up. It's a popular-enough topic.

22 November 2023
----------------

I made a few adjustments to the ``val(...)`` function so that only numbers convert.
It still allows the infinities, but no more ``nan`` or other trailing junk.

Also, I added the named mathematical constants from the preamble,
which makes the ``some_arithmetic`` demo work.

Next step will probably be name-mangling for module distinctions at the VM global scope.
After that, I'd want to get user-defined actors working, but at the moment I only have one.
That's the mouse chaser demo, which also relies on SDL. But there's an SDL demo without
user-defined actors, so I guess that's the move.

23 November 2023 - Modules and a Speed Boost
---------------------------------------------

Happy Thanksgiving!

Name mangling now works well enough.
Some cheats are still in place for the FFI,
but the effort at least caused me to think about this.

Current FFI syntax gives a way for Python to find a module and a function therein.
That "find a module" part probably becomes "find a plug-in" and short term all the
plug-ins stay built-in. At some point DLLs may become interesting.

By the way, I ran across a VM bug which I accidentally introduced late last night.
In the process of chasing it, I was surprised by how often the GC ran in non-stress mode.
So I added a few more ``#define`` flags to control its verbosity and soon realized the problem:
It was growing the heap far too slowly. So I twiddled a few more things,
and now release-mode is (slightly) faster than Python for the Fibonacci benchmark *even with* pervasive thunks,
coming in around 12 seconds and change for ``fib(39)``.
To achieve that speed-up, I arranged to let the heap grow much larger than previously.
The process now sits around 70k of heap and traces 9.5k for each collection.
Of that, 8.5k is immortal data. So generational GC might speed this up even more.

25 November 2023
----------------

I've added a cryptographically-secure pseudo-random number generator.
I'd been befuddled by the wide variety of ostensibly "fast" PRNGs,
but then I ran across this nice article wherein the author argues
we should just use a cryptographically-secure generator for everything.
There is no *significant* performance advantage to the unsecure generators,
and there *are* significant problems. So I checked out a few options and
settled on implementing ChaCha20 as a random bit generator.
I followed `RFC 7593 <https://datatracker.ietf.org/doc/rfc7539/>`_.
The standard test vectors now run when you start the VM without any arguments.

Incidentally, this means Sophie's VM now has a platform dependency and an
external linked library on Windows for the entropy API. I'm pleased to say
I've worked out how to get ``cmake`` to cooperate with this. (On Linux/Mac,
it reads from ``/dev/urandom``.)

Also, I realized a reason for the surprisingly-large heap in the 2-3 tree test:
Snapped thunks still darken their captures during collection!
A quick & dirty patch to blank the extra captures cut the memory usage
by a factor ranging from three to six in different phases of the program.
(It announces many collections because I gave it a much longer text to work with.)
Problem is the Q&D solution also slows things down again:
Thunk-ridden ``fib(39)`` is up to 14 seconds.
I'll replace it with something nicer soon.

26 November 2023
----------------

I implemented a much nicer alternative to yesterday's Q&D hack.
The garbage collector now aggressively prunes snapped thunks out of existence:
Any ``Value`` that points to one gets the computed result in its place.
And just in case, forcing a thunk now changes the object header to one
which only darkens the result slot. (The rest of the closure is unreachable anyway.)
Heaps remain small and net performance is quite respectable:
The 2-3 tree demo maxes out well below 50k and the thunk-ful Fibonacci takes
about 12.8 seconds on a good run.

It surprised me, but the object-header tweak yields a (small, but consistent) improvement.
I've convinced myself that *every* snapped thunk gets pruned, so the only explanation
that makes a great deal of sense is the vagaries of code layout among cache lines.

27 November 2023
----------------

I have begun the ground-work for getting SDL bindings into the Sophie VM.
The first step was I've added a finalization queue. At least in theory,
Sophie's GC can now make sure resources get released before they leak.
I realized while making it that it's also perfect for file handles and the like.
Of course the proper thing is still to release resources overtly when they're
no longer relevant to the program's future, but the GC can act as a stopgap.

    SDL does a lot of its own allocation (presumably on the ``malloc`` heap) and
    expects to be told when to destroy/free those resources with calls to functions
    like ``SDL_FreeSurface`` and ``SDL_DestroyWindow``.
 
The basic concept is quite simple: The ``GC_Kind`` structure now has a field
for how to finalize an object. Just before the end of a collection, the GC
now scans the finalization queue: White objects on that list get finalized.
(Broken hearts get healed.) The finalizer is not allowed to allocate on the
GC heap (because a collection is still in progress) but that should be fine.

I have also started on adding the SDL-related system-actors into ``native.c``.
Ideally this would load the SDL library on demand, but that's not today's quest.

28 November 2023
----------------

Add https://dl.acm.org/doi/pdf/10.1145/191081.191117 to the bibliography.
*Optimizing Multi-Method Dispatch Using Compressed Dispatch Tables.*
It will be some time before this is top-of-mind, but there is is.

29 November 2023
----------------

Easy project today. Henceforth the global table is property of the compiler,
not the VM. And the compiler disposes of the global table when it's finished.
Moreover, the compiler removes itself from the set of GC root-sources.
This drops over 9k worth of useless data out of the heap after the first collection.
Interesting side effect: The Fibonacci benchmark now has a working set of 824 bytes only,
so the adaptive heap scaling gives it a much smaller heap. With that, it still ran
just a hair faster than before. Then I doubled the minimum-heap size to 32k.
Now it's consistently under 12.5 seconds. With a gigantic heap it still stays above 12 seconds,
which puts a bound on how much faster the GC can go.

30 November 2023
----------------

Tired of "compiler" meaning two things.
You know that thing in the VM which reads almost-bytecode and translates it into actually-bytecode?
"Assemble" is a better description of that than "compile".
From now on it's called "assembler" instead of "compiler".
All relevant C source code is changed to match.

December 2023
^^^^^^^^^^^^^

1 December 2023
---------------

Today I experimented a bit with bringing some SDL stuff to life inside the VM.
I've realized I will have to address some FFI design questions.
Native code needs a way to construct Sophie data and/or invoke Sophie code directly.
In particular the SDL layer will need a fairly rich vocabulary of bits and bobs.

My current plan is to exploit FFI linkage directives.
Perhaps I add an assembler directive to attempt an FFI linkage.
This could appear as a step after all the global functions are defined,
but before the ``begin:`` block's code.
In principle, it just needs to push the linkage symbols on the stack,
then the string representing the foreign-import,
and then call some special magic function responsible for building linkages.

It probably makes sense to do this before the VM proper starts up, just to eliminate confusion.
Maybe a special assembling-word like "FFI" introduces such a thing.

For now, presumably there would be a table of ``init_FOO`` functions responsible for
activating specific feature sets. That will most likely mean:

* Copying values from the stack into a private stash.
* Calling ``gc_install_roots`` with something to darken said stash.

There's one more aspect to the FFI which is yet to be resolved,
which is the matter of putting foreign symbols into a proper namespace.
Right now I'm sort of cheating by not mangling foreign names.
That can wait, but eventually the namespace information ought to fall
under control of the assembler module.

Anyway, that's enough rambling for one night. 

2 December 2023
---------------

It's ALIVE! (Sort of: The mouse-print demo *partially* works.)

The VM's game-adapter now dispatches mouse motion events in much the same way as the Python version does.
It was a minor head-scratcher to build Sophie data structures corresponding to SDL events.
The main idea behind my solution is to pass record constructors as FFI linkage parameters.
I prototyped that in Python first by adjusting the Python version of the game-adapter.

The intermediate language now has a way to instruct the assembler to invoke an FFI linkage.
It looks up the module's name in a table of native initializer functions (population one, *game-adapter*) 
and then invokes that function, which is expected to return ``BOOL_VAL(true)`` if all went well.

I also decided on an easier way to deal with the linkage GC problem:
Do not pop the linkage parameters off the stack after the native initializer runs.
That way, the native module can simply preserve a pointer into the stack.

By the way, mouse movement events in PyGame have the state of the buttons,
but SDL does not expose that directly in its movement event structure.

3 December 2023
---------------

I thought I'd work on adding complex-number arithmetic by way of operator-overloading.
So of course one needs a suitable application for complex numbers.
The obvious plan is to render the Mandelbrot set. And before I worry about new features,
I should at least be confident in a version that works with the current feature set.
So I wrote a Mandelbrot set plotter for text mode. (Find it under the mathematical examples.)
It works great (if a bit slow) on the tree-walking interpreter,
assuming you make the console big enough. Naturally, I thought to run it on the VM.

The compiler needed a few small repairs after some adjustments to the AST structure.
The VM also got a ``SKIP`` instruction, which does something unintuitive:
It pushes the (internal) nil value onto the stack.
Why? Well, there will no-doubt be a ``PERFORM`` instruction coming,
which will expect to pop an *action*. The VM treats ``NIL_VAL`` as the empty action.

The Mandelbrot program then managed to hit the VM's recursion depth limit of 64 frames.
I doubled that number (which made the program work) but right now that also doubles the total size of the stack.
I have some ideas how to improve that state of affairs (and it should be improved) but it's not the whole solution.

The *reason* the Mandelbrot program recurred so deeply is this function here::

    display(output, pic) = case pic of
        nil -> skip;
        cons -> do
            output!echo(pic.head);
            output!echo[EOL];
            display(output, pic.tail);  # This is a tail-call.
        end;
    esac;

In this case, ``pic`` is a list of 70 items, so this function goes 70 entries deep on the call stack.
I have an idea how to fix this properly, but it's too late to worry about it tonight.

7 December 2023
---------------

Pearl Harbor Day. (Go look it up.)

I want do-blocks to have proper tail recursion.
This is *almost* trivial: Just put an ``EXEC`` after the last step, right? Wrong!
There is one super-subtle problem with that.

Right now compiling a "statement" in a do-block works like this:

1. Evaluate an expression, thus placing an "action" at the top of the stack.
2. Emit a ``PERFORM`` instruction.

The job of the ``PERFORM`` instruction is to cause the given action to actually happen.
There are these kinds of action:

* ``VAL_NIL`` is the empty action.
* ``VAL_CLOSURE`` is presumed to be another do-block to run (recursively and synchronously).
* ``VAL_MESSAGE`` is a fully-specified message ready for delivery to the message queue.
* ``VAL_BOUND`` is the weird case.
  If ``PERFORM`` gets hold of it,
  then it means the message takes no arguments and should go to the message queue as-is.

It's easy to see how the ``EXEC`` instruction can do the right thing for the first three cases.
But in the case of ``VAL_BOUND`` we have a problem.
Consider a pure function that constructs a message.
It must not *send* that message, because sending a message is impure.
But it ends by pushing a ``VAL_BOUND`` and then issuing an ``EXEC`` instruction.
When ``EXEC`` is the last step of evaluating a pure expression in tail position,
the correct operational semantic for a ``VAL_BOUND`` is thus to combine it with arguments.

To correctly eliminate tail-calls from do-blocks, there are two options.

1. Make the ``EXEC`` instruction sensitive to the *arity* of a ``VAL_BOUND``.
2. Make a new instruction specific for the end of a do-block.

I've chosen to go with the second option, along with a bit of refactoring the tail-call code path.
As a result, the ``run`` function in the VM is now *officially* spaghetti code:
It has ``goto`` instructions that cross paths.
I never thought spaghetti code would be this delicious! 

Anyway, that's a wrap for this night's hack.

8 December 2023
---------------

I thought to test the finalizer mechanism by adding a finalizer for ``Function`` structures.
This makes sense, because function-objects do reference the ``malloc`` heap
for their ``Chunk`` structure: The VM could call ``freeChunk(...)`` and reclaim the space.

It worked perfectly the first time.
It was a bit confusing to watch because there several function-objects with identical names,
but they turned out to represent sub-expression thunks. (I'd forgotten this factoid.)

For now, I'll condition this behavior on running in the debug build, though.
Each thing in the finalization queue adds cycles to garbage collection,
and there's little if any benefit from releasing that miniscule portion
of the ``malloc`` heap leaked when ``Function`` structures become unreachable.

The main benefit is confidence that it will also work when applied to SDL structure proxies.

10 December 2023
----------------

The compiler no longer puts do-blocks in thunks.
I also spent way too long fighting with Python multi-threading issues in the reference run-time,
but I think that's finally sorted out. Mostly.

15 December 2023
----------------

I worked on the VM's game adapter. It:

* Respects the requested window size and frame rate.
* Has a suitably accurate frame-rate limiter that compensates for scheduling jitter.
* Colors the window using an ``SDL_Renderer``, which seems to be how the cool kids do accelerated graphics.
* Properly garbage-collects and finalizes the display window object.
* Dispatches mouse button events to the Sophie program.

Probably the next step will be actual graphics.
I'll have to sleep on that.

16 December 2023
----------------

Wow! It's been precisely three months since starting this harebrained project.
It's time for a retrospective:

* A surprising amount works.
* There is infinity left to do.

-----

The graphics display problem highlights some tedium in bridging the gap between C and Sophie.
I expect I'll end up creating a "display proxy" actor with native methods aimed at rendering things.
It's all about reading data (not composing it) so the native methods can take advantage of known layout.
But there's a fair bit to know, and there will be ever more as the ``pic`` type gains
cases to cover more graphics primitives.

As I move forward with this, I begin to see systematic repetition.
(That's one sign of an incomplete design.)
Specifically, the "system actors" take a bit of ritual to set up.
It's not too crazy for now, but it might soon merit further attention.
What about hybrid actors with some native methods and some Sophie ones?
Native *procedures* offer a work-around, but native *methods* might be more clear.
They would need:

* Some way to hook these up at assembly-time.
* Either careful agreement on data layout or else some sort of dynamic linkage.

There is always a risk of mis-categorized data when crossing the Sophie-C barrier.
Something to make the FFI self-check at start-up might be nice.

-----

Progress achieved: The game layer emits tick events with a display-proxy actor as argument.
This actor responds to "draw" events -- not quite yet by drawing, but it prints ``Draw `` to the console at least.
Maybe next time I'll try interpreting ``list[pic]`` things.

17 December 2023
----------------

https://www.cs.rochester.edu/~scott/papers/1996_PODC_queues.pdf
joins the bibliography. I'm nowhere near implementing threads just yet,
but when the day comes, a good set of queues will be important.

Today I got the ``fill`` operation working in the game layer.
Now the mouse-print demo has the green background I'm used to seeing.
In the process, I added a simple depth-first procedure to force a value and,
if that value is a record, its fields recursively, thus to remove all thunks.
This simplifies the code for the graphics messages.
I thought whether that ought to happen in the the bit that enqueues messages.
The problem is that the longest path would need to fit on the stack,
which would probably break the "algorithm" demo.

I want the contents of messages to be fully de-thunked for a couple reasons:

* If some actor is composing expensive messages,
  the costs should remain on the actor's own thread rather than
  becoming a synchronous computation on what might be a U/I thread.
* Regardless, thunks in messages represent a lost opportunity for parallel computing.

Given experience with the console, the turtle-graphics, and the game layer,
I'm seeing a common pattern: I tend to use lists quite a bit.
I may end up wanting to *stream* long messages from an actor.

This got weird.

24 December 2023
----------------

Made some progress toward being able to compile and use user-defined actors with the VM.
It's not complete yet, but at least it is no longer a crash bug.
The unit tests now also run all the examples through the translator.

The assembler now uses a specific delimiter to tell when global functions are done.
The first element of the ``begin:`` block for the mouse-chaser example was a do-block.
These compile as functions inline.
But the assembler considers the initial consecutive sequence of functions as all belonging to the global scope.
This had me flummoxed for longer than I'd care to admit chasing down the weird consequence of a stack underflow:
The first VM instruction to execute was consuming the wrong thing.

This convinces me that it's time the assembler did its own stack analysis on functions.
(This would probably prevent similar problems in the future.)

27 December 2023
----------------

I briefly had Sophie emitting pseudo-assembler for user-defined actors,
but I realized there was a distinct problem: Assignment.
Specifically, I'd like to compile assignment inline rather than
making it have to be like a thunk. But that would break assumptions
about how to compile ``do``-blocks.
After a bit of chat on the programming-languages discord,
I decided to change the translator to use richer context and exploit polymorphism to do it.
This will take more time than I can put to it in one sitting, so no commit tonight. 

28 December 2023
----------------

The new context-sensitive compiler architecture successfully compiles all the examples,
and more sensibly than before. Everything that *did* run before, runs again.
User-defined actors still don't load into the VM, but that will change soon enough.
The point of this change is realized: The compiler now recognizes four contexts that
each compile interesting bits differently.
That opens more ways for the translator to be incomplete, and I'm sure it is,
but at this point holes should be easy to patch.

More of the work that once seemed the job of a translator's tree-walk is percolating
down to the per-scope classes. That suggests a natural dividing line.

29 December 2023 - A Milestone!
-------------------------------

At long last, user-defined actors work in the VM!

*Also, I spent way too many hours debugging this.*
The most painful part came from a situation where the compiler
generated wrong pseudo-assembler code *at the same time as*
the VM mistreated the newest opcodes.

To be clear, this is not something unit-tests would have caught.
The problem was not ever that the code didn't match the spec.
The problem was a bad spec in the first place,
because I missed some subtle points in the design.
The symptoms resulted from the *interaction* of disparate parts.
Only the integration tests pointed out the flaws in my earlier thinking.

Side note: I've dropped several of the value-type tags
in favor of expanding the powers of the ``GC_Kind`` structure.
I figure this will eventually help with NaN-boxing.

30 December 2023
----------------

I took a little while to bring the game module closer to feature parity with the Python version.
The VM can now run the ``mouse.sg`` demo that keeps cross-hairs on the mouse as it moves.
But now I have all these questions about designing a suitable data type for rendering screen images.
It turns out SDL uses a stateful model for current drawing color, but the corresponding PyGame
adaptation (from which I started) requires you to pass the color along with each drawing primitive.

I also get the sense I'll soon want to attack threading.
SDL helpfully provides a cross-platform thread subsystem.
I wonder if it will be up to the task.

31 December 2023
----------------

Just a small change before the New Year:
Constructing a message now forces all the arguments deeply.
This means:

* Built-in actors (e.g. the game layer) don't need to worry about thunks.
* The heaps get a bigger in the short run.
* There's more incentive to do something about generational GC and threading.

1 January 2024
--------------

I have run into a practical problem.
This new "force-deeply" thing can easily overflow the C stack, which runs counter to my goals.
The short-term solution is to revert the change, which I have done.
Eventually I must find a something better.
It may well turn out to interact with the garbage collector.
More about that in a separate document.

2 January 2024
--------------

I have decided to implement NaN-boxing and see how it affects things.
There's a plan in a :doc:`neighboring document <nanbox>`.

3 January 2024
--------------

NaN-boxing begins.

* ``VAL_FN`` is gone, replaced with a test on the GC kind field.
* ``VAL_NIL`` and ``VAL_BOOL`` are gone, with ``VAL_ENUM`` moving into slot zero in the enumeration.
* ``NIL_VAL`` becomes ``FALSE_VAL``, defined as ``BOOL_VAL(false)``.

The change hit a snag:
The table implementation relied on being able to return ``NIL_VAL`` to communicate the absence of a key,
but now I've taken that away. Usages include:

* assembler.c in ``parse_ffi_init``: This usage relies on the front-end to provide only valid keys.
* assembler.c in ``snap_global_pointers``: This does the same, but explicitly checks for absence.
* ffi.c in ``ffi_find_module``: This delegates upward, but the one caller clearly expects the key.
* vm.c in the ``OP_FIELD`` case of ``run``: This is using the look-up to find a field offset.
* actor.c in ``bind_method_by_name`` looks up a message -- presumably the type checker's done its job?
  There is definitely code in the type checker to check that only valid messages are passed,
  so if that code works then this look-up is bound to succeed.
* table.c in ``table_get_from_C`` delegates up:
  * All usages are in vm.c in ``vm_capture_preamble_specials`` looking up things in the preamble.

Therefore, as of right now, a failed table look-up is always grounds for unceremonious termination.
I'll just move that fact into the ``tableGet`` function.

Also, since ``NIL_VAL`` has gone away, the test for a snapped thunk now checks the thunk's kind.
(Snapping it, changes the kind.) This may improve GC slightly but it slows the thunk-ful Fibonacci benchmark about 10%.
I saw a similar slow-down the last time I tried that, but for the moment there's no way around it.
I attribute this to memory bandwidth, as previously it was possible to tell a snapped thunk
by looking at the maybe-result. I may change this back eventually.

| Thunkless: 5.7 seconds
| Thunk-ful: 13.8 seconds

I'll go ahead and commit this before continuing...

4 January 2024
--------------

NaN-Boxing is complete. Fibonacci benchmark:

| Thunkless: 4.7 seconds
| Thunk-ful: 10.0 seconds

These are by far the fastest times to date.

I brought ``NIL_VAL`` back in part to experiment with the ``DID_SNAP`` test on thunks.
With NaN-boxing it's about equally fast either way.

