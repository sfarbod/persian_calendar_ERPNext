"""Patch SDK — reusable capture / rebind primitives (Phase 4b).

Thin helpers around the existing ``patches.apply_calendar_patches`` lifecycle.
New integrations should still register through ``apply_calendar_patches``;
these helpers reduce duplicated capture and identity-rebind code.
"""

from __future__ import annotations

import importlib
import logging
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any

logger = logging.getLogger("persian_calendar.calendar.patch_sdk")


def capture_original(
	module: ModuleType | str,
	attr: str,
	*,
	adapter: Callable[..., Any] | None = None,
	already: Callable[..., Any] | None = None,
) -> Callable[..., Any]:
	"""Return the stock callable for *attr*, refusing to capture *adapter*.

	If *already* is set, return it unchanged (capture-once).
	"""
	if already is not None:
		return already
	mod = importlib.import_module(module) if isinstance(module, str) else module
	current = getattr(mod, attr)
	if adapter is not None and current is adapter:
		raise RuntimeError(
			f"{getattr(mod, '__name__', mod)}.{attr} is already the adapter but "
			"the stock original was never captured"
		)
	return current


def install_adapter(module: ModuleType | str, attr: str, adapter: Callable[..., Any]) -> None:
	"""Replace ``module.attr`` with *adapter* when it is not already installed."""
	mod = importlib.import_module(module) if isinstance(module, str) else module
	if getattr(mod, attr, None) is not adapter:
		setattr(mod, attr, adapter)


def rebind_module_attr(
	mod: ModuleType,
	original: Callable[..., Any],
	adapter: Callable[..., Any],
	attr_name: str,
) -> bool:
	"""Replace ``mod.attr_name`` only when it is the captured *original*."""
	current = getattr(mod, attr_name, None)
	if current is None:
		return False
	if current is original:
		setattr(mod, attr_name, adapter)
		return True
	return False


def rebind_consumers(
	original: Callable[..., Any],
	adapter: Callable[..., Any],
	attr_name: str,
	known_consumers: tuple[str, ...],
	*,
	source_module: str | None = None,
	scan_erpnext: bool = False,
) -> list[str]:
	"""Identity-rebind known consumers; optionally scan loaded ``erpnext.*`` modules."""
	rebound: list[str] = []
	for mod_name in known_consumers:
		mod = sys.modules.get(mod_name)
		if mod is None:
			continue
		if rebind_module_attr(mod, original, adapter, attr_name):
			rebound.append(mod_name)

	if scan_erpnext:
		for mod_name, mod in list(sys.modules.items()):
			if not mod_name.startswith("erpnext."):
				continue
			if source_module and mod_name == source_module:
				continue
			if mod_name in known_consumers:
				continue
			if not isinstance(mod, ModuleType):
				continue
			if rebind_module_attr(mod, original, adapter, attr_name):
				rebound.append(mod_name)
				logger.info(
					"Rebound unlisted erpnext consumer via identity scan: %s.%s",
					mod_name,
					attr_name,
				)
	return rebound


def consumers_still_on_original(
	original: Callable[..., Any],
	attr_name: str,
	known_consumers: tuple[str, ...],
) -> list[str]:
	still = []
	for mod_name in known_consumers:
		mod = sys.modules.get(mod_name)
		if mod is None:
			continue
		if getattr(mod, attr_name, None) is original:
			still.append(mod_name)
	return still
