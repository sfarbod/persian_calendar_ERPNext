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
		// Jalali is the default; user may uncheck for Gregorian on this export only.
		default: 1,
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

function cint_like(v) {
	if (v === true || v === 1 || v === "1") {
		return 1;
	}
	if (v === false || v === 0 || v === "0" || v === "" || v == null) {
		return 0;
	}
	return v ? 1 : 0;
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
			// Respect the dialog value for this export only (default field is checked).
			// Explicit unchecked → 0; do not fall back to a stale prior flag.
			const flag = values && cint_like(values.export_dates_as_jalali) ? 1 : 0;
			frappe._jalali_report_export_flag = flag;
			jalali_report_export_log("dialog flag", flag);
			return callback.apply(this, arguments);
		};
		const dialog = _orig.call(this, report_name, fields, wrapped);
		// Ensure default stays checked if the dialog framework clears Check defaults.
		try {
			if (dialog && typeof dialog.set_value === "function") {
				const current = dialog.get_value?.("export_dates_as_jalali");
				if (current === undefined || current === null || current === "") {
					dialog.set_value("export_dates_as_jalali", 1);
				}
			}
		} catch (e) {
			jalali_report_export_log("default set_value skipped", e);
		}
		return dialog;
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
					// Prefer the value already on args (explicit user choice), else dialog flag,
					// else Jalali default (1). Never treat an explicit 0 as missing.
					let flag;
					if (
						args.export_dates_as_jalali !== undefined &&
						args.export_dates_as_jalali !== null &&
						args.export_dates_as_jalali !== ""
					) {
						flag = cint_like(args.export_dates_as_jalali);
					} else if (typeof frappe._jalali_report_export_flag !== "undefined") {
						flag = cint_like(frappe._jalali_report_export_flag);
					} else {
						flag = 1;
					}
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
					let flag;
					if (
						args.export_dates_as_jalali !== undefined &&
						args.export_dates_as_jalali !== null &&
						args.export_dates_as_jalali !== ""
					) {
						flag = cint_like(args.export_dates_as_jalali);
					} else if (typeof frappe._jalali_report_export_flag !== "undefined") {
						flag = cint_like(frappe._jalali_report_export_flag);
					} else {
						flag = 1;
					}
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
