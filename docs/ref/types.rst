Types
######

.. contents::
    :local:
    :depth: 2

Intrinsic Types
===================

These types are not defined anywhere you can read.
They're just built into the lowest levels of the language.

``flag``
    The Boolean truth values are called ``yes`` and ``no``.

``number``
    In the Python-hosted implementation, ``number`` is anything Python treats as a number,
    even including complex numbers. The future bytecoded implementation will probably go with
    all double-precision floating point until there's a demonstrated need for the semantics
    associated with binary integers.

``string``
    These are unicode. Or perhaps UTF8-encoded on the VM. We'll see.
    At some point I'll end up distinguishing text from binary data.
    That day is not today.

Predefined Types
==================

These types are defined in the standard preamble.
They may as well be built in, for all anyone cares.

``list``
    Has two cases: ``nil`` is the empty list, while ``cons`` has fields ``head`` and ``tail``.
    The implementation of explicit lists like ``[this, that, the, other]`` is in terms of ``cons``.

``maybe``
    Can be either ``this(item)`` or ``nope``.
    Useful return type for functions that don't always have a meaningful answer.
    For example, a search function might not find what it's looking for.
    It can return ``maybe[found]`` for some type ``found``.

``order``
    Consists of the enumeration ``less``, ``same``, ``more``.
    The purpose is a return-value type for functions that compare totally-ordered things.
    Eventually a spaceship operator ``<?>`` will return this type once operator overloading drops.

``pair``
    A simple record consisting of fields ``fst`` and ``snd``.
    There is no required relation between their types.

``Console``
    The ``role`` of the built-in ``console`` actor.
    It defines methods ``echo``, ``read``, and ``random``.
    Eventually it will deserve a section of its own.

And soon:

``FileSystem``
    The ``role`` of the built-in ``filesystem`` actor.
    This is presently in a separate module, but I plan to make it part of the standard preamble.

Types You Compose
===================

You can express a variety of compound types anywhere in a type signature.

Types by Name
    ``flag`` and ``list`` are both perfectly good type names.
    In this case, ``list`` is generic: You've not specified what sort of item the list contains.

Names Made Concrete
    ``list[number]`` says that the list is specifically a list of numbers.
    ``pair[apple, orange]`` suggests that you won't be giving a meaningful comparison between ``.fst`` and ``.snd``.

Functions
    Use an arrow and parenthesis to compose a function type.
    For example, ``(string, number, number) -> string`` describes a function that converts
    a string and two numbers to a new string.

Message-handler Types
    Use the exclamation point and parenthesis to compose a message-handler type.
    (This can refer either to a plain procedure or a method bound to an actor.)
    For example, ``!(list[string]))`` is the type of a message-handler that takes
    a list of strings. The type ``!`` is that of a message-handler that takes no parameters.

The Don't-Care Type
    You can use a question mark to indicate a type you don't care about.
    ``pair[?, flag]`` says the ``.snd`` element of the pair must be a ``flag``,
    but we leave unspecified what type the ``.fst`` is.

Ad-Hoc Type Variables
    While defining actual functions, you may optionally annotate the parameter types and return type.
    If these types are generic, you can either use ``?`` to let Sophie figure it out,
    or your can specifically tie type positions together with ``?x`` where ``x`` can be any
    otherwise-unused type name. For example::

        define:
        map( fn:(?a)->?b, xs:list[?a] ) : list[?b] =
    
    This declares that function ``map`` ... does exactly what it does, at least in the domain of types.
    (The rest of the implementation is left as an exercise, or you can look in the standard preamble.)

Types You Define
===================

To define your own types, include a ``type:`` section in your module.

Record Types
    For example::

        my_record is (field_1:type_1, field_2:type_2);
    
    You can have anywhere from 1 to 255 fields.
    Each field must declare its type, even if this seems redundant.

    The word ``my_record`` additionally becomes a constructor,
    which behaves like a function that produces records of type ``my_record``.

Generic Types
    After the name of a type, include type-variables in square brackets.
    For example::

        my_generic_record[X] is (alpha:X, beta:X, gamma:number);

    Now you can make any ``my_generic_record`` you like,
    as long as its ``alpha`` and ``beta`` fields have the same type as each other.

    ::

        Entry[K, V] is (key:K, value:V);

    You can have as many type parameters as you need.

Tagged Variants
    For example::

        list[x] is CASE:
             nil;
             cons(head:x, tail:list[x]);
        ESAC;

    This is the actual definition of ``list`` in the standard preamble.
    Because the ``tail`` has type ``list[x]``, this means by induction that a list contains
    all the same type of elements.

    You can have up to 255 cases.
    Each case must either be a record or, as in the case of ``nil``, just an identifier.
    In this case ``nil`` is a constant value standing for itself,
    and ``cons`` is a two-argument constructor.

    Notice that ``nil`` does not mention parameter ``x``.
    Therefore, the ``nil`` value is interchangeable among different kinds of lists.
    However, you're unlikely to find inventive uses for this fact.

    You can work with the specific components of a tagged-variant using ``CASE`` ... ``OF`` syntax::

        map(fn, xs) = case xs of
            nil -> nil;
            cons -> cons(fn(xs.head), map(fn, xs.tail));
        esac;

Alias Types
    You can give a name to any simple type. For example, ``predicate[x] is (x)->flag``
    gives the name ``predicate`` to mean a function (of one argument) that returns a ``flag``.
    Alias types do not make constructors.

Role Types
    This gives a type which some actor can implement.
    At the moment, it's mostly useful with the foreign function interface,
    because actor definitions in the ``define:`` section implicitly define their own type.
    Example::

        Console is role:
            echo(list[string]);
            read(!(string));
            random(!(number));
        end;

    This says that anything satisfying the ``Console`` interface can accept the three
    messages ``echo``, ``read``, and ``random``, with message signatures as given.


    

