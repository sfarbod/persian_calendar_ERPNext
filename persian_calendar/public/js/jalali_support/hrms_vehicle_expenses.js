/**
 * HRMS Vehicle Expenses — inject Company filter for Business Calendar chart periods.
 * Data rows stay upstream; company is used only when calling get_period_list.
 */
(function () {
	function injectCompanyFilter() {
		const report = frappe.query_reports && frappe.query_reports["Vehicle Expenses"];
		if (!report || !report.filters) {
			return;
		}
		if (report.filters.some((f) => f.fieldname === "company")) {
			return;
		}
		report.filters.unshift({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 0,
		});
	}

	if (frappe.query_reports && frappe.query_reports["Vehicle Expenses"]) {
		injectCompanyFilter();
	}
	$(document).on("app_ready", injectCompanyFilter);
	frappe.after_ajax &&
		frappe.after_ajax(() => {
			injectCompanyFilter();
		});
})();
