Interlude: Seven Moving Parts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This might be a good point to pause and reflect.
You have seen functions and decision points.
In principle, that's enough to compute anything that can be computed.

The Holy Trinity of structured programming is *sequence, selection, and repetition*.
We're doing something even holier than structured, though.
We're doing *pure* functional programming with *call-by-need*.

So far, we've seen:

* Arithmetic and Logic.
* Selection among alternatives.
* Functional abstraction, by which we obtain sequence and repetition.

We've yet to tackle:

* Organizing information internal the program for proper access.
* Influencing the world, such as displaying something or writing to long-term storage: Output.
* Getting information from the outside world into the program: Input.
* Interconnecting sections of program written by different people at different times and places: a module system.
* The eventual plans for solving *big* problems with Sophie.
