# Change Log

Read this to get a general idea of what's new and nontrivial.

## December 2024

* 20 December: Numerous changes since the last report:
  * Type-checker is rewritten into a sub-package of its own: Similar concept of operation, but simpler and more flexible.
  * Tree-walking runtime is migrated into a package of its own, and better organized.
  * Pygame adapter no longer hogs the main thread, so exceptions in other code *finally* promptly
    shut down the scheduler and get displayed without waiting for the user to close the game window.
  * Updating an actor's field currently needs a bit of work. This relates to a planned change in how Sophie
    will handle the type of an actor: It will become more like how records work. But that's for the next update.
* 3 December: Deep into a complete re-build of the type-checker.
  There will be less predefined magic.

## November 2024

* 29 November: The grammar is better-organized and reads more like a narrative tour of the language.
  Also, the notion of an `export:` section is dropped from the language -- for now.
* 28 November: The resolver is completely restructured and much simplified:
    * Three passes (`WordDefiner`, `WordResolver`, and `AliasChecker`) merge to become `Resolver`, dropping lots of code and running faster.
    * Types and terms now have distinct name spaces, which simplifies a lot of things.
    * By all rights, the new version should consume less time and space.
* 27 November: Switched to Python 3.12 (from 3.9).
* 25 November: *Translation to IL for the VM* is no longer considered *experimental*. It gets its own flag `-t` on the command line.

## October 2024

* 29 October: Force-push entire commit history with corrected meta-data.
* 27 October: Assorted code clean-ups, better names, etc.
* 15 October: Change `agent` and `interface` to `actor` and `role`, respectively.
* 3 October: Fix author name.

## Summer of 2024

* 20 September: Labs drawn and first dose of HRT. Down 50 lbs from peak in June.
* 19 September: Finally saw endocrinologist.
* 27 August: Endocrinologist hospitalized; pushed appointment. Parents stopped fighting me about being a girl.
* 30 July: Signed up for HRT. Should see endocrinologist on 28 August. Roller rink is much more fun in girl-mode.
* 28 July: Purse arrives.
* 24 July: Fem wallet arrives.
* 18 July: Out to everyone at work. HR system updated. Wearing dresses at all times and places.
* 11 July: Received first e-mail to preferred name.
* 5 July: Began laser hair removal. Came out to first colleague.
* 1 July: Got ears pierced.
* 30 June: Sleeping much better and waking refreshed. Lost interest in drinking and coffee. Eating right.
* 29 June: Yay! I'm a girl!
* 24 June: Ordered Programmer Socks.

## May 2024

* 10 May: Sophie's VM now has a *generational* garbage collector.
* 4 May: May the fourth be with you. Also, publish version 0.0.7.
* 3 May: Factored the 2d vector/math/trig out of `game.sg` into `2d.sg`.
  Also, the "Not Quite Pong" game now puts English on the ball based on
  where it strikes the paddle, exploiting more `2d` things.
* 1 May: "Not Quite Pong" game drops. (It's simplistic, but gets a point across.)
  Also, mouse button events now work in the VM.

## April 2024

* 30 April: Repair VM's message-passing behavior for new proc semantics.
* 28 April: Virtual stack-trace diagnostic is now nicer/smarter around type-case match expressions. 
* 27 April: Type-checker now copes with assigning actor members of variant type e.g. `list`.
  I have a sneaking suspicion the present method may not be *completely* sound,
  but I have a plan to fix the hole.
* 24 April: Within `cast` lists, you can now mention one actor while constructing the next.
  Declare-before-use applies, at least for now.
* 23 April: Various bugs and oversights fixed. 
* 22 April: Change compiler and VM to new procedure semantics. Some things got simpler.
* 17 April: Got the tree-walker fully working again with the new procedure semantics.
  (This includes turtle graphics and list displays, which had broken some time back.)
  All examples are updated to match. A program no longer returns a value.
* 16 April: IRS finally acknowledges payment. Retroactively, thank heavens.
* 15 April: Tax day. Also, functions and procedures are now completely distinct.
  The syntax and type checker are overhauled to understand this.
  (The tree-walker and compiler still need some work.)
* 14 April: Resolver now respects procedures subordinate to functions.
* 12 April: Decided to generalize method-syntax for global procedures and adjust semantics accordingly.
  The type system will soon distinguish *parametric* messages from *functions-returning* messages,
  creating a predictable *local* cost-model for high-order methods on actors. (Code to follow.)
* 8 April: I watched the Total Solar Eclipse with excellent weather and a great view,
  smack dab on the centerline of the path of totality,
  with a handful of excellent friends in the heart of Texas hill country.
* 4 April: Implemented snapshot semantics for actor member access. (Much code oddly simplified!)
  Syntax now always uses ``my foo`` instead of ``self.foo`` to refer to an actor's own private state.
* 3 April: I have decided on snapshot semantics for actor member access, with associated doc updates.
* Various and sundry bugs fixed, mainly relating to recent features. 

## March 2024

* 31 March: Added ``trim`` function as built-in.
* 29 March: Added ``split_lines`` function as built-in.
* 27 March: Operator overloading now also works in the VM. Version 0.0.6 is published.
* 24 March: Operator overloading works in the tree-walker.
* 5 March: Sophie gains anonymous-function expressions, a.k.a. lambda forms. They work everywhere.
* 3 March: The VM gets the `filesystem` actor built in, along with both methods.

## February 2024

* 21 February: The `<=>` three-way comparison operator now works in both the tree-walker and the VM.
  `tree` library is updated to use it.
  Also, start a change log and back-fill it since start of year based on commit history.
* 18 February: The tree-walk run-time now produces a proper stack-trace upon hitting an `absurd` situation. 
* 17 February: Function parameter type annotations can now mention type-aliases like `predicate`.  
* 10 February: Bump version number to `0.0.5` and post to PyPI.
* 8 February: Sophie gets a syntax-highlight extension for VS-Code, and thus becomes much nicer.
* 7 February: Put stack-traces innermost call last, which is evidently a better user experience. Improve demand analyzer.
* 5 February: Sophie gets a demand analyzer to infer strict parameters and eager expressions, yielding much faster VM code.
* 3 February: `filesystem` actor moves to standard preamble.


## January 2024

* 27 January: Tree-walker now handles tail-recursion suitably. Formal parameters may not be declared `strict`.
  These two changes enable tree-walker to run nontrivial programs and solve Advent-of-Code challenges.
* 25 January: Add a `filesystem` native-actor to tree-walker, for now just to read data files.
* 4 January: VM now uses NaN-boxing technique. Uses half the RAM and runs 20% faster.

