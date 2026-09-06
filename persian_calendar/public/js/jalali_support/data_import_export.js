// Jalali toggles for Data Export / List View Export Data (persian_calendar)
//
// Extension points (Frappe v16):
// - Data Export form: Custom Field / injected checkbox + open_url_post →
//   frappe.core.doctype.data_export.exporter.export_data
// - List View Export: frappe.data_import.DataExporter (lazy bundle
//   data_import_tools.bundle.js) → download_template → data_import.Exporter
//
// Do not convert CSV text with regex. Conversion is fieldtype-driven on the server.

frappe.provide("persian_calendar.data_io");

const JALALI_DATA_IO_DEBUG = false;
const DATA_EXPORT_API_METHOD = "frappe.core.doctype.data_export.exporter.export_data";
const DOWNLOAD_TEMPLATE_API =
	"/api/method/frappe.core.doctype.data_import.data_import.download_template";
const DATA_IMPORT_TOOLS_BUNDLE = "data_import_tools.bundle.js";

function jalali_data_io_log(...args) {
	if (JALALI_DATA_IO_DEBUG) {
		console.log("[Jalali Data IO]", ...args);
	}
}

function get_data_export_frm() {
	try {
		const route = frappe.get_route?.() || [];
		if (
			route[0] === "Form" &&
			route[1] === "Data Export" &&
			cur_frm?.doctype === "Data Export"
		) {
			return cur_frm;
		}
	} catch (e) {
		/* ignore */
	}
	return null;
}

function get_export_jalali_flag(frm) {
	if (!frm || !frm.doc) {
		return 0;
	}
	const ctrl = frm.fields_dict?.export_dates_as_jalali;
	if (ctrl && typeof ctrl.get_value === "function") {
		return ctrl.get_value() ? 1 : 0;
	}
	if (frm.doc.export_dates_as_jalali) {
		return 1;
	}
	return frm._export_dates_as_jalali ? 1 : 0;
}

function inject_export_jalali_flag_into_args(url, args) {
	if (!url || String(url).indexOf(DATA_EXPORT_API_METHOD) === -1) {
		return;
	}
	const frm = get_data_export_frm();
	const value = frm ? get_export_jalali_flag(frm) : 0;
	try {
		if (args == null) {
			return;
		}
		if (typeof FormData !== "undefined" && args instanceof FormData) {
			args.set("export_dates_as_jalali", String(value));
		} else if (typeof args === "object") {
			args.export_dates_as_jalali = value;
		}
		if (JALALI_DATA_IO_DEBUG) {
			jalali_data_io_log("open_url_post export", { url, export_dates_as_jalali: value });
		}
	} catch (e) {
		console.error("[persian_calendar] open_url_post inject failed", e);
	}
}

/** Inject Jalali flag into Data Export POST; leave Frappe's Export handler unchanged. */
function patch_open_url_post_for_data_export() {
	if (window.open_url_post && window.open_url_post._jalali_data_export_patched) {
		return;
	}
	const original_open_url_post = window.open_url_post;
	if (typeof original_open_url_post !== "function") {
		setTimeout(patch_open_url_post_for_data_export, 50);
		return;
	}

	function jalali_open_url_post(URL, PARAMS, new_window) {
		try {
			inject_export_jalali_flag_into_args(URL, PARAMS);
		} catch (e) {
			console.error("[persian_calendar] open_url_post patch error", e);
		}
		return original_open_url_post.apply(this, arguments);
	}

	jalali_open_url_post._jalali_data_export_patched = true;
	window.open_url_post = jalali_open_url_post;
}

function inject_data_export_jalali_checkbox(frm) {
	if (!frm) {
		return;
	}
	if (frm.fields_dict?.export_dates_as_jalali) {
		return;
	}
	if (frm._jalali_export_checkbox_injected) {
		return;
	}

	let anchor =
		frm.fields_dict.file_type?.$wrapper ||
		frm.fields_dict.export_without_main_header?.$wrapper;
	if (!anchor?.length && frm.wrapper) {
		anchor = frm.wrapper.jquery ? frm.wrapper : $(frm.wrapper);
	}
	if (!anchor?.length && frm.page?.wrapper) {
		anchor = frm.page.wrapper.jquery ? frm.page.wrapper : $(frm.page.wrapper);
	}

	if (!anchor || !anchor.length) {
		return;
	}

	const $row = $(`
		<div class="form-group frappe-control jalali-export-dates-check" style="margin-top: 8px;">
			<div class="checkbox">
				<label>
					<input type="checkbox" class="jalali-export-dates-input">
					<span>${__("Export dates as Jalali")}</span>
				</label>
			</div>
		</div>
	`);

	anchor.closest(".form-column, .form-section, .form-layout").length
		? anchor.closest(".form-column").append($row)
		: anchor.after($row);

	$row.find(".jalali-export-dates-input").on("change", function () {
		frm._export_dates_as_jalali = $(this).prop("checked") ? 1 : 0;
	});

	frm._jalali_export_checkbox_injected = true;
	frm._export_dates_as_jalali = frm._export_dates_as_jalali || 0;
}

