"""
I want a simple, light-weight way to pass-around and manipulate points and spans within a collection of files.
The concept is simple: Use integers, with spans of them associated to specific files.
"""
from bisect import bisect_right
from pathlib import Path
from typing import NamedTuple, Optional

class Span(NamedTuple):
	""" Aimed at whatever prints error messages """
	path: Path
	slice: slice

_slices: list[slice] = []
_bounds: list[int] = []
_paths: list[Optional[Path]] = []

def reset_location_index():
	for it in _slices, _bounds, _paths: it.clear()
	# Now prepare the "built-in" location, which is location zero:
	start_segment(None)
	insert_token(slice(0,0))

def start_segment(path:Optional[Path]):
	assert isinstance(path, Path) or path is None
	_bounds.append(len(_slices)-1)
	_paths.append(path)

def insert_token(s:slice) -> int:
	index = len(_slices)
	_slices.append(s)
	return index

def lookup_token(index:int) -> Span:
	segment_index = bisect_right(_bounds, index)-1
	return Span(_paths[segment_index], _slices[index])

def lookup_span(first: int, last:int) -> Span:
	left = lookup_token(first)
	right = lookup_token(last)
	assert left.path == right.path
	return Span(left.path, slice(left.slice.start, right.slice.stop))
