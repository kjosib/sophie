Lifting Sub-Functions
#######################

Sometimes, you have a sub-function that doesn't refer to anything in its immediately-enclosing scope,
but it's enclosed within whatever scope because that's where it's relevant or that's where it's used.
For example::

    outer(a,b,c) = ... where
        inner(d,e,f) = ... not mentioning anything in .;
    end outer;

A naive translation might end up creating a closure for ``inner`` every time ``outer`` gets called.
However, that's wasted time if ``inner`` may as well be a global function.

Now that the resolver works out exactly which values get captured by which functions, it might make
sense to lift functions out to the outermost scope where they have access to everything they need.

At the moment, that's a *nice-to-have* possible optimization. But one day, perhaps I'll try it out.
