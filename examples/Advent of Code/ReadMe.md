# Advent of Code Solutions

[Advent of Code](https://adventofcode.com/about)
is a web site that annually poses a set of fun little programming puzzles themed in the guise of an Advent calendar.
By design, it does not depend on any particular programming language or technique.
Therefore, it makes perfect source material for trying out what it's like to program in a *new* language --
or motivating the work to bring a new language out of infancy and into childhood.

This folder contains **Sophie** solutions to some of the historical puzzles.
You can read the puzzle descriptions by constructing a URL of the form:

    https://adventofcode.com/2023/day/1

That puzzle in particular was the first AoC puzzle I attempted in Sophie.
It required some changes:

* This was the first time I had Sophie reading files from the file system,
  so I added a `filesystem` actor and a convenient `read_lines` message.
* The tree-walker finally eliminates tail-calls, solving the corresponding
  class of stack overflows. (The VM has always had a proper solution.)
* Sophie now supports a `strict` modifier for formal parameters.
  Judicious use of this feature prevents enormous recursive towers of
  thunks which then cannot fit on the stack to be evaluated.

Then I did 2015's day 1, which required much less new stuff.
Principally, I added a `read_file` message to `filesystem` because
this puzzle is not line-oriented. At that, everything just worked.

## Caveats

So far, support for Advent of Code is limited to the tree-walking interpreter.
The new `filesystem` actor and its corresponding native module
are not yet implemented in the VM. Furthermore, I've yet to update
the code generator to respect the `strict` modifier. 

At the time of this writing, Sophie's standard libraries are rather spartan.
I expect that after I have whole bunch of solutions,
that will be the time to refactor the good bits into system libraries.

I will update this document when these things change.
