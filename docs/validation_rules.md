#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
data_validator.py

A production‑ready data validation module for CSV ETL pipelines.
Implements type, range, format, required, business‑rule, and referential
integrity checks based on YAML schema definitions.

Author: AIGON‑X Core Team
License: MIT
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

# Optional dependency: PyYAML
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

# Optional dependency: python-dateutil
try:
    from dateutil import parser as date_parser  # type: ignore
except Exception:  # pragma: no cover
    date_parser = None  # type: ignore

# --------------------------------------------------------------------------- #
# Logging configuration
# --------------------------------------------------------------------------- #
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class ValidationError(Exception):
    """Raised when a validation rule fails."""


class SchemaLoadError(Exception):
    """Raised when the YAML schema cannot be loaded."""


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #
def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file and return its contents as a dictionary."""
    if not yaml:
        raise SchemaLoadError("PyYAML is required to load schema files.")
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        logger.exception("Failed to load YAML schema: %s", path)
        raise SchemaLoadError(f"Failed to load YAML schema: {exc}") from exc


def _trim_whitespace(series: pd.Series) -> pd.Series:
    """Trim leading/trailing whitespace from string columns."""
    return series.str.strip()


def _normalize_case(series: pd.Series, lower: bool = True) -> pd.Series:
    """Normalize string case."""
    return series.str.lower() if lower else series.str.upper()


def _parse_bool(series: pd.Series) -> pd.Series:
    """Parse boolean‑like values into True/False."""
    true_vals = {"true", "1", "yes", "y"}
    false_vals = {"false", "0", "no", "n"}
    return series.str.strip().str.lower().map(
        lambda v: True if v in true_vals else False if v in false_vals else pd.NA
    )


def _parse_date(series: pd.Series, fmt: str = "%Y-%m-%d") -> pd.Series:
    """Parse dates with optional format; fallback to dateutil if available."""
    if date_parser:
        return series.apply(
            lambda v: date_parser.parse(v, dayfirst=False, yearfirst=True)
            if pd.notna(v)
            else pd.NaT
        )
    try:
        return pd.to_datetime(series, format=fmt, errors="coerce")
    except Exception:
        return pd.to_datetime(series, errors="coerce")


def _validate_regex(series: pd.Series, pattern: str) -> pd.Series:
    """Return a boolean mask where the pattern matches."""
    regex = re.compile(pattern)
    return series.astype(str).str.match(regex)


def _collect_errors(
    errors: List[Dict[str, Any]],
    record_id: Any,
    field: str,
    rule: str,
    value: Any,
) -> None:
    """Append a validation error to the list."""
    errors.append(
        {
            "record_id": record_id,
            "field": field,
            "rule": rule,
            "value": value,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


# --------------------------------------------------------------------------- #
# Validation logic
# --------------------------------------------------------------------------- #
def validate_dataframe(
    df: pd.DataFrame,
    schema: Dict[str, Any],
    reference_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Validate a DataFrame against a YAML schema.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    schema : Dict[str, Any]
        Parsed YAML schema.
    reference_data : Optional[Dict[str, pd.DataFrame]]
        Reference datasets for foreign‑key checks.

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame]
        Valid rows, error rows.
    """
    errors: List[Dict[str, Any]] = []
    record_ids = df.index.tolist()

    # 1. Trim whitespace for all string columns
    string_cols = [
        c for c, t in schema.get("columns", {}).items() if t.get("type") == "string"
    ]
    for col in string_cols:
        if col in df.columns:
            df[col] = _trim_whitespace(df[col])

    # 2. Required field validation
    for col, rules in schema.get("columns", {}).items():
        if rules.get("required", False):
            if col not in df.columns:
                for rid in record_ids:
                    _collect_errors(errors, rid, col, "missing_column", None)
                continue
            mask = df[col].isna() | df[col].astype(str).str.strip().eq("")
            for rid in df[mask].index:
                _collect_errors(errors, rid, col, "required", df.at[rid, col])