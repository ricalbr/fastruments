from __future__ import annotations

import logging
import sys

from fastruments.logger import CustomConsoleFormatter

logger = logging.getLogger("fastruments")
logger.setLevel(logging.DEBUG)
logger.propagate = False

# Clear old handlers
for h in logger.handlers[:]:
    logger.removeHandler(h)
    h.close()

_ch1 = logging.StreamHandler(sys.stdout)
_ch1.setLevel(logging.INFO)
_ch1.setFormatter(CustomConsoleFormatter())
_ch1.addFilter(lambda record: record.levelno <= logging.INFO)
logger.addHandler(_ch1)
_ch2 = logging.StreamHandler(sys.stdout)
_ch2.setLevel(logging.WARNING)
_ch2.setFormatter(CustomConsoleFormatter())
logger.addHandler(_ch2)