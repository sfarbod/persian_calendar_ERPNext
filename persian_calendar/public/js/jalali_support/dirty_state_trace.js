/**
 * Trace client mutations that mark forms dirty (post-save debugging).
 * Enable: localStorage.setItem("persian_calendar_dirty_trace", "1")
 * Or: frappe.persian_calendar.runtime.enableDirtyStateTrace()
 */
(function () {
  if (typeof frappe === "undefined") {
    return;
  }
  frappe.provide("frappe.persian_calendar");
  frappe.persian_calendar.runtime = frappe.persian_calendar.runtime || {};

  const FLAG = "persian_calendar_dirty_trace";
  let savePhase = "idle";

  function traceEnabled() {
    try {
      return localStorage.getItem(FLAG) === "1";
    } catch (e) {
      return false;
    }
  }

  function context() {
    const rt = frappe.persian_calendar?.runtime;
    return {
      savePhase,
      effective_calendar_mode: rt?.getEffectiveCalendarModeSync?.() || null,
      route: frappe.get_route?.() || null,
      doctype: typeof cur_frm !== "undefined" ? cur_frm?.doc?.doctype : null,
      docname: typeof cur_frm !== "undefined" ? cur_frm?.doc?.name : null,
      is_dirty: typeof cur_frm !== "undefined" ? cur_frm?.is_dirty?.() : null,
    };
  }

  function logMutation(kind, detail) {
    if (!traceEnabled()) {
      return;
    }
    const entry = {
      at: Date.now(),
      kind,
      ...detail,
      ...context(),
    };
    console.warn("[persian_calendar dirty trace]", entry);
    console.trace("[persian_calendar dirty trace] stack");
    window.__persianCalendarDirtyTraceLog =
      window.__persianCalendarDirtyTraceLog || [];
    window.__persianCalendarDirtyTraceLog.push(entry);
  }

  function valuesDiffer(a, b) {
    if (a === b) {
      return false;
    }
    return String(a ?? "") !== String(b ?? "");
  }

  let installed = false;

  function installDirtyStateTrace() {
    if (installed || !traceEnabled()) {
      return;
    }
    installed = true;

    if (frappe.ui?.form?.Form?.prototype?.dirty) {
      const origDirty = frappe.ui.form.Form.prototype.dirty;
      frappe.ui.form.Form.prototype.dirty = function () {
        logMutation("frm.dirty", { fieldname: null, old_value: null, new_value: null });
        return origDirty.apply(this, arguments);
      };
    }

    if (frappe.model?.set_value) {
      const origModelSet = frappe.model.set_value;
      frappe.model.set_value = function (doctype, docname, fieldname, value) {
        const doc =
          $.isPlainObject(doctype) ? doctype : locals[doctype] && locals[doctype][docname];
        const fn = $.isPlainObject(doctype) ? docname : fieldname;
        const val = $.isPlainObject(doctype) ? fieldname : value;
        const old = doc ? doc[fn] : undefined;
        if (doc && valuesDiffer(old, val)) {
          logMutation("frappe.model.set_value", {
            fieldname: fn,
            old_value: old,
            new_value: val,
            doctype: doc.doctype,
            docname: doc.name,
          });
        }
        return origModelSet.apply(this, arguments);
      };
    }

    if (frappe.ui?.form?.ControlData?.prototype?.set_value) {
      const origControlSet = frappe.ui.form.ControlData.prototype.set_value;
      frappe.ui.form.ControlData.prototype.set_value = function (value, force) {
        const old = this.get_model_value?.() ?? this.doc?.[this.df?.fieldname];
        if (valuesDiffer(old, value)) {
          logMutation("control.set_value", {
            fieldname: this.df?.fieldname,
            fieldtype: this.df?.fieldtype,
            old_value: old,
            new_value: value,
            force_set_value: force,
          });
        }
        return origControlSet.apply(this, arguments);
      };
    }

    if (frappe.ui?.form?.Form?.prototype?.set_value) {
      const origFrmSet = frappe.ui.form.Form.prototype.set_value;
      frappe.ui.form.Form.prototype.set_value = function (field, value) {
        const old = this.doc?.[field];
        if (valuesDiffer(old, value)) {
          logMutation("frm.set_value", {
            fieldname: field,
            old_value: old,
            new_value: value,
          });
        }
        return origFrmSet.apply(this, arguments);
      };
    }

    frappe.ui.form.on("*", {
      before_save() {
        savePhase = "before_save";
      },
      after_save() {
        savePhase = "after_save";
        setTimeout(() => {
          savePhase = "post_after_save";
        }, 0);
        setTimeout(() => {
          savePhase = "idle";
        }, 3000);
      },
    });
  }

  Object.assign(frappe.persian_calendar.runtime, {
    enableDirtyStateTrace() {
      try {
        localStorage.setItem(FLAG, "1");
      } catch (e) {
        /* ignore */
      }
      installed = false;
      installDirtyStateTrace();
    },
    disableDirtyStateTrace() {
      try {
        localStorage.removeItem(FLAG);
      } catch (e) {
        /* ignore */
      }
    },
    getDirtyTraceLog() {
      return window.__persianCalendarDirtyTraceLog || [];
    },
    resetDirtyTraceLog() {
      window.__persianCalendarDirtyTraceLog = [];
    },
  });

  installDirtyStateTrace();
})();
