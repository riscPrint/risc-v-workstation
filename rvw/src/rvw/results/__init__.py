"""Shared result formats (contracts C1 run, C3 suite results, C4 verdict): dataclasses, load/save,
validation, failure signatures and JUnit export. Other tools import this; it has no dependencies
beyond the standard library."""
from .junit import to_junit, write_junit
from .schema import (FAILING, RESULTS_SCHEMA, RUN_SCHEMA, STATUSES, VERDICT_SCHEMA, RunResult,
                     SchemaError, SuiteResults, TestEntry, Verdict, find_results, inconclusive_cause, load_results,
                     load_run, load_run_set, load_verdict, save_results, save_run, validate, validate_results,
                     validate_run, validate_verdict, write_json)
from .signature import failure_signature, normalize_message, run_signature, scala_location

__all__ = [
    "FAILING", "RESULTS_SCHEMA", "RUN_SCHEMA", "STATUSES", "VERDICT_SCHEMA", "RunResult", "SchemaError",
    "SuiteResults", "TestEntry", "Verdict", "find_results", "inconclusive_cause", "load_results", "load_run", "load_run_set", "load_verdict",
    "save_results", "save_run", "validate", "validate_results", "validate_run", "validate_verdict",
    "write_json", "to_junit", "write_junit", "failure_signature", "normalize_message", "run_signature",
    "scala_location",
]
