# Change Log

Read this to get a general idea of what's new and nontrivial.

## March 2024

* 3 Mar: The VM gets the `filesystem` actor built in, along with both methods.

## February 2024

* 21 Feb: The `<=>` three-way comparison operator now works in both the tree-walker and the VM.
  `tree` library is updated to use it.
  Also, start a change log and back-fill it since start of year based on commit history.
* 18 Feb: The tree-walk run-time now produces a proper stack-trace upon hitting an `absurd` situation. 
* 17 Feb: Function parameter type annotations can now mention type-aliases like `predicate`.  
* 10 Feb: Bump version number to `0.0.5` and post to PyPI.
* 8 Feb: Sophie gets a syntax-highlight extension for VS-Code, and thus becomes much nicer.
* 7 Feb: Put stack-traces innermost call last, which is evidently a better user experience. Improve demand analyzer.
* 5 Feb: Sophie gets a demand analyzer to infer strict parameters and eager expressions, yielding much faster VM code.
* 3 Feb: `filesystem` actor moves to standard preamble.


## January 2024

* 27 Jan: Tree-walker now handles tail-recursion suitably. Formal parameters may not be declared `strict`.
  These two changes enable tree-walker to run nontrivial programs and solve Advent-of-Code challenges.
* 25 Jan: Add a `filesystem` native-actor to tree-walker, for now just to read data files.
* 4 Jan: VM now uses NaN-boxing technique. Uses half the RAM and runs 20% faster.

