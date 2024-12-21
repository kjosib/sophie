"""
This module aims to express an interface agreement
between the evaluator and various kinds of data.
"""

from abc import ABC, abstractmethod
from typing import Sequence, Union
from ..ontology import TermSymbol


NATIVE_DATA = Union[int, float, str, dict]

class SophieValue(ABC):
	""" Root for classes that implement specialized run-time data structures """
	def perform(self): raise NotImplementedError(type(self))

LAZY_VALUE = Union[NATIVE_DATA, SophieValue]
ARGS = Sequence[LAZY_VALUE]
ENV = dict[TermSymbol, LAZY_VALUE]


STRICT_VALUE = Union[NATIVE_DATA, SophieValue]
STRICT_ARGS = Sequence[STRICT_VALUE]

