Text-String Functions
######################

.. contents::
    :local:
    :depth: 2

Predefined Constant Strings
============================

* ``EOL``: Equivalent to ``chr(10)`` because it's handy to have a nice name for this.

Conversion Functions
=====================

* ``chr(a:number) : string``: Produce the given numbered unicode code-point as a string.
* ``str(a:number) : string``: Format a number as a string in the most typical way.
* ``val(s:string) : maybe[number];``: parse a string into a number - maybe.


Examining Strings
==================

* ``len(s:string) : number``: Return the size of a string, as defined by the implementation.
* ``ord(s:string) : number``: Return the numeric value of the first item in the given string.
* ``each_chr(s:string) : list[string]``: The list of items drawn from a string, as strings.

.. note::
    A string "item" is a unicode code-point in the tree-walker implementation, or a byte in the VM.
    Eventually the VM should get a bit smarter about text encoding and distinguish code-points from bytes.

The next four items are planned but not yet implemented:

* ``ord_at(s:string, offset:number) : number``: Return the Unicode code-point at the given offset, or -1 if offset is invalid.
* ``byte_at(s:string, offset:number) : number``: Return the byte at the given offset, or -1 if offset is out of range.
* ``each_ord(s:string) : list[number]``: The list of code-points drawn from a string, as numbers.
* ``each_byte(s:string) : list[number]``: The list of bytes drawn from a string, as numbers.

Searching Strings
==================

By convention, the order of arguments for searching things is always *needle, haystack*.
If there is an offset, it comes first in the argument list.
If there is a replacement string, it comes last.

* ``find_string(needle, haystack) : maybe[number]``: Equivalent to ``find_string_at(0, needle, haystack)``
* ``find_string_at(offset, needle, haystack) : maybe[number]``: The offset of the first occurrence of the needle, if any.
* ``is_match_at(offset, needle, haystack) : flag``: tells whether the needle matches the haystack at that position.
* ``replace_first(needle, haystack, with) : string``: replaces the first instance of ``needle`` with ``with``. 
* ``replace_all(needle, haystack, with) : string``: replaces every instance of ``needle`` with ``with``. 

Composing Strings
==================

* ``mid : (a:string, offset, length) : string;``: Extract a substring.
* ``strcat : (a:string, b:string) : string;``: Concatenate a pair of strings.
* ``join(ss : list[string]) : string``: Concatenate an entire list of strings. (Runs in linear time.)
* ``interleave(x:string, ys:list[string])``: Construct the string of ``ys`` concatenated but with ``x`` between them.

* ``trim : (a:string) : string;``: Return a copy of ``a`` without leading or trailing whitespace.
* ``ltrim : (a:string) : string;``: Return a copy of ``a`` without leading whitespace.
* ``rtrim : (a:string) : string;``: Return a copy of ``a`` without trailing whitespace.


Implementation Caveat
======================
Strings in Sophie depend slightly on the implementation.
In the Python-based tree-walker, a Sophie string is backed by a Python string.
In the VM, it's backed by an array of bytes which is, by convention, normally encoded in UTF-8.
The internal string functions in the VM all either assume nothing or assume UTF-8. 

See also :doc:`../explain/string` for more details.

The ``join`` function has recently been made native so it can run in linear time.

