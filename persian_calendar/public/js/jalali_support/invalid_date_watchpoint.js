/**
 * Debug watchpoint: log stack when "Invalid date" is written to inputs or model.
 * Enable: localStorage.setItem("persian_calendar_invalid_date_watch", "1")
 * Or: frappe.persian_calendar.runtime.enableInvalidDateWatch()
 */
(function () {
  if (typeof frappe === "undefined") {
    return;
  }
  frappe.provide("frappe.persian_calendar");
  frappe.persian_calendar = frappe.persian_calendar || {};
  frappe.persian_calendar.runtime = frappe.persian_calendar.runtime || {};

  const FLAG = "persian_calendar_invalid_date_watch";
  const TARGET_FIELDS = new Set(["posting_time", "from_time", "to_time"]);

  function watchEnabled() {
    try {
      return localStorage.getItem(FLAG) === "1";
    } catch (e) {
      return false;
    }
  }

  function isInvalidDateValue(val) {
    if (val == null) return false;
    return String(val).trim() === "Invalid date";
  }

  function fieldContextFromInput(el) {
    const $ = window.jQuery;
    if (!el || !$) {
      return {};
    }
    const $input = $(el);
    const $fc = $input.closest(".frappe-control");
    let fieldname =
      $fc.attr("data-fieldname") ||
      $input.attr("data-fieldname") ||
      $input.attr("name") ||
      null;
    let fieldtype =
      $fc.attr("data-fieldtype") || $input.attr("data-fieldtype") || null;
    let doctype = null;
    if (typeof cur_frm !== "undefined" && cur_frm?.doc?.doctype) {
      doctype = cur_frm.doc.doctype;
    }
    const gridRow = $input.closest(".grid-row").data("grid_row");
    if (gridRow?.doc?.doctype) {
      doctype = gridRow.doc.doctype;
    }
    return {
      fieldname,
      fieldtype,
      doctype,
      inputClass: el.className || "",
    };
  }

  function logInvalidAssignment(source, detail) {
    const rt = frappe.persian_calendar?.runtime;
    const pref = rt?.getActiveCalendarPreferenceSync?.() || null;
    const route =
      (typeof frappe !== "undefined" && frappe.get_route && frappe.get_route()) ||
      null;
    console.warn("[persian_calendar Invalid date watch]", source, {
      ...detail,
      calendar_preference: pref,
      route,
    });
    console.trace("[persian_calendar Invalid date watch] stack");
    if (typeof window !== "undefined") {
      window.__persianCalendarInvalidDateLog =
        window.__persianCalendarInvalidDateLog || [];
      window.__persianCalendarInvalidDateLog.push({
        at: Date.now(),
        source,
        detail: { ...detail, calendar_preference: pref, route },
      });
    }
  }

  function maybeLog(source, value, extra) {
    if (!watchEnabled() || !isInvalidDateValue(value)) {
      return;
    }
    logInvalidAssignment(source, { value, ...extra });
  }

  let inputPatched = false;
  let modelPatched = false;
  let frmSetPatched = false;

  function installInputValueWatchpoint() {
    if (inputPatched || typeof HTMLInputElement === "undefined") {
      return;
    }
    inputPatched = true;
    const desc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
    if (!desc || !desc.set || !desc.get) {
      return;
    }
    Object.defineProperty(HTMLInputElement.prototype, "value", {
      configurable: true,
      enumerable: desc.enumerable,
      get: desc.get,
      set: function (next) {
        if (watchEnabled() && isInvalidDateValue(next)) {
          maybeLog("HTMLInputElement.value", next, fieldContextFromInput(this));
        }
        desc.set.call(this, next);
      },
    });
  }

  function installModelSetValueWatchpoint() {
    if (modelPatched || !frappe.model?.set_value) {
      return;
    }
    modelPatched = true;
    const orig = frappe.model.set_value;
    frappe.model.set_value = function (doctype, docname, fieldname, value) {
      if (
        watchEnabled() &&
        isInvalidDateValue(value) &&
        (TARGET_FIELDS.has(fieldname) ||
          fieldname === "from_time" ||
          fieldname === "to_time" ||
          fieldname === "posting_time")
      ) {
        maybeLog("frappe.model.set_value", value, {
          doctype,
          docname,
          fieldname,
        });
      }
      return orig.apply(this, arguments);
    };
  }

  function installFrmAndControlWatchpoints() {
    if (frmSetPatched) {
      return;
    }
    const tryPatch = () => {
      if (!frappe.ui?.form?.ControlData?.prototype?.set_input) {
        return false;
      }
      if (!frmSetPatched) {
        frmSetPatched = true;
        const origSetInput = frappe.ui.form.ControlData.prototype.set_input;
        frappe.ui.form.ControlData.prototype.set_input = function (value) {
          if (watchEnabled() && isInvalidDateValue(value)) {
            maybeLog("control.set_input", value, {
              fieldname: this.df?.fieldname,
              fieldtype: this.df?.fieldtype,
              doctype: this.frm?.doc?.doctype || this.doc?.doctype,
              inputClass: this.$input?.[0]?.className || "",
            });
          }
          return origSetInput.call(this, value);
        };
      }
      return true;
    };
    if (!tryPatch()) {
      setTimeout(tryPatch, 50);
    }
  }

  function installWatchpoints() {
    if (!watchEnabled()) {
      return;
    }
    installInputValueWatchpoint();
    installModelSetValueWatchpoint();
    installFrmAndControlWatchpoints();
  }

  frappe.persian_calendar.runtime.enableInvalidDateWatch = function () {
    try {
      localStorage.setItem(FLAG, "1");
    } catch (e) {
      /* ignore */
    }
    installWatchpoints();
  };

  frappe.persian_calendar.runtime.disableInvalidDateWatch = function () {
    try {
      localStorage.removeItem(FLAG);
    } catch (e) {
      /* ignore */
    }
  };

  frappe.persian_calendar.runtime.getInvalidDateLog = function () {
    return (
      (typeof window !== "undefined" && window.__persianCalendarInvalidDateLog) ||
      []
    );
  };

  frappe.persian_calendar.runtime.resetInvalidDateLog = function () {
    if (typeof window !== "undefined") {
      window.__persianCalendarInvalidDateLog = [];
    }
  };

  if (watchEnabled()) {
    installWatchpoints();
  }

  if (typeof frappe !== "undefined" && frappe.ready) {
    frappe.ready(() => installWatchpoints());
  }
})();
