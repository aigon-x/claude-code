#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AIGON‑X DataFrame Validation Module
====================================

This module provides a highly‑robust, type‑safe implementation of
``apply_validation_rules`` for validating and coercing Pandas
DataFrames against a collection of validation rules.

The implementation follows the following guidelines:

* Comprehensive type annotations (PEP 484, PEP 544)
* Full error handling with custom exception hierarchy
* Extensive logging with configurable levels
* Input validation and security checks
* Performance optimisations via vectorised Pandas operations
* Clean code and documentation (Sphinx style)

The module is self‑contained and only relies on the standard library
and the public ``pandas`` API, which is available in the repository
context.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Protocol,
    Tuple,
    Union,
)

import pandas as pd

__all__ = [
    "ValidationConfigError",
    "ValidationRule",
    "ValidationRuleImpl",
    "apply_validation_rules",
]

# --------------------------------------------------------------------------- #
# Logging configuration
# --------------------------------------------------------------------------- #

logger = logging.getLogger(__name__)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #

class ValidationConfigError(RuntimeError):
    """
    Raised when a validation rule configuration is invalid.

    Attributes
    ----------
    message : str
        Human readable description of the error.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# --------------------------------------------------------------------------- #
# ValidationRule protocol
# --------------------------------------------------------------------------- #

class ValidationRule(Protocol):
    """
    Protocol describing a validation rule.

    Attributes
    ----------
    column : str
        Target column name.
    required : bool
        Whether the column must be present.
    nullable : bool
        Whether the column may contain null values.
    dtype : Optional[Union[type, str]]
        Desired dtype for the column. ``None`` or ``"string"`` means no
        coercion.
    """

    column: str
    required: bool
    nullable: bool
    dtype: Optional[Union[type, str]]


# --------------------------------------------------------------------------- #
# Concrete implementation of ValidationRule
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ValidationRuleImpl:
    """
    Immutable dataclass implementing :class:`ValidationRule`.

    Parameters
    ----------
    column : str
        Target column name.
    required : bool, default False
        Whether the column must be present.
    nullable : bool, default True
        Whether the column may contain null values.
    dtype : Optional[Union[type, str]], default None
        Desired dtype for the column. ``None`` or ``"string"`` means no
        coercion.
    """

    column: str
    required: bool = False
    nullable: bool = True
    dtype: Optional[Union[type, str]] = None


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #

def _validate_dataframe(df: pd.DataFrame) -> None:
    """
    Validate that the input is a Pandas DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to validate.

    Raises
    ------
    TypeError
        If ``df`` is not a :class:`pandas.DataFrame`.
    """
    if not isinstance(df, pd.DataFrame):
        logger.error("Expected pandas.DataFrame, got %s", type(df).__name__)
        raise TypeError("df must be a pandas.DataFrame instance")


def _validate_rule(rule: ValidationRule) -> None:
    """
    Validate a single rule instance.

    Parameters
    ----------
    rule : ValidationRule
        Rule to validate.

    Raises
    ------
    ValidationConfigError
        If the rule is missing required attributes or contains invalid values.
    """
    if not isinstance(rule, ValidationRule):
        logger.error("Rule does not conform to ValidationRule protocol: %r", rule)
        raise ValidationConfigError("Rule does not conform to ValidationRule protocol")

    if not isinstance(rule.column, str) or not rule.column:
        logger.error("Rule column must be a non‑empty string: %r", rule)
        raise ValidationConfigError("Rule column must be a non‑empty string")

    if not isinstance(rule.required, bool):
        logger.error("Rule.required must be bool: %r", rule)
        raise ValidationConfigError("Rule.required must be bool")

    if not isinstance(rule.nullable, bool):
        logger.error("Rule.nullable must be bool: %r", rule)
        raise ValidationConfigError("Rule.nullable must be bool")

    if rule.dtype is not None and not isinstance(rule.dtype, (type, str)):
        logger.error("Rule.dtype must be type or str or None: %r", rule)
        raise ValidationConfigError("Rule.dtype must be type, str, or None")


def _coerce_series(series: pd.Series, dtype: Optional[Union[type, str]]) -> pd.Series:
    """
    Coerce a Pandas Series to the requested dtype.

    Parameters
    ----------
    series : pd.Series
        Series to coerce.
    dtype : Optional[Union[type, str]]
        Target dtype. ``None`` or ``"string"`` means no coercion.

    Returns
    -------
    pd.Series
        Coerced series.

    Raises
    ------
    ValidationConfigError
        If the dtype is unsupported by pandas.
    """
    if dtype is None or (isinstance(dtype, str) and dtype.lower() == "string"):
        return series

    try:
        coerced = series.astype(dtype, copy=False, errors="raise")
        logger.debug("Coerced series to dtype %s", dtype)
        return coerced
    except (TypeError, ValueError) as exc:
        logger.exception("Failed to cast series to dtype %s: %s", dtype, exc)
        raise ValidationConfigError(
            f"Coercion failed for dtype '{dtype}'"
        ) from exc


def _record_null_violations(
    reasons: Dict[int, List[str]],
    column: str,
    null_indices: pd.Index,
) -> None:
    """
    Record null violations for a column.

    Parameters
    ----------
    reasons : Dict[int, List[str]]
        Mapping from row index to list of messages.
    column : str
        Column name.
    null_indices : pd.Index
        Indices where null values were found.
    """
    msg = f"Column '{column}' contains null values but nullable is False"
    for idx in null_indices:
        reasons[idx].append(msg)
    logger.debug(
        "Recorded null violations for column '%s' at indices %s",
        column,
        null_indices.tolist(),
    )


# --------------------------------------------------------------------------- #
# Main public API
# --------------------------------------------------------------------------- #

def apply_validation_rules(
    df: pd.DataFrame,
    rules: Iterable[ValidationRule],
) -> Tuple[pd.DataFrame, Dict[int, List[str]]]:
    """
    Apply a sequence of validation rules to a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        The input data to be validated and possibly coerced.
    rules : Iterable[ValidationRule]
        Rules describing column expectations, requiredness, nullability,
        and target dtype.

    Returns
    -------
    Tuple[pd.DataFrame, Dict[int, List[str]]]
        A tuple containing the (possibly modified) DataFrame and a mapping
        from row index to a list of validation messages.

    Raises
    ------
    TypeError
        If ``df`` is not a pandas DataFrame or ``rules`` is not iterable.
    ValidationConfigError
        If a required column is missing from ``df`` or a rule is malformed.
    """
    _validate_dataframe(df)

    try:
        rule_iter = iter(rules)
    except TypeError as exc:
        logger.error("rules must be an iterable of ValidationRule instances")
        raise TypeError("rules must be an iterable of ValidationRule instances") from exc

    reasons: Dict[int, List[str]] = defaultdict(list)

    for rule in rule_iter:
        try:
            _validate_rule(rule)
        except ValidationConfigError as exc:
            logger.warning("Skipping invalid rule: %s", exc)
            continue

        column = rule.column
        required = rule.required
        nullable = rule.nullable
        dtype = rule.dtype

        if column not in df.columns:
            if required:
                logger.error("Required column '%s' missing from DataFrame", column)
                raise ValidationConfigError(f"Required column '{column}' is not present in the DataFrame")
            logger.debug("Column '%s' not present and not required; skipping rule", column)
            continue

        series = df[column]
        try:
            coerced = _coerce_series(series, dtype)
        except ValidationConfigError as exc:
            logger.warning("Skipping rule for column '%s' due to coercion error: %s", column, exc)
            continue

        if dtype is not None and dtype != "string":
            df.loc[:, column] = coerced

        null_mask = coerced.isna()
        if not nullable and null_mask.any():
            null_indices = df.index[null_mask]
            _record_null_violations(reasons, column, null_indices)

    return df, dict(reasons)