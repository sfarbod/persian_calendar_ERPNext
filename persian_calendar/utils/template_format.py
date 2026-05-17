"""Brace-style `{field}` and `{toshamshi(field)}` templates for messages and titles."""

from __future__ import annotations

import re
from typing import Any

from persian_calendar.utils.jalali import toshamshi

# {toshamshi(cheque_due_date)} or {toshamshi(posting_date, include_time=True, ...)}
_TOSHAMSHI_PLACEHOLDER_RE = re.compile(
	r"\{toshamshi\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:,\s*(.+?))?\s*\)\}",
	re.IGNORECASE,
)


def _parse_toshamshi_kwargs(args_str: str | None) -> tuple[bool, bool]:
	if not args_str:
		return False, False
	include_time = bool(re.search(r"include_time\s*=\s*True", args_str, re.IGNORECASE))
	persian_digits = bool(re.search(r"persian_digits\s*=\s*True", args_str, re.IGNORECASE))
	return include_time, persian_digits


class _SafeFormatDict(dict):
	"""str.format_map helper: missing keys stay as `{key}`."""

	def __missing__(self, key: str) -> str:
		return "{" + key + "}"


def _stringify_context_value(value: Any) -> Any:
	if value is None:
		return ""
	return value


def expand_toshamshi_placeholders(template: str, context: dict[str, Any]) -> str:
	"""Replace `{toshamshi(fieldname, ...)}` with Jalali display values."""

	def _replace(match: re.Match) -> str:
		fieldname = match.group(1)
		include_time, persian_digits = _parse_toshamshi_kwargs(match.group(2))
		raw = context.get(fieldname)
		return toshamshi(raw, include_time=include_time, persian_digits=persian_digits)

	return _TOSHAMSHI_PLACEHOLDER_RE.sub(_replace, template)


def render_brace_template(
	template: str | None,
	context: dict[str, Any] | None,
	*,
	fallback_on_error: bool = True,
) -> str:
	"""Render `{field}` and `{toshamshi(field)}` templates (not full Jinja).

	1. Expand `{toshamshi(...)}` using :func:`toshamshi`.
	2. Apply Python ``str.format_map`` for remaining ``{placeholders}``.
	"""
	tpl = (template or "").strip()
	if not tpl:
		return ""

	ctx = context or {}
	safe_ctx = _SafeFormatDict({k: _stringify_context_value(v) for k, v in ctx.items()})

	try:
		expanded = expand_toshamshi_placeholders(tpl, ctx)
		return expanded.format_map(safe_ctx)
	except Exception:
		if fallback_on_error:
			return tpl
		raise


def doc_as_format_context(doc: Any) -> dict[str, Any]:
	"""Build a flat dict from a Document for brace templates."""
	if doc is None:
		return {}
	if hasattr(doc, "as_dict"):
		data = doc.as_dict()
	elif isinstance(doc, dict):
		data = doc
	else:
		return {}
	return {k: _stringify_context_value(v) for k, v in data.items()}
