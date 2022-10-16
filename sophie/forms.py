"""
"""

from typing import NamedTuple, Optional

class Module(NamedTuple):
	exports: Optional[list]
	imports: Optional[list]
	types: Optional[list]
	functions: Optional[list]
