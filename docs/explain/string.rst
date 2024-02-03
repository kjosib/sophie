What even is a "string"?
=========================

Naively, a string is a sequence of text elements, or characters.
But that just moves the goal posts: What even is a "character"?
In the days before Unicode, you could freely assume that a byte held a character and a character took one byte,
so for all anyone cared bytes and characters were interchangeable. That wasn't actually true if you needed
to process Asian character sets, so for a while there were "wide characters" which combined into "wide strings".
That was a partial solution, but it didn't really solve the problem of a universal character set.
And then the Unicode consortium swooped in to save the day...

Originally Unicode was supposed to be a 16-bit universal character set.

* So a string is a sequence of 16-bit characters, right?

Nope. Unicode quickly changed to be 17 planes of 16-bits per plane, so a minimum of 21 bits if you're still counting.
(God only knows if that will be enough at the rate they keep on adding emoji, but I digress.)

For backwards compatibility with 16-bit text systems, Unicode added a concept of "surrogate pair",
which allows two 16-bit quantities to specify a code-point above the original 16-bit "Basic Multilingual Plane".
Each of these quantities contributes 10 bits (for a total of 20 bits) and implicitly does not overlap the BMP.
(That's how we get 17 planes.) In this encoding, most characters take two bytes, but some take four.
But also for compact encoding of non-Asian text, there is UTF-8, which takes anywhere from 1-3 bytes per code-point.

* So a string is a sequence of Unicode code-points, right?

Well, maybe. Some code-points don't actually make any sense on their own, or at the beginning of a text.
There are complicated rules about "extended grapheme clusters",
which are *extended* only because the original definition of "grapheme clusters"
apparently didn't cut the mustard.

* So a string is a sequence of extended grapheme clusters, right?

Not so fast! Some people want to make "cursed text", which is regular text that has all manner of
extra diacritics sprinkled in, so that it makes the font renderer go bananas.
If you want to do this, then you need to work at the level of the individual code-point.

* So we're hosed, right? There's no such thing as a character anymore?

Clearly, Sophie needs an answer. This is that answer:

In Sophie, a string is a blob of data which normally may be interpreted as a sequence of Unicode code points.
However, for practical reasons the exact representation of that data may differ between implementations.
In the tree-walker, substring indices refer to code-point indices.
In the VM, substring indices refer to byte-positions within the encoded form of the text,
whether that encoding is well-formed or not. The usual expected encoding is UTF-8,
but the string-processing functions make no such assumptions.

I may eventually add a "wstring" type (and conversions) specifically to deal with Microsoft Windows,
which has many APIs that expect 16-bit "wide characters" and don't necessarily enforce Unicode-style
well-formed-ness requirements.

