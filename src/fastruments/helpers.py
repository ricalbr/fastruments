"""Helper functions"""

from typing import Optional
from typing import Tuple
from typing import Protocol
import ctypes
from fastruments import logger


class _HasAttr(Protocol):
    """Protocol for objects that can receive dynamically bound attributes."""

    pass


class DllBinder:
    def __init__(self, dll: ctypes.CDLL) -> None:
        self._dll: ctypes.CDLL = dll

    def bind(
        self,
        target: _HasAttr,
        name: str,
        restype: Optional[type],
        argtypes: Optional[Tuple[type, ...]] = None,
    ) -> None:
        func = getattr(self._dll, name)

        # ctypes function attributes are dynamic → Any is unavoidable here
        func.restype = restype  # type: ignore[attr-defined]

        if argtypes is not None:
            func.argtypes = argtypes  # type: ignore[attr-defined]

        setattr(target, name, func)
        logger.debug(f"Bind {name} function.")
