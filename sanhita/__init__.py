"""sanhita: check Indian criminal-law citations against the 2023 codes."""
from .check import check
from .cite import find_citations

__all__ = ["check", "find_citations"]
__version__ = "0.1.0"
