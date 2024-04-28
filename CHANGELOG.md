# Change Log

Read this to get a general idea of what's new and nontrivial.

## April 2024

* 27 April: Type-checker now copes with assigning actor members of variant type e.g. `list`.
  I have a sneaking suspicion the present method may not be *completely* sound,
  but I have a plan to fix the hole.
* 24 April: Within `cast` lists, you can now mention one actor while constructing the next.
  Declare-before-use applies, at least for now.
* 23 April: Various bugs and oversights fixed. 
* 22 April: Change compiler and VM to new procedure semantics. Some thing get simpler.
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

