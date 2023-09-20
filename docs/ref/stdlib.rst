Standard Library
####################

    Obviously a work in progress...

.. contents::
    :local:
    :depth: 2

Intrinsic Types
===================

Predefined type names include ``flag``, ``number``, ``string``, and ``list``.

``flag``:
    The Boolean truth values are called ``yes`` and ``no``.

``number``:
    In the Python-hosted implementation, ``number`` is anything Python treats as a number,
    even including complex numbers. The future bytecoded implementation will probably go with
    all double-precision floating point until there's a demonstrated need for the semantics
    associated with binary integers.

``string``:
    These are unicode. Or perhaps UTF8-encoded on the VM. We'll see.
    At some point I'll end up distinguishing text from binary data.
    That day is not today.

``list``:
    That last has the pre-defined constructor ``cons``, which takes fields ``head`` and ``tail``.
    The implementation of explicit lists like ``[this, that, the, other]`` is in terms of ``cons``.


Intrinsic Functions
======================

You can find `the standard preamble <https://github.com/kjosib/sophie/blob/main/sophie/sys/preamble.sg>`_.

Predefined functions include:

Mathematical Functions
------------------------

* ``id(x)``: Return ``x`` as-is.
* ``int(a:number) : number``: Convert floating-point value to integer.
* ``sum(xs)``: add all the numbers in the given list and return their sum, or a if the list is empty.
* product(xs): The product of a list of numbers, or 1 if that list is empty.


* Python's math library of functions and constants are also installed, with two caveats:
  * ``log`` becomes two functions: ``log(x)`` and ``log_base(x, b)`` because Sophie does not deal in optional arguments.
  * ``hypot`` is re-implemented in Sophie because the python version takes a variable number of arguments. The Sophie version takes a list of numbers.


List Functions
----------------

* ``any(xs)``: True when at least one member of an input list evaluates to true. (Otherwise false.)
* ``all(xs)``: False when at least one member of an input list evaluates to false. (Otherwise true.)
* ``map(fn, xs)``: Produce a list by applying ``fn`` to all members of ``xs``.
* ``filter(predicate, xs)``: Returns a list composed of those elements from ``fn`` such that ``predicate(fn)``.
* ``reduce(fn, a, xs)``: Produce a single element by applying ``fn`` repeatedly to rolling pairs of arguments:
  first ``a`` and the head of ``xs``, then that result with the next entry in ``xs``, and so forth.
  If ``xs`` is empty, it returns ``a`` without ever calling ``fn``.
* ``expand`` is not currently a thing. When it becomes a thing, this page will update.
* ``cat(xs, ys)``: Return a list composed of the elements of ``xs`` followed by those of ``ys``.
* ``flat(xss)``: Given a list of lists, return a single list composed of the elements of each input list in sequence.
* ``take(n, xs)``: return a list composed of the first ``n`` elements of ``xs``.
* ``drop(n, xs)``: return the remainder of list ``xs`` after skipping the first ``n`` elements.


Text-String Functions
-----------------------

* ``chr(a:number) -> string``: Produce the given numbered unicode code-point as a string.
* ``str(a:number) -> string``: Format a number as a string in the most typical way.
* ``len``:
* ``ord``:
* ``mid : (a:string, offset, length) : string;``: Extract a substring 
* ``val : (a:string) : maybe[number];``: parse a string into a number - maybe.
* ``strcat : (a:string, b:string) : string;``: Concatenate a pair of strings.
* ``join(ss : list[string]) : string``: Concatenate an entire list of strings.
* ``interleave(x:string, ys:list[string])``: Construct the string of ``ys`` concatenated but with ``x`` between them.
* ``each_chr(s:string) : list[string]``: The list of characters drawn from a string. Characters are, for now, just short strings.
* ``EOL``: Equivalent to ``chr(10)`` because it's handy to have a nice name for this.


The Console
====================

The standard preamble defines an actor called ``console`` (lower-case) with this interface::

    Console is agent:
        echo(list[string]);
        read(!(string));
        random(!(number));
    end;

* ``echo`` means to print each string to the console with no space between.
* ``read`` means to await keyboard input, ending with [return] or [enter], and send it to the parameter.
* ``random`` means to send a number chosen at random, at least zero and less than 1, to its parameter.


Turtle Graphics
=================

To use Sophie's turtle-graphics, import the ``sys."turtle"`` module.
It offers the designated type ``drawing`` which represents the runtime presenting a list of turtle-steps as a picture::

    drawing is (steps: list[turtle_step]);

Put your drawings as expressions in the ``begin:``-block.

The type of ``turtle_step`` is defined as::

    turtle_step is case:
        forward(distance:number);
        backward(distance:number);
        right(angle:number);
        left(angle:number);
        goto(x:number, y:number);
        setheading(angle:number);
        home;
        pendown;
        penup;
        color(color:string);
        pensize(width:number);
        showturtle;
        hideturtle;
    esac;

Distances are expressed in pixels. Angles are in degrees, or 360ths of a complete rotation.
The ``x`` and ``y`` coordinates are Cartesian from the lower left of the image.
By default the turtle starts out centered on the drawing and facing the top of the screen.

.. note:: This is not what you'll build games on. It's part proof-of-concept and part fun-game in itself.

Game/Graphics/Sound/SDL
=========================

Sophie's SDL integration is through module ``sys."game"``.
Details are still in flux, so it's best to have a look.

Data Structures and Algorithms
================================

Sophie offers a balanced-tree implementation at ``sys."tree"``.
That makes a nice ordered dictionary or set.

The interface types are::

    Tree[K,V] is ... ;
    Item[K,V] is (key: K, value:V);
    Removed[K,V] is (item:maybe[Item[K,V]], rest:Tree[K,V]);

Exported functions include::

    new_tree:Tree
    is_empty(T:Tree):flag
    search(T:Tree, key) : maybe 
    in_order(T:Tree) : list[Item]
    assign(tree:Tree, key, value) : Tree
    first(T:Tree) : maybe[Item]
    last(T:Tree) : maybe[Item]
    shift(root:Tree) : Removed
    delete(root:Tree[K,V], key) : Removed

The type-signatures alone convey most of what you need to know.
A few specifics:

* ``search`` : That's a maybe-value, not a maybe-item.
* ``shift`` : Removes the first element, if there is one.
* ``delete`` : If the key is not present, you get ``Removed(nope, root)``.

You can find `an example <https://github.com/kjosib/sophie/blob/main/examples/algorithm.sg>`_.


