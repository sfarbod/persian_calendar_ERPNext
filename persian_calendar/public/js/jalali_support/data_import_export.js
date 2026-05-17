// Jalali toggles for Data Export / Data Import (persian_calendar)

frappe.provide("persian_calendar.data_io");

const JALALI_DATA_IO_DEBUG = true;
const DATA_EXPORT_API_METHOD = "frappe.core.doctype.data_export.exporter.export_data";

function jalali_data_io_log(...args) {
	if (JALALI_DATA_IO_DEBUG) {
		console.log("[Jalali Data IO]", ...args);
	}
}

function get_data_export_frm() {
	try {
		const route = frappe.get_route?.() || [];
		if (route[0] === "Form" && route[1] === "Data Export" && cur_frm?.doctype === "Data Export") {
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
			// Core always passes an object; do not replace arguments[1] — only mutate when present.
			return;
		}
		if (typeof FormData !== "undefined" && args instanceof FormData) {
			args.set("export_dates_as_jalali", String(value));
		} else if (typeof args === "object") {
			args.export_dates_as_jalali = value;
		}
		console.log("[Jalali Data IO] open_url_post patch hit", url, args);
		console.log("[Jalali Data IO] export_dates_as_jalali", value);
	} catch (e) {
		console.warn("[Jalali Data IO] open_url_post inject failed", e);
	}
}

/** Inject Jalali flag into Data Export POST; leave Frappe's Export handler unchanged. */
function patch_open_url_post_for_data_export() {
	if (window.open_url_post && window.open_url_post._jalali_data_export_patched) {
		return;
	}
	const original_open_url_post = window.open_url_post;
	if (typeof original_open_url_post !== "function") {
		jalali_data_io_log("open_url_post not ready, retry patch");
		setTimeout(patch_open_url_post_for_data_export, 50);
		return;
	}

	function jalali_open_url_post(URL, PARAMS, new_window) {
		try {
			inject_export_jalali_flag_into_args(URL, PARAMS);
		} catch (e) {
			console.warn("[Jalali Data IO] open_url_post patch error", e);
		}
		return original_open_url_post.apply(this, arguments);
	}

	jalali_open_url_post._jalali_data_export_patched = true;
	window.open_url_post = jalali_open_url_post;
	jalali_data_io_log("patched window.open_url_post for Data Export");
}

function inject_data_export_jalali_checkbox(frm) {
	if (!frm) {
		return;
	}
	if (frm.fields_dict?.export_dates_as_jalali) {
		jalali_data_io_log("Data Export: using Custom Field export_dates_as_jalali");
		return;
	}
	if (frm._jalali_export_checkbox_injected) {
		return;
	}

	const anchor =
		frm.fields_dict.file_type?.$wrapper ||
		frm.fields_dict.export_without_main_header?.$wrapper ||
		frm.wrapper;

	if (!anchor || !anchor.length) {
		jalali_data_io_log("Data Export: no anchor for injected checkbox");
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
	jalali_data_io_log("Data Export: injected export_dates_as_jalali checkbox");
}

function setup_data_export_form() {
	frappe.ui.form.on("Data Export", {
		onload(frm) {
			jalali_data_io_log("Data Export form onload", frappe.get_route());
		},
		refresh(frm) {
			jalali_data_io_log("Data Export form refresh", frappe.get_route());
			inject_data_export_jalali_checkbox(frm);
		},
	});
}

function setup_data_import_form() {
	frappe.ui.form.on("Data Import", {
		onload(frm) {
			jalali_data_io_log("Data Import form onload", frappe.get_route());
		},
		refresh(frm) {
			jalali_data_io_log(
				"Data Import refresh",
				frappe.get_route(),
				"has field",
				!!frm.fields_dict.import_dates_from_jalali
			);
		},
	});
}

function patch_data_exporter_dialog() {
	const DataExporter = frappe.data_import?.DataExporter;
	if (!DataExporter || DataExporter._jalali_dialog_patched) {
		return;
	}
	DataExporter._jalali_dialog_patched = true;

	const _make_dialog = DataExporter.prototype.make_dialog;
	DataExporter.prototype.make_dialog = function (filetype = "CSV") {
		_make_dialog.call(this, filetype);
		const dialog = this.dialog;
		if (!dialog || dialog._jalali_export_field_added) {
			return;
		}
		if (typeof dialog.add_field === "function") {
			dialog.add_field({
				fieldtype: "Check",
				fieldname: "export_dates_as_jalali",
				label: __("Export dates as Jalali"),
				insert_after: "file_type",
			});
			dialog._jalali_export_field_added = true;
			jalali_data_io_log("Export Data dialog: added export_dates_as_jalali");
		}
	};

	DataExporter.prototype.export_records = function () {
		const method = "/api/method/frappe.core.doctype.data_import.data_import.download_template";
		const multicheck_fields = this.dialog.fields
			.filter((df) => df.fieldtype === "MultiCheck")
			.map((df) => df.fieldname);
		const values = this.dialog.get_values();
		const doctype_field_map = { ...values };
		for (const key of Object.keys(doctype_field_map)) {
			if (!multicheck_fields.includes(key)) {
				delete doctype_field_map[key];
			}
		}
		let filters = null;
		if (values.export_records === "by_filter") {
			filters = this.get_filters();
		}
		jalali_data_io_log(
			"Export Data dialog download",
			values.export_dates_as_jalali ? 1 : 0
		);
		open_url_post(method, {
			doctype: this.doctype,
			file_type: values.file_type,
			export_records: values.export_records,
			export_fields: doctype_field_map,
			export_filters: filters,
			export_dates_as_jalali: values.export_dates_as_jalali ? 1 : 0,
		});
	};
}

function setup_route_hooks() {
	frappe.router.on("change", () => {
		jalali_data_io_log("route change", frappe.get_route());
	});
}

$(() => {
	jalali_data_io_log("loaded");
	patch_open_url_post_for_data_export();
	setup_data_export_form();
	setup_data_import_form();
	patch_data_exporter_dialog();
	setup_route_hooks();
});
