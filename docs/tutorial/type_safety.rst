Apples, Oranges, and Mixing Them
=========================================

.. contents::
    :local:
    :depth: 3


Introducing the Type Checker
-----------------------------

One of Sophie's key features is something called *static type-safety*.
Before she runs any program, Sophie checks it carefully to make sure that
no part of the program can produce a value of the wrong type for what uses it.
By that I mean:

* Numbers are in places where numbers can go.
* Text strings are in places where text strings can go.
* Lists are in places where lists can go.
* And so on, including all the types you define in your own programs.

Try this bit of nonsense:

.. literalinclude:: ../../zoo/fail/type_check/num_plus_string.sg

When you try to run this nonsense::

    D:\GitHub\sophie>sophie zoo\fail\type_check\num_plus_string.sg
    Error while Checking Types: Needed number; got string.
    Excerpt from D:\GitHub\sophie\zoo\fail\type_check\num_plus_string.sg :
         5 :    add(a,b) = a + b;
                               ^ This has type 'string' but 'number' was expected.
         5 :    add(a,b) = a + b;
                ^^^ Called with a:number, b:string
         8 :    add(1, "one");
                ^^^ Called from here

Sophie worked out this addition of a number to text doesn't make any sense,
and so gave us fair notice that something is not right about how we're using that ``+`` sign.

This was a super-simple example, just to show the concept.
Sophie carries this same checking through any depth of functions and data structures.
This turns out to be a big help as your programs gets big:
It's easy to forget some relevant detail, but Sophie will remind you.

These particular messages may not be beautiful,
but I've tried to make them clear and informative.
In time Sophie will get better in this regard.

* Exercise:
    Try introducing some deliberate type-errors into the ``define_functions.sg`` example,
    such as taking the square of ``"hello"``, and see what sorts of messages Sophie generates.

.. note::
    There's a truism commonly repeated for languages with strict static typing:
    *If it compiles, it probably works.* That's the attraction, and in this author's
    experience it's worth the price of admission. However, do not mistake *type* safety
    for *program* safety. If you're running safety-critical systems (e.g. medical implants,
    nuclear power plants, avionics, or the brake pedal in a certain well-known automobile)
    then you need a *much* higher degree of quality assurance. But that's a rant for another day.

Checking Programs Without Running Them
---------------------------------------

You can ask Sophie to check your program without running it, using the ``-c`` option.
In that case, Sophie will list the inferred types of all the functions::

	D:\GitHub\sophie>sophie examples\tutorial\define_functions.sg -c
	Loading D:\GitHub\sophie\examples\tutorial\define_functions.sg
	2 >> double : (number) -> number
	2 >> square : (number) -> number
	2 >> area_of_rectangle : (number, number) -> number
	1 >> five : number

.. note:
    Um... actually... this is not exactly correct anymore.
    Right now, Sophie deduces the types of all the ``begin:`` expressions.
    This means working through the types of functions *as they actually get used* in your program.
    (Or else she prints an error message -- hopefully informative.)
    Per-function type read-outs *may* come back some day, but they're not a top priority right now.

Here we see the inferred types. The arrows mean "function".
For example, ``area_of_rectangle`` is a function from ``(number, number)`` to ``number``.
By contrast, ``five`` is just a number.

* Exercise:
	Check the types of all the examples.
	Does anything surprise you?

How to Influence Type-Checking
-------------------------------

.. note::
    This section is presently on ice. I have plans to bring it back to life in due time.
    Sophie continues to recognize the syntax, but she ignores it in favor of her own deductions.

If Sophie comes to surprising (or inadequate) conclusions about the types of your functions,
it's possible to add *type annotations* to make Sophie take your intentions into account.

For example, you could write::

	area_of_rectangle(length:number, width:number):number = length * width;

which means that the two parameters (``length`` and ``width``) both have type ``number``,
and so does the result of the function.
Sophie will still check that these assertions work with the function's body expression ``length * width``
rather than blindly take your word for things, but otherwise this can be a good way to narrow down the type
Sophie infers.

The simple types are ``string``, ``number``, and ``flag``. There are also some predefined types like ``list``.
In fact, ``list`` can take a parameter, as in ``list[number]`` or ``list[string]``.

* Later in this tutorial, a section will cover the rest of the syntax for type annotations in more detail.

Type annotations are all completely optional. You may annotate any combination of parameters,
return-types, or nothing at all and just let Sophie read your mind.
Type annotations are rarely necessary from Sophie's perspective,
but they can be a nice adjunct to explanatory comments, since they get checked automatically.

* Exercise:
    Try giving an incorrect type annotation to a function, and see what happens.
    For example, maybe you write ``double(x:flag) = x + x;`` and then call ``double(10)``


More Apples and More Oranges
------------------------------

* *Take a look at type-report and ``iterate_four_times`` specifically.*
* *Discuss the types of higher-order functions generally.*
