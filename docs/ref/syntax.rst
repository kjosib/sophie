Language Syntax
###################

The primary authority is at `the literate grammar file <https://github.com/kjosib/sophie/blob/main/sophie/Sophie.md>`_
which -- despite reading mostly like a reference document -- is actually what the implementation uses internally.
(If you must know, it's input to `this system <https://pypi.org/project/booze-tools/>`_.)

Sophie is not exactly *block-structured:* module files have sections dedicated to:

* Exports
* Imports
* Type definitions
* Type assumptions
* Function and Actor definitions
* "Main-Program" Behavior

Every section is optional, but if it appears, it must appear in exactly that order.

Within each section but the last, there is no ordering constraint.
There is neither the need for, nor any concept of, *forward-declaration* of any kind.

