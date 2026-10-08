"""Teaching Tools: a launcher of small tools for a computing teacher."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    __version__ = _version("teaching-tools")
except PackageNotFoundError:  # a checkout that is not installed
    __version__ = "0.0.0+local"
