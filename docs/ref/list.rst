List Functions
##################



* ``any(xs) : flag`` True when at least one member of an input list evaluates to true. (Otherwise false.)
* ``all(xs) : flag``: False when at least one member of an input list evaluates to false. (Otherwise true.)
* ``map(fn, xs) : list``: Produce a list by applying ``fn`` to all members of ``xs``.
* ``filter(predicate, xs) : list``: Returns a list composed of those elements from ``fn`` such that ``predicate(fn)``.
* ``reduce(fn, a, xs)``: Produce a single element by applying ``fn`` repeatedly to rolling pairs of arguments:
  first ``a`` and the head of ``xs``, then that result with the next entry in ``xs``, and so forth.
  If ``xs`` is empty, it returns ``a`` without ever calling ``fn``.
* ``expand`` is not currently a thing. When it becomes a thing, this page will update.
* ``cat(xs, ys) : list``: Return a list composed of the elements of ``xs`` followed by those of ``ys``.
* ``flat(xss) : list``: Given a list of lists, return a single list composed of the elements of each input list in sequence.
* ``take(n, xs) : list``: return a list composed of the first ``n`` elements of ``xs``.
* ``drop(n, xs) : list``: return the remainder of list ``xs`` after skipping the first ``n`` elements.
* ``first(predicate, xs) : maybe``: return (maybe) the first element ``e`` of list ``xs`` such that ``predicate(e)`` is true.
