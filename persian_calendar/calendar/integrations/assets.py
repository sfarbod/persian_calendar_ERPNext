"""ERPNext Asset Depreciation — Business Calendar adapters."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, cint, date_diff, flt, getdate

from erpnext.assets.doctype.asset.asset import Asset
from erpnext.assets.doctype.asset_depreciation_schedule.asset_depreciation_schedule import (
	AssetDepreciationSchedule,
)
from erpnext.assets.doctype.asset_shift_allocation.asset_shift_allocation import AssetShiftAllocation

from persian_calendar.calendar.engine import CalendarEngine
from persian_calendar.calendar.types import LastDayPolicy

_DISPOSAL_PATCHED = False


def _company_for_asset(asset_name_or_doc) -> str | None:
	if not asset_name_or_doc:
		return None
	if hasattr(asset_name_or_doc, "company"):
		return asset_name_or_doc.company
	return frappe.db.get_value("Asset", asset_name_or_doc, "company")


def get_provider_for_company(company: str | None):
	"""Resolve Business Calendar provider for ``company`` (never Display)."""
	return CalendarEngine.for_company(company)


class BusinessCalendarDateMixin:
	"""Helpers that route month arithmetic through the Company Business Calendar."""

	def _business_calendar(self):
		company = getattr(self, "company", None)
		if not company and getattr(self, "asset_doc", None):
			company = self.asset_doc.company
		if not company and getattr(self, "asset", None):
			company = _company_for_asset(self.asset)
		return get_provider_for_company(company)

	def _bc_is_month_end(self, d) -> bool:
		return self._business_calendar().is_month_end(d)

	def _bc_month_end(self, d):
		return self._business_calendar().month_end(d)

	def _bc_add_months(self, d, months: int, *, preserve_month_end: bool = False):
		policy = (
			LastDayPolicy.PRESERVE_MONTH_END if preserve_month_end else LastDayPolicy.CLAMP_DAY
		)
		return self._business_calendar().add_months(d, months, last_day_policy=policy)

	def _bc_month_diff(self, start, end) -> int:
		return self._business_calendar().month_diff(start, end)

	def _bc_add_years(self, d, years: int):
		return self._business_calendar().add_years(d, years, last_day_policy=LastDayPolicy.CLAMP_DAY)


class PersianCalendarAssetDepreciationSchedule(BusinessCalendarDateMixin, AssetDepreciationSchedule):
	"""Asset Depreciation Schedule with Company Business Calendar month arithmetic."""

	def initialize_variables(self):
		super().initialize_variables()
		# Re-evaluate month-end using Business Calendar (not Gregorian-only).
		self.should_get_last_day = self._bc_is_month_end(self.fb_row.depreciation_start_date)

	def set_final_number_of_depreciations_considering_increase_in_asset_life(self):
		self.final_schedule_date = self._bc_add_months(
			self.asset_doc.available_for_use_date,
			(self.fb_row.total_number_of_depreciations * cint(self.fb_row.frequency_of_depreciation))
			+ cint(self.fb_row.increase_in_asset_life),
		)

		number_of_pending_depreciations = cint(self.fb_row.total_number_of_depreciations) - cint(
			self.asset_doc.opening_number_of_booked_depreciations
		)
		schedule_date = self._bc_add_months(
			self.fb_row.depreciation_start_date,
			number_of_pending_depreciations * cint(self.fb_row.frequency_of_depreciation),
		)

		if self.final_schedule_date > getdate(schedule_date):
			months = self._bc_month_diff(schedule_date, self.final_schedule_date)
			self.final_number_of_depreciations += months // cint(self.fb_row.frequency_of_depreciation) + 1

	def _check_is_pro_rata(self):
		self.has_pro_rata = False

		if self.fb_row.depreciation_method in ("Straight Line", "Manual"):
			prev_depreciation_start_date = self._bc_month_end(
				self._bc_add_months(
					self.fb_row.depreciation_start_date,
					(self.fb_row.frequency_of_depreciation * -1)
					* self.asset_doc.opening_number_of_booked_depreciations,
				)
			)
			from_date = self.asset_doc.available_for_use_date
			days = date_diff(prev_depreciation_start_date, from_date) + 1
			total_days = self.get_total_days(prev_depreciation_start_date)
		else:
			from_date = self._get_modified_available_for_use_date_for_existing_assets()
			days = date_diff(self.fb_row.depreciation_start_date, from_date) + 1
			total_days = self.get_total_days(self.fb_row.depreciation_start_date)

		if days <= 0:
			frappe.throw(
				frappe._(
					"""Error: This asset already has {0} depreciation periods booked.
					The `depreciation start` date must be at least {1} periods after the `available for use` date.
					Please correct the dates accordingly."""
				).format(
					self.asset_doc.opening_number_of_booked_depreciations,
					self.asset_doc.opening_number_of_booked_depreciations,
				)
			)
		if days < total_days:
			self.has_pro_rata = True
			self.has_wdv_or_dd_non_yearly_pro_rata = True

	def _get_modified_available_for_use_date_for_existing_assets(self):
		if self.asset_doc.opening_number_of_booked_depreciations > 0:
			from_date = add_days(
				self._bc_add_months(
					self.fb_row.depreciation_start_date,
					self.fb_row.frequency_of_depreciation * -1,
				),
				1,
			)
			return from_date
		return self.asset_doc.available_for_use_date

	def get_total_days(self, date):
		period_start_date = self._bc_add_months(date, cint(self.fb_row.frequency_of_depreciation) * -1)
		if self._bc_is_month_end(date):
			period_start_date = self._bc_month_end(period_start_date)
		return date_diff(date, period_start_date)

	def get_last_booked_depreciation_date(self):
		last_depr_date = None
		if self.first_non_depreciated_row_idx > 0:
			last_depr_date = self.depreciation_schedule[self.first_non_depreciated_row_idx - 1].schedule_date
		elif self.asset_doc.opening_number_of_booked_depreciations > 0:
			last_depr_date = self._bc_add_months(
				self.fb_row.depreciation_start_date, -1 * self.fb_row.frequency_of_depreciation
			)
		return last_depr_date

	def get_booked_depr_for_months_count(self, last_depr_date):
		depr_booked_for_months = 0
		if last_depr_date:
			asset_used_for_months = self.fb_row.frequency_of_depreciation * (
				1 + self.asset_doc.opening_number_of_booked_depreciations
			)
			computed_available_for_use_date = add_days(
				self._bc_add_months(self.fb_row.depreciation_start_date, -1 * asset_used_for_months),
				1,
			)
			if getdate(computed_available_for_use_date) < getdate(self.asset_doc.available_for_use_date):
				computed_available_for_use_date = self.asset_doc.available_for_use_date
			depr_booked_for_months = (date_diff(last_depr_date, computed_available_for_use_date) + 1) / (
				365 / 12
			)
		return depr_booked_for_months

	def has_fiscal_year_changed(self, row_idx):
		from erpnext.accounts.utils import get_fiscal_year

		self.fiscal_year_changed = False

		schedule_date = self._bc_month_end(
			self._bc_add_months(
				self.fb_row.depreciation_start_date,
				row_idx * cint(self.fb_row.frequency_of_depreciation),
			)
		)

		if not self.current_fiscal_year_end_date:
			self.current_fiscal_year_end_date = get_fiscal_year(self.fb_row.depreciation_start_date)[2]
			self.fiscal_year_changed = True
		elif getdate(schedule_date) > getdate(self.current_fiscal_year_end_date):
			self.current_fiscal_year_end_date = self._bc_add_years(self.current_fiscal_year_end_date, 1)
			self.fiscal_year_changed = True

	def get_next_schedule_date(self, row_idx):
		schedule_date = self._bc_add_months(
			self.fb_row.depreciation_start_date,
			row_idx * cint(self.fb_row.frequency_of_depreciation),
			preserve_month_end=bool(self.should_get_last_day),
		)
		return schedule_date

	def set_depreciation_amount_for_disposal(self, row_idx):
		if self.depreciation_schedule:
			from_date = add_days(self.depreciation_schedule[-1].schedule_date, 1)
		else:
			from_date = self._get_modified_available_for_use_date_for_existing_assets()
			if self._bc_is_month_end(getdate(self.asset_doc.available_for_use_date)):
				from_date = self._bc_month_end(from_date)

		self.depreciation_amount, days, months = self._get_pro_rata_amt(
			from_date,
			self.disposal_date,
			original_schedule_date=self.schedule_date,
		)

		self.depreciation_amount = flt(
			self.depreciation_amount, self.asset_doc.precision("net_purchase_amount")
		)
		if self.depreciation_amount > 0:
			self.schedule_date = self.disposal_date
			self.add_depr_schedule_row(row_idx)

	def set_depreciation_amount_for_last_row(self, row_idx):
		if not self.fb_row.increase_in_asset_life:
			self.final_schedule_date = self._bc_add_months(
				self.asset_doc.available_for_use_date,
				(row_idx + self.opening_number_of_booked_depreciations)
				* cint(self.fb_row.frequency_of_depreciation),
			)
			if self._bc_is_month_end(getdate(self.asset_doc.available_for_use_date)):
				self.final_schedule_date = self._bc_month_end(self.final_schedule_date)

		if self.opening_accumulated_depreciation:
			self.depreciation_amount, days, months = self._get_pro_rata_amt(
				self.schedule_date,
				self.final_schedule_date,
			)
		else:
			if not self.fb_row.increase_in_asset_life:
				self.depreciation_amount -= self.get("depreciation_schedule")[0].depreciation_amount
			days = date_diff(self.final_schedule_date, self.schedule_date) + 1

		self.schedule_date = add_days(self.schedule_date, days - 1)

	def _get_total_days(self, depreciation_start_date, row_idx):
		from_date = self._bc_add_months(
			depreciation_start_date, (row_idx - 1) * self.frequency_of_depreciation
		)
		to_date = self._bc_add_months(from_date, self.frequency_of_depreciation)
		if self._bc_is_month_end(depreciation_start_date):
			to_date = self._bc_month_end(to_date)
			from_date = add_days(self._bc_month_end(from_date), 1)
		return from_date, date_diff(to_date, from_date) + 1

	def _get_pro_rata_amt(self, from_date, to_date, original_schedule_date=None):
		days = date_diff(to_date, from_date) + 1
		months = self._bc_month_diff(from_date, to_date)
		total_days = self.get_total_days(original_schedule_date or to_date)
		return (self.depreciation_amount * flt(days)) / flt(total_days), days, months


class PersianCalendarAsset(BusinessCalendarDateMixin, Asset):
	"""Default depreciation_start_date uses Company Business Calendar month-end."""

	def validate_asset_finance_books(self, row):
		row.expected_value_after_useful_life = flt(
			row.expected_value_after_useful_life, self.precision("net_purchase_amount")
		)

		if flt(row.expected_value_after_useful_life) < 0:
			frappe.throw(
				frappe._("Row {0}: Expected Value After Useful Life cannot be negative").format(row.idx)
			)
		if flt(row.expected_value_after_useful_life) >= flt(self.net_purchase_amount):
			frappe.throw(
				frappe._(
					"Row {0}: Expected Value After Useful Life must be less than Net Purchase Amount"
				).format(row.idx)
			)

		if not row.depreciation_start_date:
			row.depreciation_start_date = self._bc_month_end(self.available_for_use_date)
		self.validate_depreciation_start_date(row)
		self.validate_total_number_of_depreciations_and_frequency(row)

		if self.asset_type != "Existing Asset":
			self.opening_accumulated_depreciation = 0
			self.opening_number_of_booked_depreciations = 0
		else:
			self.validate_opening_depreciation_values(row)


class PersianCalendarAssetShiftAllocation(BusinessCalendarDateMixin, AssetShiftAllocation):
	"""Shift schedule row dates follow Company Business Calendar."""

	def add_schedule_row(self, factor, reverse_shift_factors_map):
		last_date = self.depreciation_schedule[-1].schedule_date
		preserve = self._bc_is_month_end(last_date)
		schedule_date = self._bc_add_months(
			last_date,
			cint(self.asset_depr_schedule_doc.frequency_of_depreciation),
			preserve_month_end=preserve,
		)

		self.append(
			"depreciation_schedule",
			{
				"schedule_date": schedule_date,
				"shift": reverse_shift_factors_map.get(factor),
			},
		)


def disposal_was_made_on_original_schedule_date(schedule_idx, row, disposal_date):
	"""Business-calendar-aware mirror of ERPNext disposal date equality check."""
	company = None
	if hasattr(row, "parent") and row.parent:
		company = _company_for_asset(row.parent)
	if not company:
		company = getattr(row, "company", None)
	# When restoring an asset, ``row`` is an Asset Finance Book child whose parent is the Asset.
	# Fall back to the asset currently being processed if flags are set.
	if not company and getattr(frappe.flags, "current_asset_company", None):
		company = frappe.flags.current_asset_company
	cal = get_provider_for_company(company)
	preserve = cal.is_month_end(row.depreciation_start_date)
	original_schedule_date = cal.add_months(
		row.depreciation_start_date,
		schedule_idx * cint(row.frequency_of_depreciation),
		last_day_policy=(
			LastDayPolicy.PRESERVE_MONTH_END if preserve else LastDayPolicy.CLAMP_DAY
		),
	)
	return getdate(original_schedule_date) == getdate(disposal_date)


def apply_asset_disposal_patch():
	"""Narrowly replace disposal_was_made_on_original_schedule_date (not global add_months)."""
	global _DISPOSAL_PATCHED
	if _DISPOSAL_PATCHED:
		return
	import erpnext.assets.doctype.asset.depreciation as depr_mod

	depr_mod.disposal_was_made_on_original_schedule_date = (
		disposal_was_made_on_original_schedule_date
	)
	_DISPOSAL_PATCHED = True
