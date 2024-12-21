# Sophie's New Static Type Checker

Why start over?

Two reasons.
First, the old one got rather messy.
Second, major upheaval in how I want the mechanics to work. 

As before, the basic concept is to run the program in the domain
of types, and look for any square pegs bound for round holes.

As before, the general plan is a syntax-directed operation
where objects-representing-types are associated with symbols
in something like a dynamic name-space. However, the new
captured-symbols sets simplify some of the trickier bits.

Also, since this is no longer my first rodeo, I have ideas.

----------------------------------------------------------------

Last time, I treated *product-type* as its own thing, but that
didn't really feel like a win. This time, I'll try to keep the
structural types more in line with the surface syntax. Thus,
arrow- and message-types will contain their fields directly,
rather than delegating to a weird extra layer.

Also last time, I had this weird "ManifestBuilder" thing.
The idea was to convert manifest type annotations into the
same kind of type-as-value thing that everything else worked
with, and then have a unification engine that only had to
understand one kind of object. But that got really confusing!
I think it will be better to do a syntax-directed verification.

The motivation for unification in the first place was to deal
with conditionals and match-clauses. However, this is simpler
than it looks! Either you have *exactly* the same type coming
out, or you don't. And in the case when you don't, there are
exactly two possibilities: Genuine type-mismatch, or like a
list-of-functions is going on. In the latter case, a very
restricted form of unification will generally be sufficient,
for an interesting reason: I plan to represent *either-or*
as a distinct kind of type. For intersecting actors, we look
at the roles they have in common, which I'll call "character".
(Corresponding roles will get either-or parameters as needed.)
For functions, any attempt to apply an either-or means to apply
each component and then intersect the results. Any other kind
of either-or shall be an error -- at least, for now. (I may
eventually relax the rules and allow either-or records with
an intersection of fields, 

Either-or types for UDFs seem like a cumbersome and slow idea.
However, ad-hoc multiple-dispatch makes it quite challenging to
represent everything about a function's precondition any other
way. We can simplify this. Normally Sophie checks that a
function is *plausible*. However, if its manifest has no holes,
we can check *safety* with universal types. If the function uses
an existential *more than one way,* then it's implausible. But
if it examines a universal *at all,* then the check fails and
the manifest is incomplete.

Gödel's theorem still applies: You can't be correct, complete,
and consistent. But you can sure try pretty hard, and error on
the side of soundness.

----------------------------------------------------------------

So let's get started.