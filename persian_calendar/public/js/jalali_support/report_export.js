/**
 * Jalali export checkbox for Query Report / Script Report / Report View.
 *
 * Upstream: frappe.report_utils.get_export_dialog (shared by query_report.js
 * and report_view.js). Injects "Export dates as Jalali" and forwards the flag
 * on open_url_post / frappe.call for export_query cmds.
 */

function jalali_report_export_log(...args) {
	if (frappe.boot?.developer_mode || window.persian_calendar_debug) {
		console.debug("[persian_calendar:report_export]", ...args);
	}
}

function jalali_report_export_field_df() {
	return {
		fieldtype: "Check",
		fieldname: "export_dates_as_jalali",
		label: __("Export dates as Jalali"),
		default: 0,
	};
}

function with_jalali_report_export_field(extra_fields) {
	const fields = Array.isArray(extra_fields) ? extra_fields.slice() : [];
	if (fields.some((f) => f && f.fieldname === "export_dates_as_jalali")) {
		return fields;
	}
	fields.push(jalali_report_export_field_df());
	return fields;
}

function is_report_export_cmd(cmd) {
	return (
		cmd === "frappe.desk.query_report.export_query" ||
		cmd === "frappe.desk.reportview.export_query"
	);
}

function inject_jalali_flag_into_args(args, flag) {
	if (!args || typeof args !== "object") {
		return;
	}
	if (typeof FormData !== "undefined" && args instanceof FormData) {
		args.set("export_dates_as_jalali", String(flag));
		return;
	}
	args.export_dates_as_jalali = flag;
}

function apply_report_export_dialog_patch() {
	const utils = frappe.report_utils;
	if (!utils || typeof utils.get_export_dialog !== "function") {
		return false;
	}
	if (utils.get_export_dialog._jalali_report_patched) {
		return true;
	}

	const _orig = utils.get_export_dialog;
	utils.get_export_dialog = function (report_name, extra_fields, callback) {
		const fields = with_jalali_report_export_field(extra_fields);
		const wrapped = function (values) {
			const flag = values && values.export_dates_as_jalali ? 1 : 0;
			frappe._jalali_report_export_flag = flag;
			jalali_report_export_log("dialog flag", flag);
			return callback.apply(this, arguments);
		};
		return _orig.call(this, report_name, fields, wrapped);
	};
	utils.get_export_dialog._jalali_report_patched = true;
	utils.get_export_dialog._jalali_orig = _orig;
	jalali_report_export_log("get_export_dialog patched");
	return true;
}

function apply_report_export_transport_patch() {
	if (window.open_url_post && !window.open_url_post._jalali_report_patched) {
		const _orig_open = window.open_url_post;
		window.open_url_post = function (url, args, new_window) {
			try {
				if (args && is_report_export_cmd(args.cmd)) {
					const flag =
						typeof frappe._jalali_report_export_flag !== "undefined"
							? frappe._jalali_report_export_flag
							: 0;
					inject_jalali_flag_into_args(args, flag);
					jalali_report_export_log("open_url_post flag", flag);
				}
			} catch (e) {
				console.error("[persian_calendar] report export flag inject failed", e);
			}
			return _orig_open.apply(this, arguments);
		};
		window.open_url_post._jalali_report_patched = true;
		window.open_url_post._jalali_orig = _orig_open;
	}

	if (frappe.call && !frappe.call._jalali_report_patched) {
		const _orig_call = frappe.call;
		frappe.call = function (opts) {
			try {
				const o = opts || {};
				const method = o.method || (o.args && o.args.cmd);
				const args = o.args;
				if (args && is_report_export_cmd(method || args.cmd)) {
					const flag =
						typeof frappe._jalali_report_export_flag !== "undefined"
							? frappe._jalali_report_export_flag
							: 0;
					inject_jalali_flag_into_args(args, flag);
					jalali_report_export_log("frappe.call flag", flag);
				}
			} catch (e) {
				console.error("[persian_calendar] report export call flag inject failed", e);
			}
			return _orig_call.apply(this, arguments);
		};
		frappe.call._jalali_report_patched = true;
		frappe.call._jalali_orig = _orig_call;
	}

	return true;
}

function setup_report_export_jalali() {
	apply_report_export_dialog_patch();
	apply_report_export_transport_patch();
}

frappe.after_ajax(() => {
	setup_report_export_jalali();
});

$(document).ready(() => {
	setup_report_export_jalali();
});
