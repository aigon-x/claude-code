"""
Production‑grade test suite for the ETL data validation & transformation layer.

The tests exercise the public API of the :mod:`data_processing` module,
verifying that the functions return the expected types, handle errors
gracefully, and behave correctly when presented with valid and invalid
data.  All fixtures provide fresh, deep copies of the sample data to
guarantee isolation between tests, which is essential for parallel
execution with ``pytest-xdist``.

The test module uses the standard :mod:`logging` library to emit
debug‑level information to the ``test_data_processing`` logger.  Run
with ``pytest -o log_cli=true --log-cli-level=DEBUG`` to see the
full trace.

The module is intentionally self‑contained; it only relies on
libraries that are part of the repository or the Python standard
library.  If any required dependency is missing, an informative
``ImportError`` is raised.
"""

from __future__ import annotations

import copy
import