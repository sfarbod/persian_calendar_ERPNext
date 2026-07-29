# Asset Depreciation — Business Calendar Integration Notes
#
# Investigation (ERPNext v16) — Checkpoint 3
# ============================================
#
# Call chain (schedule generation)
# --------------------------------
# Asset.create_asset_depreciation_schedule()
#   → make_draft_asset_depr_schedule / AssetDepreciationSchedule.create_depreciation_schedule
#     → get_finance_book_row / fetch_asset_details
#     → clear()  # keeps rows that already have journal_entry (booked)
#     → create()
#         → initialize_variables()
#             should_get_last_day = is_last_day_of_the_month(depreciation_start_date)
#         → for row_idx in pending rows:
#             schedule_date = get_next_schedule_date(row_idx)
#                 add_months(start, row_idx * frequency)
#                 if should_get_last_day: get_last_day(schedule_date)
#
# Booked vs unbooked
# ------------------
# clear() retains child rows with journal_entry set; only regenerates from
# first_non_depreciated_row_idx. Submitted JE rows are not mutated by schedule
# regeneration. Active (submitted) schedules are cancelled and replaced only via
# explicit reschedule_depreciation() — never silently rewritten on migrate.
#
# Additional Gregorian call sites (must stay in sync with ADS)
# -----------------------------------------------------------
# 1. DepreciationScheduleController methods using add_months / get_last_day /
#    is_last_day_of_the_month / month_diff (pro-rata, life extension, FY detect).
# 2. asset/depreciation.py::disposal_was_made_on_original_schedule_date
#    (module-level duplicate of get_next_schedule_date math).
# 3. AssetShiftAllocation.add_schedule_row
# 4. Asset (finance book setup) depreciation_start_date = get_last_day(AFU)
#
# Integration mechanism
# ---------------------
# - override_doctype_class: Asset Depreciation Schedule, Asset Shift Allocation, Asset
# - narrowly scoped before_request patch: disposal_was_made_on_original_schedule_date only
# - Forbidden: global frappe.utils.add_months monkey-patch
#
# Policy mapping
# --------------
# should_get_last_day True  → LastDayPolicy.PRESERVE_MONTH_END on add_months
# should_get_last_day False → LastDayPolicy.CLAMP_DAY (relativedelta-compatible)
# is_last_day_of_the_month  → provider.is_month_end
# get_last_day              → provider.month_end
# month_diff                → provider.month_diff
#
# Company Business Calendar = Gregorian → behaviour ≡ stock ERPNext.
