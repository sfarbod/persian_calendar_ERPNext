"""ERPNext / Frappe version compatibility detector for the Business Calendar Framework.

Phase 4a — upgrade safety only. Does not change business period behaviour.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CompatibilityStatus(str, Enum):
	SUPPORTED = "SUPPORTED"
	PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
	UNKNOWN_VERSION = "UNKNOWN_VERSION"
	UNAVAILABLE = "UNAVAILABLE"


# Versions validated for Release 1.9.0 (Frappe ControlDatetime.sync_datepicker_state).
VALIDATED_ERPNEXT = "16.30.0"
VALIDATED_FRAPPE = "16.29.0"
SUPPORTED_ERPNEXT_MAJOR = 16
SUPPORTED_FRAPPE_MAJOR = 16


@dataclass(frozen=True)
class VersionReport:
	frappe_version: str | None
	erpnext_version: str | None
	python_version: str
	framework_version: str
	status: CompatibilityStatus
	messages: tuple[str, ...]


def _pkg_version(name: str) -> str | None:
	try:
		mod = __import__(name)
		return getattr(mod, "__version__", None)
	except ImportError:
		return None


def _major(version: str | None) -> int | None:
	if not version:
		return None
	try:
		return int(str(version).split(".", 1)[0])
	except (TypeError, ValueError):
		return None


def detect_compatibility() -> VersionReport:
	"""Compare installed Frappe/ERPNext against the validated matrix."""
	from persian_calendar import __version__ as framework_version

	frappe_v = _pkg_version("frappe")
	erpnext_v = _pkg_version("erpnext")
	py_v = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
	messages: list[str] = []

	if frappe_v is None or erpnext_v is None:
		messages.append(
			"Frappe and/or ERPNext are not importable in this process — " "cannot classify compatibility."
		)
		return VersionReport(
			frappe_version=frappe_v,
			erpnext_version=erpnext_v,
			python_version=py_v,
			framework_version=framework_version,
			status=CompatibilityStatus.UNAVAILABLE,
			messages=tuple(messages),
		)

	frappe_ok = frappe_v == VALIDATED_FRAPPE
	erpnext_ok = erpnext_v == VALIDATED_ERPNEXT
	frappe_major = _major(frappe_v)
	erpnext_major = _major(erpnext_v)

	if frappe_ok and erpnext_ok:
		status = CompatibilityStatus.SUPPORTED
		messages.append(
			f"Exact match with validated matrix " f"(Frappe {VALIDATED_FRAPPE}, ERPNext {VALIDATED_ERPNEXT})."
		)
	elif frappe_major == SUPPORTED_FRAPPE_MAJOR and erpnext_major == SUPPORTED_ERPNEXT_MAJOR:
		status = CompatibilityStatus.PARTIALLY_VERIFIED
		messages.append(
			f"Installed Frappe {frappe_v} / ERPNext {erpnext_v} share major "
			f"{SUPPORTED_ERPNEXT_MAJOR} with the validated matrix "
			f"({VALIDATED_FRAPPE} / {VALIDATED_ERPNEXT}) but are not an exact match. "
			"Re-run contract tests and the upgrade checklist before production."
		)
	else:
		status = CompatibilityStatus.UNKNOWN_VERSION
		messages.append(
			f"Installed Frappe {frappe_v} / ERPNext {erpnext_v} differ from the "
			f"validated matrix (Frappe {VALIDATED_FRAPPE}, ERPNext {VALIDATED_ERPNEXT}). "
			"Business Calendar patches may be unsafe — run release_check and "
			"contract tests; do not assume period arithmetic is correct."
		)

	return VersionReport(
		frappe_version=frappe_v,
		erpnext_version=erpnext_v,
		python_version=py_v,
		framework_version=framework_version,
		status=status,
		messages=tuple(messages),
	)


def compatibility_as_dict(report: VersionReport | None = None) -> dict[str, Any]:
	report = report or detect_compatibility()
	return {
		"framework_version": report.framework_version,
		"frappe_version": report.frappe_version,
		"erpnext_version": report.erpnext_version,
		"python_version": report.python_version,
		"status": report.status.value,
		"messages": list(report.messages),
		"validated_frappe": VALIDATED_FRAPPE,
		"validated_erpnext": VALIDATED_ERPNEXT,
	}
