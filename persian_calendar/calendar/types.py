"""Calendar Framework shared types.

Public date values are always Gregorian (``datetime.date`` or ISO ``YYYY-MM-DD``).
Period keys are stable identifiers independent of display calendar or language.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Union

DateLike = Union[date, str]


class LastDayPolicy(str, Enum):
	"""Policy for month/year arithmetic when the day does not exist in the target month.

	``CLAMP_DAY`` (default)
	    Clamp the day to the last day of the destination month.
	    Example (Jalali): 1405-01-31 + 6 months → 1405-07-30.

	``PRESERVE_MONTH_END``
	    If the source date is the last day of its calendar month, the result is
	    always the last day of the destination month. Otherwise behave like
	    ``CLAMP_DAY``.
	    Example (Jalali): 1404-12-29 + 1 month → 1405-01-31.
	"""

	CLAMP_DAY = "clamp_day"
	PRESERVE_MONTH_END = "preserve_month_end"


# Default for add_months / add_years when callers omit the policy.
# Matches dateutil.relativedelta / frappe.utils.add_months clamping behaviour.
DEFAULT_LAST_DAY_POLICY = LastDayPolicy.CLAMP_DAY


class PeriodGrain(str, Enum):
	MONTHLY = "Monthly"
	QUARTERLY = "Quarterly"
	HALF_YEARLY = "Half-yearly"
	YEARLY = "Yearly"


class Frequency(str, Enum):
	"""Recurrence frequencies expressed in calendar months (or years for Yearly)."""

	MONTHLY = "Monthly"
	QUARTERLY = "Quarterly"
	HALF_YEARLY = "Half-yearly"
	YEARLY = "Yearly"


FREQUENCY_MONTHS = {
	Frequency.MONTHLY: 1,
	Frequency.QUARTERLY: 3,
	Frequency.HALF_YEARLY: 6,
	Frequency.YEARLY: 12,
}


@dataclass(frozen=True)
class Period:
	"""A business calendar period with Gregorian boundaries and a stable key.

	``key`` examples:
	- Gregorian monthly: ``2026-03``
	- Jalali monthly: ``1405-01``
	- Gregorian quarterly: ``2026-Q1``
	- Jalali yearly: ``1405``

	``calendar_system`` identifies which provider produced this period (``"Gregorian"``
	or ``"Jalali"``). Downstream consumers should never localize the key.
	"""

	start: date
	end: date
	grain: PeriodGrain
	year: int
	period_number: int
	key: str
	calendar_system: str = "Gregorian"