function setup_data_export_form() {
	frappe.ui.form.on("Data Export", {
		refresh(frm) {
			inject_data_export_jalali_checkbox(frm);
		},
	});
}

function setup_data_import_form() {
	/* Custom Field import_dates_from_jalali is on the form; no extra JS required. */
}

function jalali_export_field_df() {
	return {
		fieldtype: "Check",
		fieldname: "export_dates_as_jalali",
		label: __("Export dates as Jalali"),
		default: 0,
	};
}

/**
 * Insert Export dates as Jalali after Export Type (or File Type) in dialog field defs.
 * Dialog has no add_field(); FieldGroup.add_fields appends at the end — wrong UX.
 */
function with_jalali_export_field(fields) {
	if (!Array.isArray(fields)) {
		return fields;
	}
	if (fields.some((f) => f && f.fieldname === "export_dates_as_jalali")) {
		return fields;
	}
	const out = fields.slice();
	const after_export_type = out.findIndex((f) => f && f.fieldname === "export_records");
	const after_file_type = out.findIndex((f) => f && f.fieldname === "file_type");
	const insert_at =
		after_export_type >= 0
			? after_export_type + 1
			: after_file_type >= 0
			? after_file_type + 1
			: 1;
	out.splice(insert_at, 0, jalali_export_field_df());
	return out;
}

function apply_data_exporter_jalali_patch() {
	const DataExporter = frappe.data_import?.DataExporter;
	if (!DataExporter || DataExporter._jalali_dialog_patched) {
		return Boolean(DataExporter);
	}
	DataExporter._jalali_dialog_patched = true;

	const _make_dialog = DataExporter.prototype.make_dialog;
	DataExporter.prototype.make_dialog = function (filetype = "CSV") {
		const OrigDialog = frappe.ui.Dialog;
		let restored = false;
		const restore = () => {
			if (!restored) {
				frappe.ui.Dialog = OrigDialog;
				restored = true;
			}
		};

		// Temporarily wrap Dialog so Export Data fields include the Jalali checkbox
		// at construction time (upgrade-safe vs copying make_dialog).
		frappe.ui.Dialog = class JalaliAwareExportDialog extends OrigDialog {
			constructor(opts) {
				restore();
				if (opts && Array.isArray(opts.fields)) {
					opts = Object.assign({}, opts, {
						fields: with_jalali_export_field(opts.fields),
					});
				}
				super(opts);
			}
		};

		try {
			return _make_dialog.call(this, filetype);
		} finally {
			restore();
		}
	};

	const _export_records = DataExporter.prototype.export_records;
	DataExporter.prototype.export_records = function () {
		// Keep stock export_records; only append the per-export Jalali flag.
		const orig_open = window.open_url_post;
		const exporter = this;
		window.open_url_post = function (url, args, new_window) {
			try {
				if (
					url &&
					String(url).indexOf("download_template") !== -1 &&
					args &&
					typeof args === "object" &&
					!(typeof FormData !== "undefined" && args instanceof FormData)
				) {
					const values = exporter.dialog?.get_values?.() || {};
					args.export_dates_as_jalali = values.export_dates_as_jalali ? 1 : 0;
					jalali_data_io_log("list export flag", args.export_dates_as_jalali);
				}
			} catch (e) {
				console.error("[persian_calendar] list export flag inject failed", e);
			}
			return orig_open.apply(this, arguments);
		};
		try {
			return _export_records.apply(this, arguments);
		} finally {
			window.open_url_post = orig_open;
		}
	};

	jalali_data_io_log("DataExporter dialog patched");
	return true;
}

/**
 * DataExporter lives in data_import_tools.bundle.js and is loaded via frappe.require
 * from BulkOperations.export — patch after that bundle loads.
 */
function patch_data_exporter_dialog() {
	if (apply_data_exporter_jalali_patch()) {
		return;
	}
	if (frappe.require?._jalali_data_exporter_hooked) {
		return;
	}

	const original_require = frappe.require.bind(frappe);
	function hooked_require(assets, callback) {
		const list = Array.isArray(assets) ? assets : [assets];
		const loads_exporter = list.some(
			(a) => a && String(a).indexOf("data_import_tools") !== -1
		);
		if (loads_exporter && typeof callback === "function") {
			const user_cb = callback;
			callback = function () {
				apply_data_exporter_jalali_patch();
				return user_cb.apply(this, arguments);
			};
		}
		return original_require(assets, callback);
	}
	hooked_require._jalali_data_exporter_hooked = true;
	frappe.require = hooked_require;
}

$(() => {
	patch_open_url_post_for_data_export();
	setup_data_export_form();
	setup_data_import_form();
	patch_data_exporter_dialog();
});
