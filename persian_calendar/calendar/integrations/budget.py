"""Budget DocType adapter — Business Calendar period generation.

ERPNext v16 Budget stores periods in the Budget Distribution child table.
Periods are regenerated via ``Budget.get_budget_periods()`` (instance method).

Extension: ``override_doctype_class`` → ``PersianCalendarBudget``.
No free-function patch is required for Budget period generation.
"""

from __future__ import annotations

from frappe.utils import getdate

from erpnext.accounts.doctype.budget.budget import Budget

from persian_calendar.calendar.period_engine import BusinessPeriodEngine
from persian_calendar.calendar.resolve import (
	BUSINESS_CALENDAR_GREGORIAN,
	get_business_calendar_for_company,
)


class PersianCalendarBudget(Budget):
	"""Budget with Company Business Calendar-aware period boundaries."""

	def get_budget_periods(self):
		"""Return list of ``(start_date, end_date)`` tuples for distribution.

		Gregorian Business Calendar → stock ERPNext behavior (exact parity).
		Jalali (or other) → ``BusinessPeriodEngine`` with Gregorian storage dates.
		"""
		from persian_calendar.calendar.engine import CalendarEngine

		bc = get_business_calendar_for_company(self.company)
		if bc == BUSINESS_CALENDAR_GREGORIAN:
			return super().get_budget_periods()

		start = getdate(self.budget_start_date)
		end = getdate(self.budget_end_date)
		frequency = self.distribution_frequency or "Monthly"

		bp_list = BusinessPeriodEngine.generate(
			start_date=start,
			end_date=end,
			periodicity=frequency,
			provider=CalendarEngine.for_calendar(bc),
		)
		return [(bp.from_date, bp.to_date) for bp in bp_list]
