Standard Library
####################

    Obviously a work in progress...

.. contents::
    :local:
    :depth: 2

Intrinsic Functions
======================

You can find `the standard preamble <https://github.com/kjosib/sophie/blob/main/sophie/sys/preamble.sg>`_.

Predefined functions include:

Mathematical Functions
------------------------

* ``id(x)``: Return ``x`` as-is.
* ``int(a:number) : number``: Convert floating-point value to integer.
* ``sum(xs)``: add all the numbers in the given list and return their sum, or a if the list is empty.
* ``product(xs)``: The product of a list of numbers, or 1 if that list is empty.
* ``max(a,b)``: Return the larger of ``a`` and ``b``.
* ``min(a,b)``: Return the smaller of ``a`` and ``b``.

* Python's math library of functions and constants are also installed, with two caveats:
  * ``log`` becomes two functions: ``log(x)`` and ``log_base(x, b)`` because Sophie does not deal in optional arguments.
  * ``hypot`` is re-implemented in Sophie because the python version takes a variable number of arguments. The Sophie version takes a list of numbers.


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
    Removed[K,V] is (item:maybe[entry[K,V]], rest:Tree[K,V]);

It relies on the standard-preambly type ``entry``, given as::

    entry[K,V] is (key: K, value:V);

Exported functions include::

    new_tree:Tree
    tree_of(es:list[entry]):Tree
    is_empty(T:Tree):flag
    search(T:Tree, key) : maybe[entry]
    in_order(T:Tree) : list[entry]
    assign(tree:Tree, key, value) : Tree
    first(T:Tree) : maybe[entry]
    last(T:Tree) : maybe[entry]
    shift(root:Tree) : Removed
    delete(root:Tree[K,V], key) : Removed

The type-signatures alone convey most of what you need to know.
A few specifics:

* ``search`` : That's a maybe-value, not a maybe-item.
* ``shift`` : Removes the first element, if there is one.
* ``delete`` : If the key is not present, you get ``Removed(nope, root)``.

You can find `an example <https://github.com/kjosib/sophie/blob/main/examples/algorithm.sg>`_.


