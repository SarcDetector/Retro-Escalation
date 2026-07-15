"""Persistent, data-only rule-set storage for the Analysis Workbench.

Rule sets are deliberately plain JSON beside the RE-OSCR settings file.  This module never
imports, evaluates, or executes user content; it validates every value through the immutable
Workbench rule types before making it available to the controller.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from .workbench import WorkbenchRuleSet


RULE_SET_STORE_FILENAME = "workbench_rule_sets.json"
RULE_SET_STORE_VERSION = 1


class WorkbenchRuleStoreError(ValueError):
    """Raised when a stored or imported rule-set document is invalid."""


class WorkbenchRuleSetStore:
    """Load and atomically save validated custom Workbench rule sets."""

    def __init__(self, config_dir: str | Path | None):
        self.config_dir = Path(config_dir) if config_dir is not None else None
        self.path = (
            self.config_dir / RULE_SET_STORE_FILENAME
            if self.config_dir is not None else None
        )

    def load(self) -> tuple[WorkbenchRuleSet, ...]:
        """Return custom definitions, or an empty tuple when no store exists."""
        if self.path is None or not self.path.is_file():
            return ()
        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            )
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            raise WorkbenchRuleStoreError(
                f"Unable to read Workbench rule sets: {error}") from error
        return self._sets_from_store_payload(payload)

    def save(self, rule_sets: tuple[WorkbenchRuleSet, ...]) -> None:
        """Atomically persist custom definitions with all per-combat toggles off."""
        if self.path is None:
            return
        temporary_path: Path | None = None
        try:
            definitions = tuple(_definition_only(rule_set) for rule_set in rule_sets)
            _validate_unique_names(definitions)
            payload = {
                "version": RULE_SET_STORE_VERSION,
                "rule_sets": [rule_set.to_dict() for rule_set in definitions],
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                    "w", encoding="utf-8", newline="\n", delete=False,
                    dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                temporary_path = Path(handle.name)
            temporary_path.replace(self.path)
        except (OSError, UnicodeError, TypeError, ValueError) as error:
            try:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise WorkbenchRuleStoreError(
                f"Unable to save Workbench rule sets: {error}") from error

    @staticmethod
    def import_file(path: str | Path) -> WorkbenchRuleSet:
        """Read one strictly validated shareable rule-set document."""
        source = Path(path)
        try:
            return WorkbenchRuleSet.from_json(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, TypeError, ValueError) as error:
            raise WorkbenchRuleStoreError(
                f"Unable to import Workbench rule set: {error}") from error

    @staticmethod
    def export_file(path: str | Path, rule_set: WorkbenchRuleSet) -> None:
        """Write one portable rule set with activation toggles disabled."""
        destination = Path(path)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps(
                    _definition_only(rule_set).to_dict(), indent=2,
                    ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except (OSError, UnicodeError, TypeError, ValueError) as error:
            raise WorkbenchRuleStoreError(
                f"Unable to export Workbench rule set: {error}") from error

    @staticmethod
    def _sets_from_store_payload(payload) -> tuple[WorkbenchRuleSet, ...]:
        if not isinstance(payload, dict):
            raise WorkbenchRuleStoreError("rule-set store must be a JSON object")
        if set(payload) != {"version", "rule_sets"}:
            raise WorkbenchRuleStoreError(
                "rule-set store must contain only version and rule_sets")
        version = payload.get("version")
        if (
                isinstance(version, bool)
                or not isinstance(version, int)
                or version != RULE_SET_STORE_VERSION):
            raise WorkbenchRuleStoreError(
                f"unsupported rule-set store version: {version!r}")
        raw_sets = payload.get("rule_sets")
        if not isinstance(raw_sets, list):
            raise WorkbenchRuleStoreError("rule_sets must be a JSON array")
        try:
            rule_sets = tuple(WorkbenchRuleSet.from_dict(value) for value in raw_sets)
        except (TypeError, ValueError) as error:
            raise WorkbenchRuleStoreError(str(error)) from error
        _validate_unique_names(rule_sets)
        return tuple(_definition_only(rule_set) for rule_set in rule_sets)


def _definition_only(rule_set: WorkbenchRuleSet) -> WorkbenchRuleSet:
    return replace(
        rule_set,
        rules=tuple(replace(rule, enabled=False) for rule in rule_set.rules),
    )


def _validate_unique_names(rule_sets: tuple[WorkbenchRuleSet, ...]) -> None:
    names = [rule_set.name.casefold() for rule_set in rule_sets]
    if len(names) != len(set(names)):
        raise WorkbenchRuleStoreError("custom rule-set names must be unique")


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


__all__ = (
    "RULE_SET_STORE_FILENAME",
    "WorkbenchRuleSetStore",
    "WorkbenchRuleStoreError",
)
