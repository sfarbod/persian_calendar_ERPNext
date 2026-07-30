"""Budget Variance report adapter — Business Calendar period alignment.

ERPNext v16 Budget Variance keys amounts by English ``strftime("%B")`` month
names. That breaks Jalali Business Calendar periods.

Strategy:

- Gregorian company → captured stock ``execute`` (exact parity).
- Jalali company → date-range matching against stored Budget Distribution rows
  and GL ``posting_date`` boundaries (no English month-name keys).

Why Trends patch alone is insufficient
--------------------------------------
Even when ``get_period_date_ranges`` returns Jalali boundaries, stock BVR still
flattens Budget Distribution into Gregorian calendar months and looks up amounts
by English month name. Period ranges alone cannot fix that.

Stored Budget Distribution rows remain authoritative. Submitted budgets are not
rewritten. Periodicity mismatch: finer stored periods aggregate into coarser
report periods by inclusion; coarser stored periods are split equally across
business months they cover (stock-equivalent flatten-then-regroup).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

from persian_calendar.calendar.engine import CalendarEngine
from persian_calendar.calendar.period_engine import BusinessPeriodEngine
from persian_calendar.calendar.period_labels import format_period_label
from persian_calendar.calendar.resolve import (
	BUSINESS_CALENDAR_GREGORIAN,
	BUSINESS_CALENDAR_JALALI,
	get_business_calendar_for_company,
)

_original_execute: Callable[..., Any] | None = None


def set_original_budget_variance_execute(fn: Callable[..., Any]) -> None:
	global _original_execute
	if _original_execute is None:
		_original_execute = fn


def get_original_budget_variance_execute() -> Callable[..., Any] | None:
	return _original_execute


def execute(filters=None):
	"""Drop-in replacement for budget_variance_report.execute."""
	if not filters:
		filters = {}

	company = filters.get("company")
	bc = get_business_calendar_for_company(company) if company else BUSINESS_CALENDAR_GREGORIAN

	if bc == BUSINESS_CALENDAR_GREGORIAN:
		if _original_execute is None:
			frappe.throw(
				_(
					"Budget Variance adapter is active but the original execute "
					"was not captured. Call apply_calendar_patches()."
				)
			)
		return _original_execute(filters)

	return _jalali_execute(filters)


def _jalali_execute(filters):
	from erpnext.accounts.report.budget_variance_report.budget_variance_report import (
		get_budget_dimensions,
		get_budget_records,
		get_cost_center_with_children,
		validate_filters,
	)

	validate_filters(filters)

	if filters.get("budget_against_filter"):
		dimensions = filters.get("budget_against_filter")
		if filters.get("budget_against") == "Cost Center":
			dimensions = get_cost_center_with_children(dimensions)
	else:
		dimensions = get_budget_dimensions(filters)

	periods = _jalali_periods(filters)
	columns = _jalali_columns(filters, periods)

	if not dimensions:
		return columns, [], None, None

	budget_records = get_budget_records(filters, dimensions)
	data = _build_jalali_report_data(budget_records, filters, periods)
	chart_data = _jalali_chart(filters, columns, data)
	return columns, data, None, chart_data


def _jalali_periods(filters):
	"""Build report periods using BusinessPeriodEngine for each fiscal year."""
	from erpnext.accounts.report.budget_variance_report.budget_variance_report import (
		get_fiscal_years,
	)

	cal = CalendarEngine.jalali()
	lang = getattr(frappe.local, "lang", None) or "en"
	locale = "fa" if lang in ("fa", "ar") else "en"
	periodicity = filters["period"]
	periods = []

	for (fiscal_year,) in get_fiscal_years(filters):
		year_start, year_end = frappe.get_cached_value(
			"Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"]
		)
		bp_list = BusinessPeriodEngine.generate(
			getdate(year_start),
			getdate(year_end),
			periodicity,
			provider=cal,
		)
		for bp in bp_list:
			label = format_period_label(bp, locale=locale)
			periods.append(
				{
					"fiscal_year": fiscal_year,
					"from_date": bp.from_date,
					"to_date": bp.to_date,
					"label_suffix": label,
					"key": f"{fiscal_year}:{bp.key}",
					"period_number": bp.period_number,
					"business_period": bp,
				}
			)
	return periods


def _jalali_columns(filters, periods):
	columns = [
		{
			"label": _(filters.get("budget_against")),
			"fieldtype": "Link",
			"fieldname": "budget_against",
			"options": filters.get("budget_against"),
			"width": 150,
		},
		{
			"label": _("Account"),
			"fieldname": "account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 150,
		},
	]

	for period in periods:
		fy = period["fiscal_year"]
		if filters["period"] == "Yearly":
			suffix = fy
		else:
			suffix = f"({period['label_suffix']}) {fy}"
		for kind in ("Budget", "Actual", "Variance"):
			label = _(kind) + " " + suffix
			columns.append(
				{
					"label": label,
					"fieldname": frappe.scrub(label),
					"fieldtype": "Float",
					"width": 150,
				}
			)

	if filters["period"] != "Yearly":
		for kind, fname in (
			(_("Total Budget"), "total_budget"),
			(_("Total Actual"), "total_actual"),
			(_("Total Variance"), "total_variance"),
		):
			columns.append({"label": kind, "fieldname": fname, "fieldtype": "Float", "width": 150})

	return columns


def _build_jalali_report_data(budget_records, filters, periods):
	from erpnext.accounts.report.budget_variance_report.budget_variance_report import (
		get_budget_distributions,
	)

	show_cumulative = filters.get("show_cumulative") and filters.get("period") != "Yearly"
	cal = CalendarEngine.jalali()
	data = []

	grouped: dict[tuple, list] = {}
	for budget in budget_records:
		key = (budget.dimension, budget.account)
		grouped.setdefault(key, []).append(budget)

	for (dimension, account), budgets in grouped.items():
		row = {"budget_against": dimension, "account": account}
		running_budget = 0.0
		running_actual = 0.0
		total_budget = 0.0
		total_actual = 0.0

		distributions = []
		for budget in budgets:
			dists = get_budget_distributions(budget)
			validate_distribution_integrity(budget.name, dists)
			distributions.extend(dists)

		actuals = _jalali_actuals(dimension, account, filters, periods)

		for period in periods:
			period_budget = budget_amount_for_period(distributions, period, cal)
			period_actual = actuals.get(period["key"], 0.0)

			if show_cumulative:
				running_budget += period_budget
				running_actual += period_actual
				display_budget = running_budget
				display_actual = running_actual
			else:
				display_budget = period_budget
				display_actual = period_actual

			total_budget += period_budget
			total_actual += period_actual

			fy = period["fiscal_year"]
			if filters["period"] == "Yearly":
				budget_label = _("Budget") + " " + fy
				actual_label = _("Actual") + " " + fy
				variance_label = _("Variance") + " " + fy
			else:
				budget_label = _("Budget") + f" ({period['label_suffix']}) {fy}"
				actual_label = _("Actual") + f" ({period['label_suffix']}) {fy}"
				variance_label = _("Variance") + f" ({period['label_suffix']}) {fy}"

			row[frappe.scrub(budget_label)] = display_budget
			row[frappe.scrub(actual_label)] = display_actual
			row[frappe.scrub(variance_label)] = display_budget - display_actual

		if filters["period"] != "Yearly":
			row["total_budget"] = total_budget
			row["total_actual"] = total_actual
			row["total_variance"] = total_budget - total_actual

		data.append(row)

	return data


def validate_distribution_integrity(budget_name: str, distributions) -> None:
	"""Reject duplicated or overlapping stored Budget Distribution rows.

	Matching never uses labels. Boundaries are Gregorian storage dates.
	"""
	seen: set[tuple] = set()
	normalized = []
	for row in distributions:
		if not row.start_date or not row.end_date:
			continue
		start = getdate(row.start_date)
		end = getdate(row.end_date)
		key = (start, end)
		if key in seen:
			frappe.throw(
				_(
					"Budget {0} has duplicated Budget Distribution periods "
					"({1} - {2}). Remove the duplicate before running Budget Variance."
				).format(budget_name, start, end)
			)
		seen.add(key)
		normalized.append((start, end, budget_name))

	normalized.sort()
	for i in range(1, len(normalized)):
		prev_start, prev_end, _prev_budget = normalized[i - 1]
		cur_start, cur_end, _cur_budget = normalized[i]
		if cur_start <= prev_end:
			frappe.throw(
				_(
					"Budget {0} has overlapping Budget Distribution periods "
					"({1}-{2} overlaps {3}-{4}). Fix the stored periods before reporting."
				).format(budget_name, prev_start, prev_end, cur_start, cur_end)
			)


def budget_amount_for_period(distributions, period, cal) -> float:
	"""Allocate stored Budget Distribution amounts into a report period.

	Policy:
	1. Distribution fully inside report period → full amount.
	2. Otherwise flatten into business months and include months that fall inside
	   the report period (stock-equivalent flatten-then-regroup).
	3. Labels are never used as lookup keys.
	"""
	p_from = getdate(period["from_date"])
	p_to = getdate(period["to_date"])
	total = 0.0

	for row in distributions:
		if not row.start_date or not row.end_date:
			continue
		d_from = getdate(row.start_date)
		d_to = getdate(row.end_date)
		amount = flt(row.amount)

		if d_from >= p_from and d_to <= p_to:
			total += amount
			continue

		if d_to < p_from or d_from > p_to:
			continue

		months = BusinessPeriodEngine.generate(d_from, d_to, "Monthly", provider=cal)
		if not months:
			continue
		per_month = amount / len(months)
		for m in months:
			if m.to_date < p_from or m.from_date > p_to:
				continue
			total += per_month

	return flt(total)


def _jalali_actuals(dimension, account, filters, periods) -> dict[str, float]:
	"""Sum GL actuals by posting_date within each report period (inclusive)."""
	budget_against = frappe.scrub(filters.get("budget_against"))
	gle = frappe.qb.DocType("GL Entry")

	from_date = min(p["from_date"] for p in periods)
	to_date = max(p["to_date"] for p in periods)

	query = (
		frappe.qb.from_(gle)
		.select(gle.posting_date, gle.debit, gle.credit)
		.where(
			(gle.account == account)
			& (gle.is_cancelled == 0)
			& (gle.posting_date >= from_date)
			& (gle.posting_date <= to_date)
			& (gle.company == filters.get("company"))
		)
	)

	if filters.get("budget_against") == "Cost Center":
		from erpnext.accounts.report.budget_variance_report.budget_variance_report import (
			get_cost_center_with_children,
		)

		cost_centers = get_cost_center_with_children([dimension])
		query = query.where(gle.cost_center.isin(cost_centers))
	else:
		query = query.where(gle[budget_against] == dimension)

	rows = query.run(as_dict=True)
	result = {p["key"]: 0.0 for p in periods}

	for txn in rows:
		posting = getdate(txn.posting_date)
		amt = flt(txn.debit) - flt(txn.credit)
		for p in periods:
			if getdate(p["from_date"]) <= posting <= getdate(p["to_date"]):
				result[p["key"]] += amt
				break

	return result


def _jalali_chart(filters, columns, data):
	from erpnext.accounts.report.budget_variance_report.budget_variance_report import (
		build_comparison_chart_data,
	)

	try:
		return build_comparison_chart_data(filters, columns, data)
	except Exception:
		return None


def validate_stale_budget_calendar(budget_name: str, company: str) -> None:
	"""Warn when stored BD boundaries are not Jalali month starts under Jalali BC.

	Does not rewrite submitted documents. Historical rows stay authoritative.
	"""
	bc = get_business_calendar_for_company(company)
	if bc != BUSINESS_CALENDAR_JALALI:
		return

	rows = frappe.get_all(
		"Budget Distribution",
		filters={"parent": budget_name},
		fields=["start_date", "end_date"],
		order_by="start_date",
	)
	if not rows:
		return

	cal = CalendarEngine.jalali()
	for row in rows:
		start = getdate(row.start_date)
		if start != cal.month_start(start):
			frappe.msgprint(
				_(
					"Budget {0} (company {1}, Business Calendar Jalali) has distribution "
					"dates that do not start on a Jalali month boundary. Submitted "
					"historical rows are kept as stored; amend/regenerate the Budget if "
					"Jalali periods are required."
				).format(budget_name, company),
				indicator="orange",
				alert=True,
			)
			return
