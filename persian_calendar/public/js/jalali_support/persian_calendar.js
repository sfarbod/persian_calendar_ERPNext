(function() {
  frappe.provide("frappe.ui.form");


  // Global variables - will be populated asynchronously
  let jalaliEnabled = null; // null = not checked yet, true/false = checked
  let EFFECTIVE_CALENDAR = {
    display_calendar: "Gregorian",
    week_start: 6,
    week_end: 5,
  };
  let FIRST_DAY = 6;

  function getEffectiveCalendarMode() {
    const rt = frappe.persian_calendar?.runtime;
    if (rt?.getEffectiveCalendarModeSync) {
      return rt.getEffectiveCalendarModeSync();
    }
    const boot = frappe.boot?.persian_calendar;
    if (!boot) {
      return "Gregorian";
    }
    return boot.display_calendar === "Jalali" ? "Jalali" : "Gregorian";
  }

  function syncEffectiveCalendarFromBoot() {
    const rt = frappe.persian_calendar?.runtime;
    if (rt?.syncBootDisplayCalendar) {
      rt.syncBootDisplayCalendar();
    }
    const b = frappe.boot?.persian_calendar;
    if (!b) {
      return;
    }
    const mode = getEffectiveCalendarMode();
    EFFECTIVE_CALENDAR = {
      display_calendar: mode,
      week_start: b.week_start ?? 6,
      week_end: b.week_end ?? 5,
    };
    FIRST_DAY = EFFECTIVE_CALENDAR.week_start;
  }

  if (frappe.boot?.persian_calendar) {
    syncEffectiveCalendarFromBoot();
  }
  
  // Cache for calendar settings to avoid multiple API calls
  let calendarSettingsCache = null;
  let calendarSettingsPromise = null;

  async function getCalendarSettings() {
    const rt = frappe.persian_calendar?.runtime;
    if (rt?.fetchCalendarSettings) {
      const cache = await rt.fetchCalendarSettings();
      calendarSettingsCache = cache;
      if (cache?.calendar) {
        EFFECTIVE_CALENDAR = cache.calendar;
        FIRST_DAY = cache.firstDay ?? cache.calendar.week_start ?? 6;
      }
      const mode = rt.getEffectiveCalendarModeSync?.();
      if (mode) {
        EFFECTIVE_CALENDAR.display_calendar = mode;
        if (calendarSettingsCache?.calendar) {
          calendarSettingsCache.calendar.display_calendar = mode;
        }
      }
      jalaliEnabled = !!cache?.enabled;
      return cache;
    }
    if (calendarSettingsCache !== null) {
      return calendarSettingsCache;
    }
    return { enabled: false, calendar: { display_calendar: "Gregorian" } };
  }

  // Start loading calendar settings immediately (but don't wait)
  getCalendarSettings();

  const JALALI_DATE_DEBUG = false;
  const JALALI_DATETIME_DEBUG = false;
  const JALALI_GRID_DATETIME_DEBUG = false;
  const JALALI_GRID_POSITION_DEBUG = false;
  const JALALI_MAIN_DISPLAY_DEBUG = false;

  function shouldUseJalaliCalendar() {
    const rt = frappe.persian_calendar?.runtime;
    if (rt?.shouldUseJalaliCalendarSync) {
      const result = rt.shouldUseJalaliCalendarSync();
      pcTrace("shouldUseJalaliCalendar", {
        result,
        boot: frappe.boot?.persian_calendar,
        cache: rt.getSettingsCache?.(),
      });
      return result;
    }
    const mode = getEffectiveCalendarMode();
    if (frappe.boot?.persian_calendar) {
      return mode === "Jalali";
    }
    if (calendarSettingsCache !== null) {
      return (
        calendarSettingsCache.enabled &&
        calendarSettingsCache.calendar?.display_calendar !== "Gregorian"
      );
    }
    return false;
  }

  /** Frappe v16: frm.wrapper may be DOM node, jQuery, or missing during lifecycle. */
  function getFormWrapper(frm) {
    if (!frm) {
      return $();
    }
    if (frm.wrapper && frm.wrapper.jquery) {
      return frm.wrapper;
    }
    if (frm.wrapper) {
      return $(frm.wrapper);
    }
    if (frm.page && frm.page.wrapper) {
      if (frm.page.wrapper.jquery) {
        return frm.page.wrapper;
      }
      return $(frm.page.wrapper);
    }
    return $(document);
  }

  function getGridRowWrapper(grid_row) {
    if (!grid_row) {
      return $();
    }
    const w = grid_row.wrapper;
    if (w && w.jquery) {
      return w;
    }
    if (w) {
      return $(w);
    }
    return $();
  }

  function gridRowContainsInput(grid_row, $input) {
    const $row = getGridRowWrapper(grid_row);
    return !!( $row.length && $input?.length && $row.find($input).length );
  }

  function jalaliGridLog(...args) {
    if (JALALI_GRID_DATETIME_DEBUG) {
      console.log("[jalali_grid_datetime]", ...args);
    }
  }

  function jalaliGridPositionLog(...args) {
    if (JALALI_GRID_POSITION_DEBUG) {
      console.log("[jalali_grid_position]", ...args);
    }
  }

  function jalaliMainDisplayLog(payload) {
    if (JALALI_MAIN_DISPLAY_DEBUG) {
      console.log("[jalali_main_display]", payload);
    }
  }

  function getControlModelValue(control) {
    if (!control?.df?.fieldname) {
      return null;
    }
    const fn = control.df.fieldname;
    if (control.frm?.doc && control.frm.doc[fn] != null && control.frm.doc[fn] !== "") {
      return control.frm.doc[fn];
    }
    if (control.doctype && control.docname && frappe.model?.get_value) {
      const v = frappe.model.get_value(control.doctype, control.docname, fn);
      if (v != null && v !== "") {
        return v;
      }
    }
    if (control.doc && control.doc[fn] != null && control.doc[fn] !== "") {
      return control.doc[fn];
    }
    return control.value;
  }

  function jalaliEscapeDisplay(text) {
    return frappe.utils?.escape_html ? frappe.utils.escape_html(text) : String(text);
  }

  function setJalaliOnDisplayElement($el, display) {
    if (!$el || !$el.length) {
      return false;
    }
    const target = String(display);
    const current = ($el.is("input, textarea, select") ? $el.val() : $el.text()) || "";
    if (String(current).trim() === target) {
      return false;
    }
    if ($el.is("input, textarea")) {
      $el.val(target);
    } else {
      $el.html(jalaliEscapeDisplay(target));
    }
    return true;
  }

  /** Main form (non-grid) Date/Datetime — input and read-only display areas. */
  function applyJalaliControlDisplay(control) {
    if (!control || control.grid || control.grid_row) {
      return;
    }
    if (!shouldUseJalaliCalendar()) {
      return;
    }
    const ft = control.df?.fieldtype;
    if (ft !== "Date" && ft !== "Datetime") {
      return;
    }
    const raw = getControlModelValue(control);
    if (raw == null || raw === "") {
      return;
    }
    const display = modelValueToDisplayInput(raw, ft === "Datetime");
    if (!display) {
      return;
    }

    const updatedTargets = [];

    if (control.$input?.length) {
      setControlInputDisplayOnly(control, display);
      updatedTargets.push("$input");
    }

    if (control.$wrapper?.length) {
      control.$wrapper.find(".control-value").each(function () {
        if (setJalaliOnDisplayElement($(this), display)) {
          updatedTargets.push(".control-value");
        }
      });
      control.$wrapper.find(".like-disabled-input").each(function () {
        if (setJalaliOnDisplayElement($(this), display)) {
          updatedTargets.push(".like-disabled-input");
        }
      });
    }

    if (control.disp_area) {
      if (setJalaliOnDisplayElement($(control.disp_area), display)) {
        updatedTargets.push("disp_area");
      }
    }

    if (control.value_area) {
      const $va = $(control.value_area);
      if (setJalaliOnDisplayElement($va, display)) {
        updatedTargets.push("value_area");
      }
    }

    if (control.jalaliDatepicker?.updateDisplay) {
      control.jalaliDatepicker.updateDisplay();
    }

    jalaliMainDisplayLog({
      fieldname: control.df.fieldname,
      fieldtype: ft,
      raw_model_value: raw,
      converted_jalali_display: display,
      updated_targets: updatedTargets,
    });
  }

  function refreshMainFormJalaliFields(frm) {
    if (!frm || !shouldUseJalaliCalendar()) {
      return;
    }
    Object.values(frm.fields_dict || {}).forEach((field) => {
      if (!field || field.grid) {
        return;
      }
      if (field.df?.fieldtype !== "Date" && field.df?.fieldtype !== "Datetime") {
        return;
      }
      if (field.$input?.length) {
        destroyAirDatepickerForInput(field.$input);
      }
      if (
        !field.jalaliDatepicker &&
        typeof field.replaceWithJalaliDatepicker === "function" &&
        field.can_write?.()
      ) {
        field.setupInputWithoutAirDatepicker?.();
        field.replaceWithJalaliDatepicker();
      }
      applyJalaliControlDisplay(field);
    });
  }

  function scheduleMainFormJalaliDisplayPasses(frm) {
    if (!frm) {
      return;
    }
    const run = () => refreshMainFormJalaliFields(frm);
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(run);
    }
    setTimeout(run, 0);
    setTimeout(run, 100);
    setTimeout(run, 300);
  }

  let jalaliPickerPopupStylesInjected = false;

  function injectJalaliPickerPopupStyles() {
    if (jalaliPickerPopupStylesInjected || document.getElementById("jalali-datepicker-popup-styles")) {
      jalaliPickerPopupStylesInjected = true;
      return;
    }
    const style = document.createElement("style");
    style.id = "jalali-datepicker-popup-styles";
    style.textContent = `
      .jalali-datepicker-popup {
        z-index: 10050 !important;
        position: fixed !important;
      }
    `;
    document.head.appendChild(style);
    jalaliPickerPopupStylesInjected = true;
  }

  function isInputInGrid($input) {
    if (!$input || !$input.length) {
      return false;
    }
    return (
      $input.closest(
        ".form-grid, .form-in-grid, .grid-row, .grid-form-row, .editable-row, .data-row"
      ).length > 0
    );
  }

  function isCalendarTraceEnabled() {
    try {
      return localStorage.getItem("persian_calendar_trace") === "1";
    } catch (e) {
      return false;
    }
  }

  function pcTrace(fn, detail) {
    if (!isCalendarTraceEnabled()) {
      return;
    }
    console.warn("[persian_calendar trace]", fn, detail);
  }

  let pcSyncCallCount = 0;
  let pcSyncResetScheduled = false;

  /**
   * Synchronous loop circuit-breaker. Counts wrapped-method entries within a single
   * macrotask. If a runaway synchronous loop blows the budget, records the offending
   * site + stack to window.__pcLoopBreak and throws to unwind the recursion (so the
   * page recovers instead of hard-freezing). The counter resets on the next macrotask.
   */
  function pcLoopGuard(name, detail) {
    pcSyncCallCount += 1;
    if (!pcSyncResetScheduled) {
      pcSyncResetScheduled = true;
      setTimeout(() => {
        pcSyncCallCount = 0;
        pcSyncResetScheduled = false;
      }, 0);
    }
    if (pcSyncCallCount > 3000) {
      const err = new Error(
        "persian_calendar sync loop budget exceeded at " + name
      );
      try {
        const win = typeof window !== "undefined" ? window : null;
        if (win && !win.__pcLoopBreak) {
          win.__pcLoopBreak = {
            name,
            detail: detail || null,
            stack: err.stack,
            count: pcSyncCallCount,
          };
        }
        console.error("[persian_calendar loop_break]", name, detail, err.stack);
      } catch (e) {
        /* ignore */
      }
      throw err;
    }
  }

  function isLoopTraceEnabled() {
    try {
      return (
        typeof localStorage !== "undefined" &&
        localStorage.getItem("persian_calendar_loop_trace") === "1"
      );
    } catch (e) {
      return false;
    }
  }

  /**
   * Lightweight loop tracer. When `persian_calendar_loop_trace=1` in localStorage,
   * counts hits per (fn,fieldname) per second. If >50 in one window, dumps stack
   * and resets the counter to prevent console spam.
   */
  function pcLoopTrace(fn, detail) {
    if (!isLoopTraceEnabled()) {
      return;
    }
    const win = typeof window !== "undefined" ? window : null;
    if (!win) {
      return;
    }
    win.__pcLoopTrace = win.__pcLoopTrace || {};
    const key = String(fn) + "|" + ((detail && detail.field) || "?");
    const now = Date.now();
    const entry = win.__pcLoopTrace[key] || { start: now, count: 0, warned: false };
    if (now - entry.start > 1000) {
      entry.start = now;
      entry.count = 0;
      entry.warned = false;
    }
    entry.count += 1;
    win.__pcLoopTrace[key] = entry;
    if (entry.count > 50 && !entry.warned) {
      entry.warned = true;
      try {
        console.warn(
          "[persian_calendar loop_trace] potential loop",
          fn,
          detail,
          "count=" + entry.count + "/s"
        );
        console.trace("[persian_calendar loop_trace] stack");
      } catch (e) {
        /* ignore */
      }
    }
  }

  function incCallCount(name) {
    try {
      const win = typeof window !== "undefined" ? window : null;
      if (!win) return;
      win.__persianCalendarCallCounts = win.__persianCalendarCallCounts || {};
      win.__persianCalendarCallCounts[name] =
        (win.__persianCalendarCallCounts[name] || 0) + 1;
    } catch (e) {
      /* ignore */
    }
  }

  function destroyJalaliDatepickerOnInput($input) {
    if (!$input || !$input.length) {
      return;
    }
    const win = typeof window !== "undefined" ? window : null;
    if (win) {
      win.__persianCalendarDestroyLog = win.__persianCalendarDestroyLog || [];
      win.__persianCalendarDestroyLog.push({
        t: Date.now(),
        field: $input.attr("data-fieldname"),
        value: $input.val(),
      });
    }
    const inst = $input.data("jalaliDatepickerInstance");
    if (inst && typeof inst.destroy === "function") {
      pcTrace("destroyJalaliDatepickerOnInput", {
        value: $input.val(),
        field: $input.attr("data-fieldname"),
      });
      inst.destroy();
    }
    $input.removeData("jalaliDatepickerInstance");
    $input.removeData("hasJalaliDatepicker");
    $input.removeAttr("data-has-jalali-datepicker");
    $input.removeData("jalali-model-value");
    $input.siblings(".jalali-datepicker").remove();
    const ns = $input.data("jalaliInputEventNs");
    if (ns) {
      $input.off(ns);
      $input.removeData("jalaliInputEventNs");
    }
  }

  function stripAllJalaliPickersInForm(frm) {
    const $wrapper = getFormWrapper(frm);
    if (!$wrapper.length) {
      return;
    }
    $wrapper
      .find(
        'input[data-has-jalali-datepicker="true"], input[data-jalali-model-value]'
      )
      .each(function () {
        destroyJalaliDatepickerOnInput($(this));
      });
    $(".jalali-datepicker").remove();
  }

  function coerceGregorianDisplayToISODateTime(displayValue) {
    if (displayValue == null || displayValue === "") {
      return null;
    }
    const s = String(displayValue).trim();
    if (!s) return null;
    // Already ISO-ish
    if (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}/.test(s)) {
      return s.length === 16 ? `${s}:00` : s;
    }
    // Use Frappe's parser (respects sys_defaults date_format / time_format)
    try {
      if (typeof frappe !== "undefined" && frappe.datetime?.user_to_str) {
        const out = frappe.datetime.user_to_str(s);
        if (out && /^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}/.test(out)) {
          return out.length === 16 ? `${out}:00` : out;
        }
      }
    } catch (e) {
      /* ignore */
    }
    const U = getDateUtils();
    if (U?.coerceToGregorianDateTime) {
      const coerced = U.coerceToGregorianDateTime(s);
      if (coerced && /^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}/.test(coerced)) {
        return coerced.length === 16 ? `${coerced}:00` : coerced;
      }
    }
    // Fallback for DD-MM-YYYY HH:mm:ss specifically
    const m = /^(\d{2})-(\d{2})-(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?$/.exec(s);
    if (m) {
      const dd = m[1], mm = m[2], yyyy = m[3];
      const hh = String(m[4]).padStart(2, "0");
      const mi = m[5];
      const ss = String(m[6] || "00").padStart(2, "0");
      return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`;
    }
    return null;
  }

  function findGridRowForInput($input) {
    if (!$input?.length || !cur_frm) {
      return null;
    }
    for (const f of Object.values(cur_frm.fields_dict || {})) {
      if (!f?.grid?.grid_rows) {
        continue;
      }
      for (const r of f.grid.grid_rows) {
        if (gridRowContainsInput(r, $input)) {
          return r;
        }
      }
    }
    return null;
  }

  /** Gregorian grid/main datetime: model ISO is source of truth before Frappe picker opens. */
  function syncGregorianDateControlInputFromModel($input, opts = {}) {
    if (!$input?.length || shouldUseJalaliCalendar()) {
      return;
    }
    const $fc = $input.closest(".frappe-control");
    const fieldtype = $fc.attr("data-fieldtype");
    const fieldname = $fc.attr("data-fieldname");
    if (!fieldname || (fieldtype !== "Datetime" && fieldtype !== "Date")) {
      return;
    }
    let modelVal = null;
    const grid_row = opts.grid_row || findGridRowForInput($input);
    if (grid_row?.doc && grid_row.doc[fieldname] != null && grid_row.doc[fieldname] !== "") {
      coerceGridRowDatetimeField(grid_row, fieldname, fieldtype);
      modelVal = grid_row.doc[fieldname];
    } else if (cur_frm?.doc && cur_frm.doc[fieldname] != null && cur_frm.doc[fieldname] !== "") {
      modelVal = cur_frm.doc[fieldname];
    } else {
      const stored = $input.data("jalali-model-value");
      if (stored) {
        modelVal = stored;
      }
    }
    if (!modelVal) {
      return;
    }
    const onlyDate = fieldtype === "Date";
    let formatted = "";
    try {
      formatted = frappe.datetime.str_to_user(modelVal, false, onlyDate);
    } catch (e) {
      return;
    }
    if (!formatted || /Invalid\s*date/i.test(formatted)) {
      pcTrace("syncGregorianDateControlInputFromModel skipped bad format", {
        fieldname,
        modelVal,
        formatted,
        ...opts,
      });
      return;
    }
    const visible = String($input.val() || "").trim();
    if (visible !== formatted) {
      pcTrace("syncGregorianDateControlInputFromModel", {
        fieldname,
        from: visible,
        to: formatted,
        modelVal,
        ...opts,
      });
      $input.val(formatted);
    }
  }

  function normalizeGregorianDatetimeInput($input, opts = {}) {
    if (!$input?.length) return;
    syncGregorianDateControlInputFromModel($input, opts);
    const raw = String($input.val() || "").trim();
    if (!raw) return;
    // Input already in user/system display form — do not overwrite with ISO (breaks Frappe picker).
    if (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}/.test(raw)) {
      try {
        const userFmt = frappe.datetime.str_to_user(raw, false);
        if (userFmt && !/Invalid\s*date/i.test(userFmt) && userFmt !== raw) {
          pcTrace("normalizeGregorianDatetimeInput iso->user", {
            from: raw,
            to: userFmt,
            ...opts,
          });
          $input.val(userFmt);
        }
      } catch (e) {
        /* ignore */
      }
      return;
    }
    const iso = coerceGregorianDisplayToISODateTime(raw);
    if (!iso || iso === raw) return;
    let userDisplay = iso;
    try {
      userDisplay = frappe.datetime.str_to_user(iso, false);
    } catch (e) {
      /* ignore */
    }
    if (userDisplay && !/Invalid\s*date/i.test(userDisplay)) {
      pcTrace("normalizeGregorianDatetimeInput stale->user", {
        from: raw,
        to: userDisplay,
        iso,
        ...opts,
      });
      $input.val(userDisplay);
    }
  }

  function normalizeGregorianDatetimeInputsInForm(frm) {
    const $wrapper = getFormWrapper(frm);
    if (!$wrapper.length) {
      return;
    }
    $wrapper
      .find('.frappe-control[data-fieldtype="Datetime"] input')
      .each(function () {
        normalizeGregorianDatetimeInput($(this), { scope: "form-pass" });
      });
  }

  function getInputFieldtype($input) {
    if (!$input?.length) {
      return null;
    }
    return (
      $input.attr("data-fieldtype") ||
      $input.closest(".frappe-control").attr("data-fieldtype") ||
      null
    );
  }

  /** Persian Calendar must never attach to or tear down Frappe Time controls. */
  function isTimeFieldInput($input) {
    return getInputFieldtype($input) === "Time";
  }

  function destroyAirDatepickerForInput($input) {
    if (!$input || !$input.length) {
      return;
    }
    if (isTimeFieldInput($input)) {
      return;
    }
    const el = $input[0];
    try {
      const inst = $input.data("datepicker");
      if (inst && typeof inst.destroy === "function") {
        inst.destroy();
      }
    } catch (e) {
      /* ignore */
    }
    if (el && el._datepicker && typeof el._datepicker.destroy === "function") {
      try {
        el._datepicker.destroy();
      } catch (e2) {
        /* ignore */
      }
      el._datepicker = null;
    }
    $input.removeData("datepicker");
    $input.removeClass("datepicker-input hasDatepicker");
    $input.removeAttr("data-date-format data-alt-input data-alt-format");
    $input.off(".datepicker");
    $input.siblings(".air-datepicker, .datepicker--pointer").remove();
  }

  /** Position popup relative to viewport (for grid / overflow containers). */
  function positionPicker(input, $pickerEl) {
    if (!input || !$pickerEl || !$pickerEl.length) {
      return;
    }
    const rect = input.getBoundingClientRect();
    const margin = 6;
    const gap = 2;
    const wasVisible = $pickerEl.is(":visible");
    if (!wasVisible) {
      $pickerEl.css({ display: "block", visibility: "hidden" });
    }
    const pw = $pickerEl.outerWidth() || 260;
    const ph = $pickerEl.outerHeight() || 320;
    let top = rect.bottom + gap;
    let left = rect.left;
    if (top + ph > window.innerHeight - margin) {
      top = rect.top - ph - gap;
    }
    if (top < margin) {
      top = margin;
    }
    if (left + pw > window.innerWidth - margin) {
      left = window.innerWidth - pw - margin;
    }
    if (left < margin) {
      left = margin;
    }
    $pickerEl.css({
      position: "fixed",
      top: top + "px",
      left: left + "px",
      zIndex: 10050,
    });
    if (!wasVisible) {
      $pickerEl.css({ visibility: "" });
    }
    jalaliGridPositionLog("positionPicker", {
      inputRect: { top: rect.top, left: rect.left, bottom: rect.bottom, right: rect.right },
      popup: { w: pw, h: ph, top, left },
    });
  }
  function jalaliDateLog(...args) {
    if (JALALI_DATE_DEBUG) {
      console.log("[jalali_date]", ...args);
    }
  }
  function jalaliDatetimeLog(...args) {
    if (JALALI_DATETIME_DEBUG) {
      console.log("[jalali_datetime]", ...args);
    }
  }

  function getDateUtils() {
    return window.jalaliDateUtils;
  }

  function isGregorianWithinConstraints(control, gy, gm, gd) {
    if (!control) return true;
    const d = new Date(gy, gm - 1, gd);
    if (control._jalaliMaxDate && d > control._jalaliMaxDate) return false;
    if (control._jalaliMinDate && d < control._jalaliMinDate) return false;
    return true;
  }

  /** Air-datepicker compatibility for ERPNext scripts (e.g. Employee date_of_birth maxDate). */
  function installJalaliDatepickerShim(control) {
    if (!control || !control.jalaliDatepicker) return;
    const jalaliInstance = control.jalaliDatepicker;
    control.datepicker = {
      _pcJalaliShim: true,
      opts: {},
      update(keyOrOpts, val) {
        if (typeof keyOrOpts === "object" && keyOrOpts !== null) {
          if (keyOrOpts.maxDate !== undefined) {
            control._jalaliMaxDate =
              keyOrOpts.maxDate instanceof Date ? keyOrOpts.maxDate : new Date(keyOrOpts.maxDate);
          }
          if (keyOrOpts.minDate !== undefined) {
            control._jalaliMinDate =
              keyOrOpts.minDate instanceof Date ? keyOrOpts.minDate : new Date(keyOrOpts.minDate);
          }
          Object.assign(this.opts, keyOrOpts);
        } else if (typeof keyOrOpts === "string") {
          this.opts[keyOrOpts] = val;
        }
      },
      clear() {
        if (control.$input) control.$input.val("");
        jalaliInstance.selectedDate = null;
      },
      hide() {
        if (jalaliInstance.isOpen) jalaliInstance.close();
      },
      selectDate() {
        /* no-op: Jalali picker sets values via applySelectedValue */
      },
    };
  }

  // Helper functions — use window.toJalali / window.toGregorian from jalaali.js; Intl fallback for display if missing.
  function gToJ(gDate) {
    if (!gDate || isNaN(gDate.getTime())) {
      return { jy: 1400, jm: 1, jd: 1 };
    }
    const toJ = typeof window !== "undefined" && window.toJalali;
    if (toJ) {
      return toJ(gDate.getFullYear(), gDate.getMonth() + 1, gDate.getDate());
    }
    try {
      const fmt = new Intl.DateTimeFormat("en-u-ca-persian", { year: "numeric", month: "2-digit", day: "2-digit" });
      const parts = fmt.formatToParts(gDate);
      const map = Object.fromEntries(parts.map((p) => [p.type, p.value]));
      return {
        jy: parseInt(map.year, 10),
        jm: parseInt(map.month, 10),
        jd: parseInt(map.day, 10),
      };
    } catch (e) {
      return { jy: gDate.getFullYear(), jm: gDate.getMonth() + 1, jd: gDate.getDate() };
    }
  }

  function jToG(jy, jm, jd) {
    const toG = typeof window !== "undefined" && window.toGregorian;
    if (toG) {
      return toG(jy, jm, jd);
    }
    return null;
  }

  function formatJalaliDate(jy, jm, jd) {
    const y = parseInt(jy, 10);
    const m = parseInt(jm, 10);
    const d = parseInt(jd, 10);
    if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(d)) {
      return "";
    }
    return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  }

  function formatJalaliDateTime(jy, jm, jd, hour, minute, second) {
    const dateStr = formatJalaliDate(jy, jm, jd);
    if (!dateStr) {
      return "";
    }
    const h = parseInt(hour, 10);
    const mi = parseInt(minute, 10);
    const s = parseInt(second, 10);
    const timeStr = `${String(Number.isFinite(h) ? h : 0).padStart(2, "0")}:${String(Number.isFinite(mi) ? mi : 0).padStart(2, "0")}:${String(Number.isFinite(s) ? s : 0).padStart(2, "0")}`;
    return `${dateStr} ${timeStr}`;
  }

  function parseJalaliDate(dateStr) {
    if (!shouldUseJalaliCalendar()) {
      pcTrace("parseJalaliDate skipped (Gregorian mode)", { dateStr });
      return null;
    }
    const U = getDateUtils();
    if (!dateStr || !U) {
      return null;
    }
    const str = String(dateStr).trim();
    const datePart = str.indexOf(" ") === -1 ? str : str.slice(0, str.indexOf(" "));

    if (U.isLikelyJalaliISO(datePart)) {
      const p = U.parseYMD(datePart);
      return p ? { jy: p.y, jm: p.m, jd: p.d } : null;
    }
    if (U.isLikelyGregorianISO(datePart)) {
      const jalali = U.gregorianToJalaliISO(datePart);
      if (!jalali) {
        return null;
      }
      const p = U.parseYMD(jalali);
      return p ? { jy: p.y, jm: p.m, jd: p.d } : null;
    }

    const coerced = U.coerceToGregorianDateTime
      ? U.coerceToGregorianDateTime(str) || U.coerceToGregorianDateTime(datePart)
      : null;
    if (coerced) {
      const jalali = U.gregorianToJalaliISO(coerced.slice(0, 10));
      if (!jalali) {
        return null;
      }
      const p = U.parseYMD(jalali);
      return p ? { jy: p.y, jm: p.m, jd: p.d } : null;
    }

    const parts = datePart.split("-").map((x) => parseInt(x, 10));
    if (
      parts.length === 3 &&
      parts.every((n) => Number.isFinite(n)) &&
      parts[0] >= 1200 &&
      parts[0] <= 1600
    ) {
      return { jy: parts[0], jm: parts[1], jd: parts[2] };
    }
    return null;
  }

  function parseJalaliDateTime(dateTimeStr) {
    incCallCount("parseJalaliDateTime");
    if (!shouldUseJalaliCalendar()) {
      pcTrace("parseJalaliDateTime skipped (Gregorian mode)", { dateTimeStr });
      return null;
    }
    const U = getDateUtils();
    if (!dateTimeStr || !U) {
      return null;
    }
    pcTrace("parseJalaliDateTime", { in: dateTimeStr });

    const str = U.stripMicroseconds(String(dateTimeStr).trim());
    if (!str) {
      return null;
    }

    function partsFromJalaliDisplay(jalaliStr) {
      const p = U.parseDateTimeParts(jalaliStr);
      if (!p || !U.isLikelyJalaliDateTime(jalaliStr)) {
        return null;
      }
      return {
        jy: p.y,
        jm: p.m,
        jd: p.d,
        hour: p.h,
        minute: p.i,
        second: p.s,
      };
    }

    if (U.isLikelyGregorianDateTime(str)) {
      return partsFromJalaliDisplay(U.gregorianDateTimeToJalali(str));
    }
    if (U.isLikelyJalaliDateTime(str)) {
      const p = U.parseDateTimeParts(str);
      if (!p) {
        return null;
      }
      return {
        jy: p.y,
        jm: p.m,
        jd: p.d,
        hour: p.h,
        minute: p.i,
        second: p.s,
      };
    }

    const coerced = U.coerceToGregorianDateTime(str);
    if (coerced) {
      return partsFromJalaliDisplay(U.gregorianDateTimeToJalali(coerced));
    }
    return null;
  }

  /** True when two model values are the same calendar instant (avoids dirty on date vs datetime string). */
  function modelValuesEqualForField(valueA, valueB, fieldtype) {
    const U = getDateUtils();
    if (!U) {
      return String(valueA ?? "") === String(valueB ?? "");
    }
    if (valueA == null && valueB == null) {
      return true;
    }
    if (fieldtype === "Datetime") {
      const a = U.normalizeModelDateTime(valueA);
      const b = U.normalizeModelDateTime(valueB);
      return !!a && a === b;
    }
    if (fieldtype === "Date") {
      const a =
        (U.coerceToGregorianDateTime(valueA) || U.normalizeModelDate(valueA) || "")
          .toString()
          .slice(0, 10) || "";
      const b =
        (U.coerceToGregorianDateTime(valueB) || U.normalizeModelDate(valueB) || "")
          .toString()
          .slice(0, 10) || "";
      return a === b && a !== "";
    }
    return String(valueA ?? "") === String(valueB ?? "");
  }

  /** Update visible input only; never touch frm.doc / model. */
  function setControlInputDisplayOnly(control, display) {
    if (!control?.$input?.length || display == null) {
      return;
    }
    const target = String(display);
    const current = String(control.$input.val() || "").trim();
    if (current === target) {
      return;
    }
    control.$input.val(target);
  }

  /** Display string for input from model value (Gregorian → Jalali; Jalali model value shown as-is). */
  function modelValueToDisplayInput(value, isDateTime) {
    if (!shouldUseJalaliCalendar()) {
      pcTrace("modelValueToDisplayInput passthrough (Gregorian)", { value, isDateTime });
      return value == null ? "" : String(value);
    }
    const U = getDateUtils();
    if (!value || !U) return value == null ? "" : String(value);
    const fieldtype = isDateTime ? "Datetime" : "Date";
    if (U.valueToJalaliDisplay) {
      return U.valueToJalaliDisplay(value, fieldtype) || "";
    }
    const str = U.stripMicroseconds(String(value).trim());
    if (!str) return "";
    if (isDateTime) {
      if (U.isLikelyJalaliDateTime(str)) {
        const p = U.parseDateTimeParts(str);
        return p
          ? `${U.formatJalaliParts(p.y, p.m, p.d)} ${U.formatTimeHMS(p.h, p.i, p.s)}`
          : str;
      }
      if (U.isLikelyGregorianDateTime(str)) {
        return U.gregorianDateTimeToJalali(str) || str;
      }
      return str;
    }
    const datePart = str.indexOf(" ") === -1 ? str : str.slice(0, str.indexOf(" "));
    if (U.isLikelyJalaliISO(datePart)) {
      return datePart;
    }
    if (U.isLikelyGregorianISO(datePart)) {
      return U.gregorianToJalaliISO(datePart) || str;
    }
    return str;
  }

// Global function to close all Jalali datepickers
function closeAllJalaliDatepickers() {
  $('.jalali-datepicker').each(function() {
    const $calendar = $(this);
    const instance = $calendar.data('jalaliDatepickerInstance');
    if (instance && instance.isOpen) {
      instance.close(); // Call the instance's close method to clean up its listeners
    } else {
      $calendar.hide(); // Fallback if instance not found or not open
    }
  });
  
  // No need to remove global handlers here if each instance manages its own
  // The keydown handler is now instance-specific, so no global off needed here.
  
}

// Enhanced Jalali Datepicker Class
class JalaliDatepicker {
    constructor(input, controlDate = null, isDateTime = false) {
      this.input = input;
      this.$input = $(input);
      this.controlDate = controlDate;
      this.isDateTime = isDateTime;
      this.isOpen = false;
      this._isDraggingSlider = false; // Track if user is dragging a slider
      this._isApplyingValue = false; // Track if we're applying a value (prevent closing during updates)
      this._suppressOpenUntil = 0;
      this._pickerUid =
        "jdp-" + (input.id || input.name || "inp") + "-" + String(Math.random()).slice(2, 9);
      this._inputEventNs = ".jalali-dp-" + this._pickerUid;
      this._useBodyPopup = isInputInGrid(this.$input);
      this._calendarOnBody = false;
      this._positionListenersBound = false;
      this.currentDate = gToJ(new Date());
      this.selectedDate = null;
      this.selectedTime = { hour: new Date().getHours(), minute: new Date().getMinutes(), second: new Date().getSeconds() };
      this.view = 'days'; // 'days', 'months', 'years'
      this.yearRange = { start: 1400, end: 1410 };
      injectJalaliPickerPopupStyles();
      destroyAirDatepickerForInput(this.$input);
      this.init();
    }

    init() {
      this.createCalendar();
      this.bindEvents();
      this.updateDisplay();
      this.fixAlignment();
      this.$calendar.data('jalaliDatepickerInstance', this); // Store instance
    }
    
    fixAlignment() {
      if (this._useBodyPopup && this.$calendar && this.$calendar.length) {
        this.$calendar.addClass("jalali-datepicker-popup");
        return;
      }
      if (this.$calendar && this.$calendar.length) {
        this.$calendar.css({
          position: "absolute",
          "z-index": 9999,
        });
      }
    }

    createCalendar() {
      // Remove existing calendar
      this.$input.siblings('.jalali-datepicker').remove();
      
      // Create calendar HTML with exact Gregorian styling
      const calendarHTML = `
        <div class="jalali-datepicker ${this.isDateTime ? 'jalali-datetime-picker' : ''}" style="
          position: absolute;
          top: 100%;
          left: 0;
          background: var(--bg-color, #fff);
          border: 1px solid var(--border-color, #d1d8dd);
          border-radius: var(--border-radius-sm, 6px);
          box-shadow: var(--shadow-md, 0 2px 8px rgba(0,0,0,0.15));
          z-index: 1000;
          display: none;
          width: ${this.isDateTime ? '240px' : '210px'};
          padding: 1px;
          font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
          font-size: var(--text-sm, 13px);
          margin-top: 1px;
        ">
          <!-- Header with Navigation -->
          <div class="calendar-header" style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1px;
            padding-bottom: 1px;
            border-bottom: 1px solid var(--border-color, #e5e7eb);
          ">
            <button type="button" class="nav-btn prev-btn" style="
              background: transparent;
              border: none;
              cursor: pointer;
              padding: 1px 3px;
              font-size: 11px;
              color: var(--text-light, #6c7b7f);
              transition: color 0.2s ease;
              border-radius: 4px;
            ">‹</button>
            <button type="button" class="nav-btn prev-decade" style="
              background: transparent;
              border: none;
              cursor: pointer;
              padding: 1px 3px;
              font-size: 11px;
              color: #6c7b7f;
              transition: color 0.2s ease;
              border-radius: 4px;
            ">‹‹</button>
            <span class="month-year clickable" style="
              font-weight: 500;
              font-size: 12px;
              cursor: pointer;
              padding: 1px 4px;
              color: var(--text-color, #36414c);
              transition: background-color 0.2s ease;
              border-radius: 4px;
            "></span>
            <button type="button" class="nav-btn next-decade" style="
              background: transparent;
              border: none;
              cursor: pointer;
              padding: 1px 3px;
              font-size: 11px;
              color: #6c7b7f;
              transition: color 0.2s ease;
              border-radius: 4px;
            ">››</button>
            <button type="button" class="nav-btn next-btn" style="
              background: transparent;
              border: none;
              cursor: pointer;
              padding: 1px 3px;
              font-size: 11px;
              color: #6c7b7f;
              transition: color 0.2s ease;
              border-radius: 4px;
            ">›</button>
          </div>
          
          <!-- Content Area -->
          <div class="calendar-content">
            <!-- Days View -->
            <div class="days-view">
              <div class="weekdays" style="
                display: grid;
                grid-template-columns: repeat(7, 30px);
                gap: 0px;
                margin-bottom: 0px;
              "></div>
              <div class="days-grid" style="
                display: grid;
                grid-template-columns: repeat(7, 30px);
                gap: 0px;
              "></div>
            </div>
            
            <!-- Months View -->
            <div class="months-view" style="display: none;">
              <div class="months-grid" style="
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 1px;
                padding: 1px 0;
              "></div>
            </div>
            
            <!-- Years View -->
            <div class="years-view" style="display: none;">
              <div class="years-grid" style="
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 1px;
                padding: 1px 0;
              "></div>
            </div>
          </div>
          
          <!-- Time Picker (for datetime) -->
          ${this.isDateTime ? `
          <div class="time-picker" style="
            margin-top: 0;
            padding: 8px;
            border-top: 1px solid var(--border-color, #e5e7eb);
            background: var(--bg-color, #fafafa);
          ">
            <div style="display: flex; flex-direction: column; gap: 8px;">
              <!-- Hour -->
              <div style="display: flex; align-items: center; gap: 8px;">
                <label style="font-size: 11px; color: var(--text-color, #36414c); min-width: 30px;">ساعت:</label>
                <input type="range" class="time-hour" min="0" max="23" value="0" style="
                  flex: 1;
                  height: 4px;
                  background: var(--border-color, #d1d8dd);
                  border-radius: 2px;
                  outline: none;
                  -webkit-appearance: none;
                ">
                <span class="time-hour-value" style="font-size: 11px; color: var(--text-color, #36414c); min-width: 25px; text-align: center; font-weight: 500;">0</span>
              </div>
              <!-- Minute -->
              <div style="display: flex; align-items: center; gap: 8px;">
                <label style="font-size: 11px; color: var(--text-color, #36414c); min-width: 30px;">دقیقه:</label>
                <input type="range" class="time-minute" min="0" max="59" value="0" style="
                  flex: 1;
                  height: 4px;
                  background: var(--border-color, #d1d8dd);
                  border-radius: 2px;
                  outline: none;
                  -webkit-appearance: none;
                ">
                <span class="time-minute-value" style="font-size: 11px; color: var(--text-color, #36414c); min-width: 25px; text-align: center; font-weight: 500;">0</span>
              </div>
              <!-- Second -->
              <div style="display: flex; align-items: center; gap: 8px;">
                <label style="font-size: 11px; color: var(--text-color, #36414c); min-width: 30px;">ثانیه:</label>
                <input type="range" class="time-second" min="0" max="59" value="0" style="
                  flex: 1;
                  height: 4px;
                  background: var(--border-color, #d1d8dd);
                  border-radius: 2px;
                  outline: none;
                  -webkit-appearance: none;
                ">
                <span class="time-second-value" style="font-size: 11px; color: var(--text-color, #36414c); min-width: 25px; text-align: center; font-weight: 500;">0</span>
              </div>
            </div>
            <style>
              .jalali-datepicker .time-picker input[type="range"]::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 14px;
                height: 14px;
                background: var(--primary, #171717);
                border-radius: 50%;
                cursor: pointer;
              }
              .jalali-datepicker .time-picker input[type="range"]::-moz-range-thumb {
                width: 14px;
                height: 14px;
                background: var(--primary, #171717);
                border-radius: 50%;
                cursor: pointer;
                border: none;
              }
              .jalali-datepicker .time-picker input[type="range"]:hover::-webkit-slider-thumb {
                background: var(--primary, #000);
              }
              .jalali-datepicker .time-picker input[type="range"]:hover::-moz-range-thumb {
                background: var(--primary, #000);
              }
            </style>
          </div>
          ` : ''}
          
          <!-- Footer -->
          <div class="calendar-footer" style="
            margin-top: 1px;
            padding-top: 1px;
            border-top: 1px solid var(--border-color, #eee);
            text-align: center;
          ">
            <button type="button" class="${this.isDateTime ? 'now-btn' : 'today-btn'}" style="
              background: transparent;
              color: var(--text-color, #36414c);
              border: 1px solid var(--border-color, #d1d8dd);
              padding: 2px 8px;
              border-radius: 3px;
              cursor: pointer;
              font-size: 12px;
              font-weight: normal;
              transition: all 0.2s ease;
              font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
              width: 100%;
            ">${this.isDateTime ? 'اکنون' : 'امروز'}</button>
          </div>
        </div>
      `;
      
      this.$calendar = $(calendarHTML);
      if (this._useBodyPopup) {
        this.$calendar.addClass("jalali-datepicker-popup");
        $(document.body).append(this.$calendar);
        this._calendarOnBody = true;
      } else {
        this.$input.after(this.$calendar);
      }
    }

    _ensureCalendarOnBody() {
      if (!this._useBodyPopup || !this.$calendar || !this.$calendar.length) {
        return;
      }
      if (!this._calendarOnBody || !this.$calendar.parent().is("body")) {
        $(document.body).append(this.$calendar);
        this._calendarOnBody = true;
      }
      this.$calendar.addClass("jalali-datepicker-popup");
    }

    _setupPositionListeners() {
      if (this._positionListenersBound || !this._useBodyPopup) {
        return;
      }
      const self = this;
      const ns = ".jalaliDatepicker-" + this._pickerUid;
      this._positionEventNs = ns;
      if (!this._positionScrollHandler) {
        this._positionScrollHandler = function () {
          if (self.isOpen) {
            self.repositionPicker();
          }
        };
      }
      if (!this._positionResizeHandler) {
        this._positionResizeHandler = function () {
          if (self.isOpen) {
            self.repositionPicker();
          }
        };
      }
      $(window).on("resize" + ns, this._positionResizeHandler);
      document.addEventListener("scroll", this._positionScrollHandler, true);
      this._positionListenersBound = true;
    }

    _teardownPositionListeners() {
      if (!this._positionListenersBound) {
        return;
      }
      const ns = this._positionEventNs || ".jalaliDatepicker-" + this._pickerUid;
      $(window).off("resize" + ns, this._positionResizeHandler);
      if (this._positionScrollHandler) {
        document.removeEventListener("scroll", this._positionScrollHandler, true);
      }
      this._positionListenersBound = false;
    }

    _scheduleGridDisplayRefresh() {
      const grid_row = this.controlDate?.grid_row;
      const fieldname = this.controlDate?.df?.fieldname;
      if (!grid_row || !fieldname) {
        return;
      }
      const run = () => applyJalaliGridCellDisplay(grid_row, fieldname);
      setTimeout(run, 0);
      setTimeout(run, 100);
    }

    repositionPicker() {
      this._ensureCalendarOnBody();
      positionPicker(this.input, this.$calendar);
    }

    bindEvents() {
      const self = this;
      const ns = this._inputEventNs;
      this.$input.data("jalaliInputEventNs", ns);

      // Input click - toggle calendar (open if closed, close if open)
      // Use mousedown instead of click to prevent _globalClickListener from closing it immediately
      this.$input.on("mousedown" + ns, function(e) {
        e.stopPropagation();
        // Use setTimeout to ensure this runs before _globalClickListener
        setTimeout(function() {
          if (!shouldUseJalaliCalendar()) {
            return;
          }
          if (Date.now() < self._suppressOpenUntil) {
            return;
          }
          if (self.isOpen) {
            // If already open, close it
            self.close();
          } else {
            // If closed, open it
            self.open();
          }
        }, 0);
      });
      
      // Also handle focus for better compatibility
      this.$input.on("focus" + ns, function(e) {
        e.stopPropagation();
        // Use setTimeout to ensure this runs before _globalClickListener
        setTimeout(function() {
          if (!shouldUseJalaliCalendar()) {
            pcTrace("JalaliDatepicker focus ignored (Gregorian)", {
              value: self.$input?.val(),
            });
            return;
          }
          if (Date.now() < self._suppressOpenUntil) {
            return;
          }
          if (!self.isOpen) {
            // Only open if not already open (don't toggle on focus)
            self.open();
          }
        }, 0);
      });
      
      // Month/Year navigation
      this.$calendar.find('.prev-btn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        self.navigateMonth(-1);
      });
      
      this.$calendar.find('.next-btn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        self.navigateMonth(1);
      });
      
      // Month/Year click to switch views
      this.$calendar.find('.month-year').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        // Switch views based on current view
        if (self.view === 'days') {
          self.showMonthsView();
        } else if (self.view === 'months') {
          self.showYearsView();
        } else if (self.view === 'years') {
          self.showMonthsView();
        }
      });
      
      // Year navigation
      this.$calendar.find('.prev-decade').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        self.navigateYear(-10);
      });
      
      this.$calendar.find('.next-decade').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        self.navigateYear(10);
      });
      
      // Today/Now button
      this.$calendar.find('.today-btn, .now-btn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        if (self.isDateTime) {
          self.selectNow();
        } else {
          self.selectToday();
        }
      });
      
      // Time picker sliders (for datetime)
      if (this.isDateTime) {
        const updateTime = function() {
          const hour = parseInt(self.$calendar.find('.time-hour').val()) || 0;
          const minute = parseInt(self.$calendar.find('.time-minute').val()) || 0;
          const second = parseInt(self.$calendar.find('.time-second').val()) || 0;
          
          // Update value labels
          self.$calendar.find('.time-hour-value').text(hour);
          self.$calendar.find('.time-minute-value').text(minute);
          self.$calendar.find('.time-second-value').text(second);
          
          self.selectedTime = {
            hour: hour,
            minute: minute,
            second: second
          };
          // Apply the updated time if date is already selected
          // Use flag to prevent calendar from closing during update
          if (self.selectedDate) {
            self._isApplyingValue = true;
            const jalaliStr = formatJalaliDateTime(
              self.selectedDate.jy,
              self.selectedDate.jm,
              self.selectedDate.jd,
              hour,
              minute,
              second
            );
            self.$input.val(jalaliStr);
            setTimeout(function () {
              self._isApplyingValue = false;
            }, 150);
          }
        };
        
        // Update on input (while dragging) and change (on release)
        // Track if user is dragging to prevent calendar from closing
        const timePickerSliders = this.$calendar.find('.time-hour, .time-minute, .time-second');
        
        // Mark dragging when user starts dragging (use instance variable)
        timePickerSliders.on('mousedown', function(e) {
          self._isDraggingSlider = true;
          // Don't stop propagation - needed for slider to work
        });
        
        // Clear dragging flag when mouse is released
        timePickerSliders.on('mouseup', function(e) {
          // Clear flag after a delay to allow click event to be handled
          setTimeout(function() {
            self._isDraggingSlider = false;
          }, 300);
          // Don't stop propagation
        });
        
        // Stop click events on sliders (but check if dragging first)
        timePickerSliders.on('click', function(e) {
          if (self._isDraggingSlider) {
            // If we were dragging, this click is from the drag, ignore it completely
            e.stopPropagation();
            e.preventDefault();
            self._isDraggingSlider = false;
            return false;
          }
          // Normal click (not from drag), stop propagation
          e.stopPropagation();
        });
        
        // Update time during drag - keep dragging flag true
        timePickerSliders.on('input', function(e) {
          self._isDraggingSlider = true; // Keep flag true during drag
          updateTime();
        });
        
        // Update time after drag ends
        timePickerSliders.on('change', function(e) {
          setTimeout(function() {
            self._isDraggingSlider = false;
          }, 300);
          updateTime();
          if (self.selectedDate) {
            self.applySelectedValue(true);
          }
        });
        
        // Stop click events on time-picker container
        const $timePicker = this.$calendar.find('.time-picker');
        $timePicker.on('click', function(e) {
          e.stopPropagation();
        });
      }
      
      // Simple click outside to close - removed, using _globalClickListener instead
      // This was causing conflicts with slider interactions
      
      // Close when clicking on any date/datetime input field
      $(document).on('click.jalali-datepicker-date-inputs', function(e) {
        if (self.isOpen) {
          const $target = $(e.target);
          // Close if clicking on any date/datetime input field that's not our current input
          if (($target.is('input[data-fieldtype="Date"]') || $target.is('input[data-fieldtype="Datetime"]')) && 
              !$target.is(self.input)) {
            self.close();
          }
        }
      });
      
      // ESC key to close - make it instance specific
      this._keydownHandler = function(e) {
        if (e.keyCode === 27 && self.isOpen) {
          self.close();
          return;
        }
        if (e.keyCode === 13 && self.isOpen && self.selectedDate) {
          e.preventDefault();
          e.stopPropagation();
          self.applySelectedValue(true);
          self.close();
        }
      };
      $(document).on('keydown.jalali-datepicker-' + (this.input.id || 'default'), this._keydownHandler);

      // Flag to prevent closing during value updates
      this._isApplyingValue = false;
      
      // Simple click outside to close
      // Use setTimeout to allow slider drag events to complete first
      this._globalClickListener = function(e) {
        if (!self.isOpen) {
          // Calendar is not open, ignore
          return;
        }
        
        // Check immediately if click is on input (before any other checks)
        const $target = $(e.target);
        const isClickOnOwnInput = $target.is(self.input) || 
                                 $(self.input).find($target).length > 0 ||
                                 $target.closest(self.input).length > 0;
        
        // If clicking on input, don't close (input handler will handle toggle)
        if (isClickOnOwnInput) {
          return;
        }
        
        
        // If currently applying value or dragging slider, don't close
        if (self._isApplyingValue || self._isDraggingSlider) {
          return;
        }
        
        // Check if click is inside calendar
        const isClickInsideDatepicker = self.$calendar && self.$calendar.length > 0 && 
                                       ($target.closest(self.$calendar).length > 0 || 
                                        self.$calendar.find($target).length > 0 ||
                                        $target.closest('.jalali-datepicker').length > 0);
        const isTimePickerElement = $target.closest('.time-picker').length > 0 ||
                                   $target.is('input[type="range"]') ||
                                   $target.closest('input[type="range"]').length > 0 ||
                                   $target.hasClass('time-hour') ||
                                   $target.hasClass('time-minute') ||
                                   $target.hasClass('time-second');
        
        // If clicking inside calendar or on slider, don't close
        if (isClickInsideDatepicker || isTimePickerElement) {
          return;
        }
        
        // Use setTimeout to check after all other handlers have run
        // This allows slider drag events to complete before we check
        setTimeout(function() {
          // Check if calendar is still open (might have been closed by another event)
          if (!self.isOpen) {
            return;
          }
          
          
          // Check again if applying value or dragging (might have started during timeout)
          if (self._isApplyingValue || self._isDraggingSlider) {
            return;
          }
          
          // Re-check if click is inside calendar (in case DOM changed)
          const $targetAgain = $(e.target);
          const isClickInsideDatepickerAgain = self.$calendar && self.$calendar.length > 0 && 
                                               ($targetAgain.closest(self.$calendar).length > 0 || 
                                                self.$calendar.find($targetAgain).length > 0 ||
                                                $targetAgain.closest('.jalali-datepicker').length > 0);
          const isClickOnOwnInputAgain = $targetAgain.is(self.input) || 
                                        $(self.input).find($targetAgain).length > 0 ||
                                        $targetAgain.closest(self.input).length > 0;
          const isTimePickerElementAgain = $targetAgain.closest('.time-picker').length > 0 ||
                                           $targetAgain.is('input[type="range"]') ||
                                           $targetAgain.closest('input[type="range"]').length > 0 ||
                                           $targetAgain.hasClass('time-hour') ||
                                           $targetAgain.hasClass('time-minute') ||
                                           $targetAgain.hasClass('time-second');
          
          // If clicking inside calendar, on input, or on slider, don't close
          if (isClickInsideDatepickerAgain || isClickOnOwnInputAgain || isTimePickerElementAgain) {
            return;
          }
          
          // Click is outside, close the calendar
          self.close();
        }, 100); // Reduced delay for better responsiveness
      };
      
      // Use click event (bubbling phase)
      document.addEventListener('click', this._globalClickListener, false);
      
      // Add hover effects
      this.$calendar.find('.nav-btn').hover(
        function() { $(this).css('background-color', '#f8f9fa'); },
        function() { $(this).css('background-color', 'transparent'); }
      );
      
      this.$calendar.find('.month-year').hover(
        function() { $(this).css('background-color', '#f8f9fa'); },
        function() { $(this).css('background-color', 'transparent'); }
      );
    }

    toggle() {
      if (this.isOpen) {
        this.close();
      } else {
        // Always reset to days view when opening
        this.view = 'days';
        this.open();
      }
    }

    open() {
      if (!shouldUseJalaliCalendar()) {
        pcTrace("JalaliDatepicker.open blocked", {
          value: this.$input?.val(),
          field: this.controlDate?.df?.fieldname,
        });
        return;
      }
      // Don't do anything if already open
      if (this.isOpen) {
        return;
      }
      
      // Close all other Jalali datepickers first (but not this one)
      const self = this;
      $('.jalali-datepicker').each(function() {
        const $calendar = $(this);
        const instance = $calendar.data('jalaliDatepickerInstance');
        if (instance && instance !== self && instance.isOpen) {
          instance.close();
        }
      });
      
      this.isOpen = true;
      this.view = 'days'; // Always reset to days view
      this.syncInputFromModel();
      this.updateDisplay(); // Update display to show current date (this will also update time picker if datetime)
      this.updateCalendar();
      
      // Initialize time picker if datetime
      if (this.isDateTime && this.$calendar) {
        this.$calendar.find('.time-hour').val(this.selectedTime.hour);
        this.$calendar.find('.time-minute').val(this.selectedTime.minute);
        this.$calendar.find('.time-second').val(this.selectedTime.second);
        // Update value labels
        this.$calendar.find('.time-hour-value').text(this.selectedTime.hour);
        this.$calendar.find('.time-minute-value').text(this.selectedTime.minute);
        this.$calendar.find('.time-second-value').text(this.selectedTime.second);
      }
      
      if (this._useBodyPopup) {
        this._ensureCalendarOnBody();
        this._setupPositionListeners();
        this.$calendar.show();
        this.repositionPicker();
      } else {
        this.$calendar.show();
      }
      this._scheduleGridDisplayRefresh();
    }

    positionPickerForGridOrDialog() {
      if (this._useBodyPopup) {
        this.repositionPicker();
      }
    }

    destroy() {
      pcTrace("JalaliDatepicker.destroy", {
        value: this.$input?.val(),
        field: this.controlDate?.df?.fieldname,
      });
      this.close();
      if (this._inputEventNs && this.$input?.length) {
        this.$input.off(this._inputEventNs);
      }
      if (this.$calendar?.length) {
        this.$calendar.remove();
      }
      if (this.$input?.length) {
        this.$input.removeData("jalaliDatepickerInstance");
        this.$input.removeData("hasJalaliDatepicker");
        this.$input.removeAttr("data-has-jalali-datepicker");
        this.$input.removeData("jalaliInputEventNs");
      }
      this.$calendar = null;
      this.controlDate = null;
    }

    close() {
      this.isOpen = false;
      this._isDraggingSlider = false; // Reset dragging flag
      this._isApplyingValue = false; // Reset applying value flag
      this._suppressOpenUntil = Date.now() + 450;
      this._teardownPositionListeners();
      this.$calendar.hide();
      this._scheduleGridDisplayRefresh();

      // Remove event handlers to prevent memory leaks
      if (this._keydownHandler) {
        $(document).off('keydown.jalali-datepicker-' + (this.input.id || 'default'), this._keydownHandler);
        this._keydownHandler = null;
      }
      if (this._globalClickListener) {
        document.removeEventListener('click', this._globalClickListener, false);
        this._globalClickListener = null;
      }
      
    }
    
    // Navigation methods
    navigateMonth(direction) {
      if (this.view === 'days') {
        this.currentDate.jm += direction;
        if (this.currentDate.jm > 12) {
          this.currentDate.jm = 1;
          this.currentDate.jy++;
        } else if (this.currentDate.jm < 1) {
          this.currentDate.jm = 12;
          this.currentDate.jy--;
        }
        this.updateCalendar();
      } else if (this.view === 'months') {
        // In months view, navigate year by year
        this.currentDate.jy += direction;
        this.updateMonthsView();
      }
    }
    
    navigateYear(direction) {
      // Navigate by decade (like Gregorian calendar)
      this.yearRange.start += direction;
      this.yearRange.end += direction;
      
      // Update current year to center of new range
      this.currentDate.jy = this.yearRange.start + 4; // Middle of decade
      
      this.updateYearsView();
    }
    
    // View switching methods
    showMonthsView() {
      this.view = 'months';
      this.updateMonthsView();
      this.$calendar.find('.days-view').hide();
      this.$calendar.find('.years-view').hide();
      this.$calendar.find('.months-view').show();
    }
    
    showYearsView() {
      this.view = 'years';
      this.updateYearsView();
      this.$calendar.find('.days-view').hide();
      this.$calendar.find('.months-view').hide();
      this.$calendar.find('.years-view').show();
    }
    
    showDaysView() {
      this.view = 'days';
      this.updateCalendar();
      this.$calendar.find('.months-view').hide();
      this.$calendar.find('.years-view').hide();
      this.$calendar.find('.days-view').show();
    }

    updateCalendar() {
      if (
        !this.currentDate ||
        !Number.isFinite(this.currentDate.jy) ||
        !Number.isFinite(this.currentDate.jm)
      ) {
        this.currentDate = gToJ(new Date());
      }
      const monthNames = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 
                        'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
      
      // Update header
      const jm = this.currentDate.jm;
      const monthLabel =
        Number.isFinite(jm) && jm >= 1 && jm <= 12
          ? monthNames[jm - 1]
          : monthNames[0];
      this.$calendar.find('.month-year').text(`${monthLabel} ${this.currentDate.jy}`);
      
      // Show/hide navigation buttons
      this.$calendar.find('.prev-btn, .next-btn').show();
      this.$calendar.find('.prev-decade, .next-decade').hide();
      
      // Hide all views first
      this.$calendar.find('.days-view').hide();
      this.$calendar.find('.months-view').hide();
      this.$calendar.find('.years-view').hide();
      
      // Show only the current view
      if (this.view === 'days') {
        this.$calendar.find('.days-view').show();
        // Update weekdays based on FIRST_DAY
        this.updateWeekdays();
        // Update days
        this.updateDays();
      } else if (this.view === 'months') {
        this.$calendar.find('.months-view').show();
        this.updateMonthsView();
      } else if (this.view === 'years') {
        this.$calendar.find('.years-view').show();
        this.updateYearsView();
      }
      if (this.isOpen && this._useBodyPopup) {
        this.repositionPicker();
      }
    }
    
    updateWeekdays() {
      // ترتیب صحیح روزهای هفته بر اساس تنظیمات: شنبه=6, یکشنبه=0, دوشنبه=1, سه‌شنبه=2, چهارشنبه=3, پنج‌شنبه=4, جمعه=5
      const weekdayNames = ['ی', 'د', 'س', 'چ', 'پ', 'ج', 'ش']; // [یکشنبه, دوشنبه, سه‌شنبه, چهارشنبه, پنج‌شنبه, جمعه, شنبه]
      const $weekdaysContainer = this.$calendar.find('.weekdays');
      $weekdaysContainer.empty();
      
      // با توجه به FIRST_DAY = 6 (شنبه)، ترتیب نمایش باید: شنبه, یکشنبه, دوشنبه, سه‌شنبه, چهارشنبه, پنج‌شنبه, جمعه
      for (let i = 0; i < 7; i++) {
        const dayIndex = (FIRST_DAY + i) % 7;
        $weekdaysContainer.append($(`<div class="weekday" style="text-align: center; padding: 0; font-weight: 500; font-size: 9px; color: var(--text-light, #7c7c7c); font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif); width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;">${weekdayNames[dayIndex]}</div>`));
      }
    }

    updateDays() {
      const $daysGrid = this.$calendar.find('.days-grid');
      $daysGrid.empty();
      
      const daysInMonth = this.currentDate.jm <= 6 ? 31 : 
                         (this.currentDate.jm <= 11 ? 30 : 
                         (this.currentDate.jy % 4 === 3 ? 30 : 29));
      
      // Get first day of month (Saturday = 0)
      const firstDay = this.getFirstDayOfMonth(this.currentDate.jy, this.currentDate.jm);
      
      // Calculate previous month's last days
      let prevMonth = this.currentDate.jm - 1;
      let prevYear = this.currentDate.jy;
      if (prevMonth < 1) {
        prevMonth = 12;
        prevYear--;
      }
      const prevMonthDays = prevMonth <= 6 ? 31 : 
                           (prevMonth <= 11 ? 30 : 
                           (prevYear % 4 === 3 ? 30 : 29));
      
      // Add previous month's last days (light color, selectable)
      for (let i = firstDay - 1; i >= 0; i--) {
        const day = prevMonthDays - i;
        const $prevDay = $(`<div class="day-cell prev-month-day" data-day="${day}" data-month="${prevMonth}" data-year="${prevYear}" style="
          text-align: center;
          padding: 0;
          cursor: pointer;
          border-radius: 0;
          transition: all 0.2s ease;
          font-size: 11px;
          color: var(--text-light, #999);
          width: 30px;
          height: 30px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
          border: none;
          background: transparent;
        ">${day}</div>`);
        
        // Add click handler for previous month days - select the day directly
        $prevDay.on('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.currentDate.jy = prevYear;
          this.currentDate.jm = prevMonth;
          this.currentDate.jd = day;
          this.selectDate(day);
        });
        
        // Add hover effect
        $prevDay.hover(
          function() { $(this).css('background-color', '#f8f9fa'); },
          function() { $(this).css('background-color', 'transparent'); }
        );
        
        $daysGrid.append($prevDay);
      }
      
      for (let day = 1; day <= daysInMonth; day++) {
        const $day = $(`<div class="day-cell" data-day="${day}" style="
          text-align: center;
          padding: 0;
          cursor: pointer;
          border-radius: 0;
          transition: all 0.2s ease;
          font-size: 11px;
          color: var(--text-color, #36414c);
          width: 30px;
          height: 30px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
          border: none;
          background: transparent;
        ">${day}</div>`);
        
        // Add click handler
        $day.on('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.selectDate(day);
        });
        
        // Add hover effects
        $day.hover(
          function() { 
            if (!$(this).hasClass('selected') && !$(this).hasClass('today')) {
              $(this).css('background-color', '#f8f9fa');
            }
          },
          function() { 
            if (!$(this).hasClass('selected') && !$(this).hasClass('today')) {
              $(this).css('background-color', 'transparent');
            }
          }
        );
        
        // Highlight today (gray background like Gregorian)
        const today = gToJ(new Date());
        if (this.currentDate.jy === today.jy && 
            this.currentDate.jm === today.jm && 
            day === today.jd) {
          $day.addClass('today').css({
            'background-color': 'var(--control-bg, #f3f3f3)',
            'color': 'var(--text-color, #36414c)',
            'font-weight': 'bold'
          });
        }
        
        // Highlight selected day (black background like Gregorian)
        if (this.selectedDate && 
            this.selectedDate.jy === this.currentDate.jy &&
            this.selectedDate.jm === this.currentDate.jm &&
            this.selectedDate.jd === day) {
          $day.addClass('selected').css({
            'background-color': 'var(--primary, #171717)',
            'color': 'var(--bg-color, white)',
            'font-weight': 'bold'
          });
        }
        
        $daysGrid.append($day);
      }
      
      // Calculate next month's first days
      let nextMonth = this.currentDate.jm + 1;
      let nextYear = this.currentDate.jy;
      if (nextMonth > 12) {
        nextMonth = 1;
        nextYear++;
      }
      
      // Calculate how many cells we need to fill to complete the grid (6 rows = 42 cells)
      const totalCells = 42; // 6 rows * 7 days
      const currentCells = firstDay + daysInMonth;
      const remainingCells = totalCells - currentCells;
      
      // Add next month's first days (light color, selectable)
      for (let day = 1; day <= remainingCells; day++) {
        const $nextDay = $(`<div class="day-cell next-month-day" data-day="${day}" data-month="${nextMonth}" data-year="${nextYear}" style="
          text-align: center;
          padding: 0;
          cursor: pointer;
          border-radius: 0;
          transition: all 0.2s ease;
          font-size: 11px;
          color: var(--text-light, #999);
          width: 30px;
          height: 30px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
          border: none;
          background: transparent;
        ">${day}</div>`);
        
        // Add click handler for next month days - select the day directly
        $nextDay.on('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.currentDate.jy = nextYear;
          this.currentDate.jm = nextMonth;
          this.currentDate.jd = day;
          this.selectDate(day);
        });
        
        // Add hover effect
        $nextDay.hover(
          function() { $(this).css('background-color', '#f8f9fa'); },
          function() { $(this).css('background-color', 'transparent'); }
        );
        
        $daysGrid.append($nextDay);
      }
      
    }

    selectDate(day, closeCalendar) {
      if (closeCalendar === undefined) {
        closeCalendar = true;
      }
      
      this.selectedDate = {
        jy: this.currentDate.jy,
        jm: this.currentDate.jm,
        jd: day
      };
      
      
      // Update time from time picker if datetime
      if (this.isDateTime) {
        this.selectedTime = {
          hour: parseInt(this.$calendar.find('.time-hour').val()) || this.selectedTime.hour || 0,
          minute: parseInt(this.$calendar.find('.time-minute').val()) || this.selectedTime.minute || 0,
          second: parseInt(this.$calendar.find('.time-second').val()) || this.selectedTime.second || 0
        };
      }
      
      this.applySelectedValue(true);
      if (closeCalendar) {
        this.close();
      }
    }

    _syncInputOnly(jalaliStr, gregorianStr, commitToModel) {
      this.$input.val(jalaliStr);
      if (commitToModel && this.controlDate && this.controlDate.set_value) {
        jalaliDatetimeLog("set_value Gregorian", gregorianStr);
        this.controlDate.set_value(gregorianStr);
      }
    }

    applySelectedValue(commitToModel = true) {
      if (!this.selectedDate) {
        return;
      }

      this._isApplyingValue = true;

      const jy = parseInt(this.selectedDate.jy, 10);
      const jm = parseInt(this.selectedDate.jm, 10);
      const jd = parseInt(this.selectedDate.jd, 10);
      const h = parseInt(this.selectedTime.hour, 10) || 0;
      const mi = parseInt(this.selectedTime.minute, 10) || 0;
      const s = parseInt(this.selectedTime.second, 10) || 0;

      if (
        !Number.isFinite(jy) ||
        !Number.isFinite(jm) ||
        !Number.isFinite(jd) ||
        jy < 1200 ||
        jy > 1600
      ) {
        console.warn(
          "[persian_calendar] invalid Jalali date parts; not applying picker value",
          { jy, jm, jd }
        );
        this._isApplyingValue = false;
        return;
      }

      const jalaliStr = this.isDateTime
        ? formatJalaliDateTime(jy, jm, jd, h, mi, s)
        : formatJalaliDate(jy, jm, jd);

      let gregorianStr;
      if (this.isDateTime) {
        jalaliDatetimeLog("selected Jalali datetime", jalaliStr);
        if (this.controlDate && this.controlDate.grid_row) {
          jalaliGridLog("selected Jalali datetime", buildGridPickerContext(this.controlDate, {}), jalaliStr);
        }
        gregorianStr = getDateUtils().jalaliPartsDateTimeToGregorian(jy, jm, jd, h, mi, s);
      } else {
        jalaliDateLog("selected Jalali", { jy, jm, jd, jalaliStr });
        gregorianStr = getDateUtils().jalaliPartsToGregorianISO(jy, jm, jd);
      }

      if (!gregorianStr) {
        this._isApplyingValue = false;
        return;
      }

      gregorianStr = getDateUtils().stripMicroseconds(gregorianStr);
      jalaliDatetimeLog("converted Gregorian datetime", gregorianStr);
      if (this.isDateTime && this.controlDate && this.controlDate.grid_row) {
        jalaliGridLog("converted Gregorian datetime", buildGridPickerContext(this.controlDate, {}), gregorianStr);
      }

      if (!this.isDateTime) {
        const gParts = getDateUtils().parseYMD(gregorianStr);
        if (
          this.controlDate &&
          gParts &&
          !isGregorianWithinConstraints(this.controlDate, gParts.y, gParts.m, gParts.d)
        ) {
          this._isApplyingValue = false;
          return;
        }
      }

      if (this.controlDate && this.controlDate.set_value) {
        this._syncInputOnly(jalaliStr, gregorianStr, commitToModel);
      } else {
        this.$input.val(jalaliStr);
        if (commitToModel) {
          this.$input.trigger("change");
        }
      }

      const self = this;
      setTimeout(function () {
        self._isApplyingValue = false;
      }, 300);
    }

    selectToday() {
      const today = gToJ(new Date());
      
      // Update current date to today's month/year
      this.currentDate = { ...today };
      
      // Switch to days view to show the calendar properly
      this.view = 'days';
      
      // Update calendar display
      this.updateCalendar();
      
      // Select today's date
      this.selectDate(today.jd);
    }
    
    selectNow() {
      const now = new Date();
      const today = gToJ(now);
      
      // Update current date to today's month/year
      this.currentDate = { ...today };
      
      // Update time to current time
      this.selectedTime = {
        hour: now.getHours(),
        minute: now.getMinutes(),
        second: now.getSeconds()
      };
      
      // Update time picker sliders and labels
      if (this.$calendar && this.$calendar.length) {
        this.$calendar.find('.time-hour').val(this.selectedTime.hour);
        this.$calendar.find('.time-minute').val(this.selectedTime.minute);
        this.$calendar.find('.time-second').val(this.selectedTime.second);
        // Update value labels
        this.$calendar.find('.time-hour-value').text(this.selectedTime.hour);
        this.$calendar.find('.time-minute-value').text(this.selectedTime.minute);
        this.$calendar.find('.time-second-value').text(this.selectedTime.second);
      }
      
      // Set selected date
      this.selectedDate = { ...today };
      
      // Apply the value
      this.applySelectedValue();
      
      // Close calendar after selecting now
      this.close();
    }

    prevMonth() {
      if (this.currentDate.jm === 1) {
        this.currentDate.jm = 12;
        this.currentDate.jy--;
      } else {
        this.currentDate.jm--;
      }
      this.updateCalendar();
    }

    nextMonth() {
      if (this.currentDate.jm === 12) {
        this.currentDate.jm = 1;
        this.currentDate.jy++;
      } else {
        this.currentDate.jm++;
      }
      this.updateCalendar();
    }

    syncInputFromModel() {
      incCallCount("syncInputFromModel");
      if (!shouldUseJalaliCalendar()) {
        pcTrace("syncInputFromModel skipped (Gregorian)", {
          value: this.$input?.val(),
        });
        return;
      }
      const U = getDateUtils();
      if (!U) {
        return;
      }
      pcTrace("syncInputFromModel", { input: this.$input?.val() });
      let model = this.controlDate ? getControlModelValue(this.controlDate) : null;
      if (model != null && model !== "") {
        const iso = U.coerceToGregorianDateTime
          ? U.coerceToGregorianDateTime(model) || U.normalizeModelDateTime(model)
          : U.normalizeModelDateTime(model);
        if (iso) {
          model = iso;
        }
        const display = modelValueToDisplayInput(model, this.isDateTime);
        if (display && !isUnsafeJalaliDisplayString(display)) {
          this.$input.val(display);
        }
        return;
      }
      const visible = this.$input.val();
      if (visible && U.coerceToGregorianDateTime) {
        const iso = U.coerceToGregorianDateTime(visible);
        if (iso) {
          const display = modelValueToDisplayInput(iso, this.isDateTime);
          if (display && !isUnsafeJalaliDisplayString(display)) {
            this.$input.val(display);
          }
        }
      }
    }

    updateDisplay() {
      if (!shouldUseJalaliCalendar()) {
        return;
      }
      this.syncInputFromModel();
      const value = this.$input.val();
      pcTrace("updateDisplay", { value });
      if (value) {
        if (this.isDateTime) {
          const jalaliDateTime = parseJalaliDateTime(value);
          if (jalaliDateTime) {
            this.selectedDate = {
              jy: jalaliDateTime.jy,
              jm: jalaliDateTime.jm,
              jd: jalaliDateTime.jd
            };
            this.currentDate = { ...this.selectedDate };
            if (jalaliDateTime.hour !== undefined) {
              this.selectedTime = {
                hour: jalaliDateTime.hour || 0,
                minute: jalaliDateTime.minute || 0,
                second: jalaliDateTime.second || 0
              };
              // Update time picker sliders and labels if calendar exists
              if (this.$calendar && this.$calendar.length) {
                this.$calendar.find('.time-hour').val(this.selectedTime.hour);
                this.$calendar.find('.time-minute').val(this.selectedTime.minute);
                this.$calendar.find('.time-second').val(this.selectedTime.second);
                // Update value labels
                this.$calendar.find('.time-hour-value').text(this.selectedTime.hour);
                this.$calendar.find('.time-minute-value').text(this.selectedTime.minute);
                this.$calendar.find('.time-second-value').text(this.selectedTime.second);
              }
            }
          }
        } else {
          const jalali = parseJalaliDate(value);
          if (jalali) {
            this.selectedDate = jalali;
            this.currentDate = { ...jalali };
          }
        }
      }
      
      // Always reset to days view when updating display
      this.view = 'days';
    }
    
    // Month/Year view methods
    updateMonthsView() {
      // Update header to show only year
      this.$calendar.find('.month-year').text(`${this.currentDate.jy}`);
      
      // Hide/show navigation buttons - use year-by-year navigation for months view
      this.$calendar.find('.prev-btn, .next-btn').show();
      this.$calendar.find('.prev-decade, .next-decade').hide();
      
      const monthNames = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 
                        'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
      
      const $monthsGrid = this.$calendar.find('.months-grid');
      $monthsGrid.empty();
      
      monthNames.forEach((month, index) => {
        const $month = $(`<div class="month-cell" data-month="${index + 1}" style="
          text-align: center;
          padding: 3px 2px;
          cursor: pointer;
          border-radius: 0;
          transition: all 0.2s ease;
          font-size: 11px;
          color: var(--text-color, #36414c);
          border: 1px solid var(--border-color, #e2e2e2);
          font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
          background: transparent;
        ">${month}</div>`);
        
        // Add click handler
        $month.on('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.currentDate.jm = index + 1;
          this.showDaysView();
        });
        
        // Add hover effects
        $month.hover(
          function() { 
            if (!$(this).hasClass('selected')) {
              $(this).css('background-color', '#f8f9fa');
            }
          },
          function() { 
            if (!$(this).hasClass('selected')) {
              $(this).css('background-color', 'transparent');
            }
          }
        );
        
        // Check if current month - use site theme colors like Gregorian
        if (this.currentDate.jm === index + 1) {
          $month.addClass('selected').css({
            'background-color': 'var(--primary, #171717)',
            'color': 'var(--bg-color, white)',
            'font-weight': 'bold'
          });
        }
        
        $monthsGrid.append($month);
      });
    }
    
    updateYearsView() {
      // Calculate year range centered around current year (like Gregorian calendar)
      const currentYear = this.currentDate.jy;
      const startYear = Math.floor(currentYear / 10) * 10; // Round down to decade
      const endYear = startYear + 9;
      
      // Update yearRange for navigation
      this.yearRange = { start: startYear, end: endYear };
      
      // Update header to show year range
      this.$calendar.find('.month-year').text(`${this.yearRange.start} - ${this.yearRange.end}`);
      
      // Hide/show navigation buttons
      this.$calendar.find('.prev-btn, .next-btn').hide();
      this.$calendar.find('.prev-decade, .next-decade').show();
      
      const $yearsGrid = this.$calendar.find('.years-grid');
      $yearsGrid.empty();
      
      // Show years from startYear-1 to endYear+1 (like Gregorian calendar)
      for (let year = startYear - 1; year <= endYear + 1; year++) {
        const $year = $(`<div class="year-cell" data-year="${year}" style="
          text-align: center;
          padding: 3px 2px;
          cursor: pointer;
          border-radius: 0;
          transition: all 0.2s ease;
          font-size: 11px;
          color: var(--text-color, #36414c);
          border: 1px solid var(--border-color, #e2e2e2);
          font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
          background: transparent;
        ">${year}</div>`);
        
        // Add click handler
        $year.on('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.currentDate.jy = year;
          this.showMonthsView();
        });
        
        // Add hover effects
        $year.hover(
          function() { 
            if (!$(this).hasClass('selected')) {
              $(this).css('background-color', '#f8f9fa');
            }
          },
          function() { 
            if (!$(this).hasClass('selected')) {
              $(this).css('background-color', 'transparent');
            }
          }
        );
        
        // Check if current year - use site theme colors like Gregorian
        if (this.currentDate.jy === year) {
          $year.addClass('selected').css({
            'background-color': 'var(--primary, #171717) !important',
            'color': 'var(--bg-color, white) !important',
            'font-weight': 'bold !important'
          });
        }
        
        // Make years outside range faded (like Gregorian calendar)
        if (year < startYear || year > endYear) {
          $year.addClass('other-decade').css({
            'color': 'var(--text-light, #999) !important',
            'cursor': 'not-allowed !important',
            'opacity': '0.4 !important'
          });
          
          // Disable click for years outside range
          $year.off('click').on('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            // Do nothing for years outside range
          });
          
          // Remove hover effect for years outside range
          $year.off('mouseenter mouseleave');
        }
        
        $yearsGrid.append($year);
      }
    }
    
    getFirstDayOfMonth(year, month) {
      // Calculate first day of Jalali month
      // Convert Jalali date to Gregorian to get the weekday
      const gregorian = jToG(year, month, 1);
      if (!gregorian) return 0;
      const date = new Date(gregorian.gy, gregorian.gm - 1, gregorian.gd);
      
      // Convert JavaScript weekday (Sunday=0) to our weekday system (Saturday=0)
      // JavaScript: Sunday=0, Monday=1, Tuesday=2, Wednesday=3, Thursday=4, Friday=5, Saturday=6
      // Our system: Saturday=0, Sunday=1, Monday=2, Tuesday=3, Wednesday=4, Thursday=5, Friday=6
      const jsWeekday = date.getDay(); // 0=Sunday, 6=Saturday
      return (jsWeekday + 1) % 7; // Convert to our system: Saturday=0, Sunday=1, etc.
    }
  }

  function buildGridPickerContext(field, ctx) {
    const grid = ctx?.grid || field?.grid;
    const grid_row = ctx?.grid_row || field?.grid_row;
    return {
      doctype: grid_row?.doc?.doctype || field?.doctype || ctx?.frm?.doctype,
      parentfield: grid?.df?.fieldname,
      child_fieldname: field?.df?.fieldname,
      row_name: grid_row?.doc?.name,
    };
  }

  const JALALI_GRID_DISPLAY_DEBUG = false;

  function jalaliGridDisplayLog(payload) {
    if (JALALI_GRID_DISPLAY_DEBUG) {
      console.log("[jalali_grid_display]", payload);
    }
  }

  function getGridRowFieldDf(grid_row, fieldname) {
    if (!grid_row) {
      return null;
    }
    const fields =
      grid_row.grid?.user_defined_columns?.length > 0
        ? grid_row.grid.user_defined_columns
        : grid_row.docfields;
    return fields?.find((col) => col?.fieldname === fieldname) || null;
  }

  function getGridRowModelValue(grid_row, fieldname) {
    const doc = grid_row?.doc;
    if (!doc?.doctype || doc.name == null) {
      return null;
    }
    try {
      if (frappe.model?.get_doc) {
        const d = frappe.model.get_doc(doc.doctype, doc.name);
        if (d && d[fieldname] != null && d[fieldname] !== "") {
          return d[fieldname];
        }
      }
    } catch (e) {
      /* ignore */
    }
    if (typeof locals !== "undefined" && locals[doc.doctype]?.[doc.name]) {
      const v = locals[doc.doctype][doc.name][fieldname];
      if (v != null && v !== "") {
        return v;
      }
    }
    return doc[fieldname];
  }

  function findGridCellStaticArea(grid_row, fieldname) {
    const column = grid_row.columns?.[fieldname];
    if (column?.static_area?.length) {
      return column.static_area;
    }
    const $rowWrap = getGridRowWrapper(grid_row);
    if ($rowWrap.length) {
      const $area = $rowWrap
        .find(
          `.grid-static-col[data-fieldname="${fieldname}"] .static-area, [data-fieldname="${fieldname}"] .static-area`
        )
        .first();
      if ($area.length) {
        return $area;
      }
    }
    return null;
  }

  function isGridCellPlaceholderText(text, df) {
    const t = String(text || "").trim();
    if (!t) {
      return true;
    }
    if (df?.label) {
      const label = __(df.label, null, df.parent);
      if (t === label || t === df.label) {
        return true;
      }
    }
    if (/^(from time|to time|from date|to date)$/i.test(t)) {
      return true;
    }
    return false;
  }

  function applyJalaliGridCellDisplay(grid_row, fieldname) {
    if (!shouldUseJalaliCalendar() || !grid_row?.doc) {
      return;
    }
    const U = getDateUtils();
    if (!U?.valueToJalaliDisplay) {
      return;
    }
    const df = getGridRowFieldDf(grid_row, fieldname);
    if (!df || (df.fieldtype !== "Date" && df.fieldtype !== "Datetime")) {
      return;
    }
    const raw = getGridRowModelValue(grid_row, fieldname);
    if (raw == null || raw === "") {
      return;
    }
    const display = U.valueToJalaliDisplay(raw, df.fieldtype);
    if (display == null || display === "") {
      return;
    }
    const $area = findGridCellStaticArea(grid_row, fieldname);
    if (!$area?.length) {
      return;
    }
    const current = ($area.text() || "").trim();
    if (current === String(display)) {
      return;
    }
    if (!isGridCellPlaceholderText(current, df)) {
      const looksLikeDate =
        U.looksLikeGregorianUserDisplay?.(current) ||
        /^\d{1,2}-\d{1,2}-\d{4}/.test(current) ||
        /^\d{4}-\d{2}-\d{2}/.test(current) ||
        /^1[2-4]\d{2}-\d{1,2}-\d{1,2}/.test(current);
      if (!looksLikeDate) {
        return;
      }
    }
    jalaliGridDisplayLog({
      child_doctype: grid_row.doc.doctype,
      row_name: grid_row.doc.name,
      fieldname,
      raw_model_value: raw,
      current_cell_text: current,
      converted_display: display,
    });
    const html = frappe.utils?.escape_html ? frappe.utils.escape_html(display) : display;
    $area.html(html);
  }

  function applyJalaliGridRowDisplay(grid_row) {
    if (!grid_row?.docfields) {
      return;
    }
    grid_row.docfields.forEach((df) => {
      if (df.fieldtype === "Date" || df.fieldtype === "Datetime") {
        applyJalaliGridCellDisplay(grid_row, df.fieldname);
      }
    });
  }

  function applyJalaliGridAllDisplay(frm) {
    if (!frm || !shouldUseJalaliCalendar()) {
      return;
    }
    Object.values(frm.fields_dict || {}).forEach((f) => {
      if (!f?.grid?.grid_rows) {
        return;
      }
      f.grid.grid_rows.forEach((row) => applyJalaliGridRowDisplay(row));
    });
  }

  function scheduleJalaliGridDisplayPasses(frm) {
    if (!frm) {
      return;
    }
    const run = () => applyJalaliGridAllDisplay(frm);
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(run);
    }
    setTimeout(run, 0);
    setTimeout(run, 100);
    setTimeout(run, 300);
  }

  let gridRowRefreshJalaliPatched = false;

  function installGridRowRefreshPatch() {
    const GridRow = frappe.ui.form?.GridRow;
    if (!GridRow || gridRowRefreshJalaliPatched) {
      return;
    }
    gridRowRefreshJalaliPatched = true;
    const origRefreshField = GridRow.prototype.refresh_field;
    GridRow.prototype.refresh_field = function (fieldname, txt) {
      origRefreshField.apply(this, arguments);
      if (!shouldUseJalaliCalendar()) {
        // Passive in Gregorian mode: never write back to the model and never rebuild
        // the native Air Datepicker here. Doing so during a date selection re-triggered
        // refresh_field → ensure → reinit → set_value and froze the page. The native
        // picker is created once at control creation; CSV imports are normalized via
        // normalizeImportedChildTableRows on the Table refresh, not per cell.
        const df = getGridRowFieldDf(this, fieldname);
        if (df && (df.fieldtype === "Datetime" || df.fieldtype === "Date")) {
          pcLoopTrace("GridRow.refresh_field(Gregorian)", {
            field: fieldname,
            doctype: this.doc?.doctype,
            parenttype: this.doc?.parenttype,
          });
        }
        return;
      }
      applyJalaliGridCellDisplay(this, fieldname);
      const field = this.on_grid_fields_dict?.[fieldname];
      if (field) {
        const ctx = { frm: this.frm, grid: this.grid, grid_row: this };
        setTimeout(() => ensureJalaliPickerForControl(field, ctx), 0);
        if (field.$input?.length) {
          destroyAirDatepickerForInput(field.$input);
        }
      }
    };
  }

  function bindGridDisplayMutationObserver(frm) {
    if (!frm || frm._jalaliGridDisplayObserver) {
      return;
    }
    const $body = getFormWrapper(frm)
      .find(".form-grid-container .form-grid-body")
      .first();
    if (!$body.length) {
      return;
    }
    let debounceTimer = null;
    const flush = () => {
      debounceTimer = null;
      applyJalaliGridAllDisplay(frm);
      scheduleScanFormJalaliFields(frm);
    };
    const observer = new MutationObserver(() => {
      if (debounceTimer) {
        clearTimeout(debounceTimer);
      }
      debounceTimer = setTimeout(flush, 50);
    });
    observer.observe($body[0], {
      childList: true,
      subtree: true,
      characterData: true,
    });
    frm._jalaliGridDisplayObserver = observer;
  }

  function attachJalaliPickerToGridInput($input, fieldtype, fieldname, grid_row, frm, control) {
    if (!$input || !$input.length) return null;
    if (!shouldUseJalaliCalendar()) {
      pcTrace("attachJalaliPickerToGridInput blocked (Gregorian)", {
        fieldname,
        value: $input.val(),
      });
      destroyJalaliDatepickerOnInput($input);
      return null;
    }
    pcTrace("attachJalaliPickerToGridInput", { fieldname, value: $input.val() });
    const existing = $input.data("jalaliDatepickerInstance");
    if (existing) {
      destroyAirDatepickerForInput($input);
      return existing;
    }

    destroyAirDatepickerForInput($input);
    $input.removeClass("datepicker-input hasDatepicker");
    $input.off(".datepicker");

    const isDateTime = fieldtype === "Datetime";
    const $wrapper = $input.closest(".frappe-control, .form-group");

    const fakeControl = control || {
      df: { fieldtype: fieldtype, fieldname: fieldname },
      $wrapper: $wrapper.length ? $wrapper : $input.parent(),
      $input: $input,
      grid_row: grid_row,
      frm: frm,
      set_value: function (value) {
        const U = getDateUtils();
        let v = value;
        if (U && fieldtype === "Datetime" && value) {
          v = U.normalizeModelDateTime(value);
        } else if (U && fieldtype === "Date" && value) {
          v = U.normalizeModelDate(value);
        }
        if (v != null && v !== "") {
          $input.data("jalali-model-value", v);
        } else {
          $input.removeData("jalali-model-value");
        }
        $input.val(
          fieldtype === "Datetime" && U
            ? modelValueToDisplayInput(v, true)
            : fieldtype === "Date" && U
              ? modelValueToDisplayInput(v, false)
              : v
        );
        if (grid_row && grid_row.doc && fieldname) {
          grid_row.doc[fieldname] = v;
          if (frm && frappe.model && frappe.model.set_value) {
            frappe.model.set_value(grid_row.doc.doctype, grid_row.doc.name, fieldname, v);
          }
          applyJalaliGridCellDisplay(grid_row, fieldname);
        }
        $input.trigger("change");
      },
      get_value: function () {
        const stored = $input.data("jalali-model-value");
        if (stored) return stored;
        const U = getDateUtils();
        const raw = $input.val();
        if (!raw || !U) return raw;
        if (fieldtype === "Datetime") {
          return U.normalizeModelDateTime(String(raw).trim());
        }
        if (fieldtype === "Date") {
          return U.normalizeModelDate(String(raw).trim());
        }
        return raw;
      },
    };

    const picker = new JalaliDatepicker($input[0], fakeControl, isDateTime);
    $input.data("hasJalaliDatepicker", true);
    $input.attr("data-has-jalali-datepicker", "true");
    $input.data("jalaliDatepickerInstance", picker);

    if (grid_row && fieldname) {
      coerceGridRowDatetimeField(grid_row, fieldname, fieldtype);
    }

    const raw =
      (grid_row && grid_row.doc && grid_row.doc[fieldname]) || $input.val();
    if (raw) {
      const display = modelValueToDisplayInput(raw, isDateTime);
      if (display && !isUnsafeJalaliDisplayString(display)) {
        $input.val(display);
        picker.syncInputFromModel();
        picker.updateDisplay();
      }
    }
    return picker;
  }

  function clearJalaliShimDatepicker(field) {
    if (!field) {
      return;
    }
    const dp = field.datepicker;
    if (dp && (dp._pcJalaliShim || !dp.$datepicker)) {
      field.datepicker = null;
    }
  }

  function hasNativeAirDatepicker(field) {
    if (!field?.$input?.length) {
      return false;
    }
    const dp = field.datepicker || field.$input.data("datepicker");
    return !!(dp && dp.$datepicker);
  }

  /**
   * Passive Gregorian cleanup for control refresh: strip a leftover Jalali picker when
   * switching from Jalali to Gregorian, but NEVER rebuild the native Air Datepicker
   * (Frappe's own refresh_input/make_input owns it). Rebuilding here re-fired change →
   * Grid.set_value → refresh_field → refresh_input and froze the page.
   */
  function cleanupStaleJalaliInGregorian(field) {
    if (!field || shouldUseJalaliCalendar()) {
      return;
    }
    if (field.jalaliDatepicker) {
      stripJalaliPickerFromField(field);
      field.jalaliDatepicker = null;
    }
    clearJalaliShimDatepicker(field);
    if (
      field.$input?.length &&
      (field.$input.data("jalaliDatepickerInstance") ||
        field.$input.attr("data-has-jalali-datepicker") === "true")
    ) {
      destroyJalaliDatepickerOnInput(field.$input);
    }
  }

  function ensureGregorianNativeDatepickerActive(field) {
    if (!field?.$input?.length || shouldUseJalaliCalendar()) {
      return;
    }
    if (field._pcEnsuringGregorian) {
      pcLoopTrace("ensureGregorianNativeDatepickerActive reentry blocked", {
        field: field.df?.fieldname,
      });
      return;
    }
    field._pcEnsuringGregorian = true;
    try {
      pcLoopTrace("ensureGregorianNativeDatepickerActive", {
        field: field.df?.fieldname,
        fieldtype: field.df?.fieldtype,
      });
      clearJalaliShimDatepicker(field);
      const hadJalaliArtifact =
        field.$input.data("jalaliDatepickerInstance") ||
        field.$input.attr("data-has-jalali-datepicker") === "true";
      if (hadJalaliArtifact) {
        destroyJalaliDatepickerOnInput(field.$input);
      }
      // Only (re)build a native picker when one is genuinely missing. Never rebuild an
      // already-working native Air Datepicker — doing so during onSelect causes a loop.
      if (!hasNativeAirDatepicker(field)) {
        reinitializeGregorianDateControl(field);
      }
      hookGregorianPickerOnShow(field);
    } finally {
      field._pcEnsuringGregorian = false;
    }
  }

  function logGregorianGridPickerClick($input, field, extra) {
    try {
      if (localStorage.getItem("persian_calendar_grid_picker_debug") !== "1") {
        return;
      }
    } catch (e) {
      return;
    }
    const $fc = $input.closest(".frappe-control");
    const rt = frappe.persian_calendar?.runtime;
    const dpData = $input.data("datepicker");
    const controlDp = field?.datepicker;
    const events =
      $input[0] &&
      (typeof $._data === "function"
        ? $._data($input[0], "events")
        : $input[0].__events);
    console.warn("[persian_calendar grid picker debug]", {
      fieldname: field?.df?.fieldname || $fc.attr("data-fieldname"),
      fieldtype: field?.df?.fieldtype || $fc.attr("data-fieldtype"),
      effective_mode: rt?.getEffectiveCalendarModeSync?.(),
      readOnly: $input.prop("readOnly"),
      disabled: $input.prop("disabled"),
      hasDatepicker: $input.hasClass("hasDatepicker"),
      dataDatepicker: !!dpData,
      controlDatepicker: !!controlDp,
      controlDatepickerIsShim: !!(controlDp && controlDp._pcJalaliShim),
      nativeAir: hasNativeAirDatepicker(field || { $input, datepicker: controlDp }),
      jalaliOnField: !!field?.jalaliDatepicker,
      jalaliOnInput: !!$input.data("jalaliDatepickerInstance"),
      inputHandlers: events ? Object.keys(events) : null,
      airPopupVisible: (function () {
        const nodes = document.querySelectorAll(".datepicker");
        for (let i = 0; i < nodes.length; i++) {
          const s = window.getComputedStyle(nodes[i]);
          if (s.display !== "none" && s.visibility !== "hidden" && nodes[i].offsetParent) {
            return true;
          }
        }
        return false;
      })(),
      ...extra,
    });
  }

  function installGregorianGridPickerDebug() {
    if (window.__pcGregorianGridPickerDebugInstalled) {
      return;
    }
    window.__pcGregorianGridPickerDebugInstalled = true;
    $(document).on(
      "mousedown.pcGregorianGridPickerDebug click.pcGregorianGridPickerDebug",
      ".form-grid .frappe-control[data-fieldtype='Datetime'] input, .form-grid .frappe-control[data-fieldtype='Date'] input, .form-in-grid .frappe-control[data-fieldtype='Datetime'] input, .form-in-grid .frappe-control[data-fieldtype='Date'] input",
      function () {
        if (shouldUseJalaliCalendar()) {
          return;
        }
        const $input = $(this);
        const $fc = $input.closest(".frappe-control");
        const fieldname = $fc.attr("data-fieldname");
        let field = null;
        if (cur_frm) {
          for (const f of Object.values(cur_frm.fields_dict || {})) {
            if (!f?.grid?.grid_rows) {
              continue;
            }
            for (const r of f.grid.grid_rows) {
              if (gridRowContainsInput(r, $input)) {
                field = r.on_grid_fields_dict?.[fieldname];
                break;
              }
            }
            if (field) {
              break;
            }
          }
        }
        logGregorianGridPickerClick($input, field, { phase: "click" });
        setTimeout(() => logGregorianGridPickerClick($input, field, { phase: "after50ms" }), 50);
      }
    );
  }

  function stripJalaliPickerFromField(field) {
    if (!field) {
      return;
    }
    if (field.jalaliDatepicker) {
      try {
        field.jalaliDatepicker.close();
      } catch (e) {
        /* ignore */
      }
      if (field.$input && field.$input.length) {
        field.$input.siblings(".jalali-datepicker").remove();
        field.$input.removeData("jalaliDatepickerInstance");
        field.$input.removeAttr("data-has-jalali-datepicker");
        field.$input.removeData("hasJalaliDatepicker");
      }
      field.jalaliDatepicker = null;
    }
    if (field.$input && field.$input.length) {
      destroyJalaliDatepickerOnInput(field.$input);
    }
    clearJalaliShimDatepicker(field);
  }

  /** Remove Jalali UI only; never tear down Frappe's native Air Datepicker. */
  function removeJalaliFromField(field) {
    stripJalaliPickerFromField(field);
  }

  /** ISO model value for Frappe native set_formatted_input (avoids DD-MM mis-parse in picker). */
  function gregorianInputValueForBase(control, incomingValue) {
    const iso = getGregorianControlModelIso(control);
    if (iso) {
      return iso;
    }
    const U = getDateUtils();
    if (!U || incomingValue == null || incomingValue === "") {
      return incomingValue;
    }
    const ft = control?.df?.fieldtype;
    if (ft === "Datetime") {
      return (
        U.coerceToGregorianDateTime(incomingValue) ||
        U.normalizeModelDateTime(incomingValue) ||
        incomingValue
      );
    }
    if (ft === "Date") {
      const d =
        U.coerceToGregorianDateTime(incomingValue) || U.normalizeModelDate(incomingValue);
      return d ? String(d).slice(0, 10) : incomingValue;
    }
    return incomingValue;
  }

  function getGregorianControlModelIso(field) {
    const U = getDateUtils();
    if (!field || !U) {
      return null;
    }
    const ft = field.df?.fieldtype;
    if (ft !== "Date" && ft !== "Datetime") {
      return null;
    }
    // Read-only: never mutate the model from this getter. (A coerce-write here
    // re-triggered grid set_value → refresh → set_formatted_input → loop.)
    let raw =
      (field.grid_row?.doc && field.df?.fieldname
        ? field.grid_row.doc[field.df.fieldname]
        : null) ??
      (typeof field.get_model_value === "function" ? field.get_model_value() : null) ??
      (field.doc && field.df?.fieldname ? field.doc[field.df.fieldname] : null);
    if (raw == null || raw === "") {
      return null;
    }
    if (ft === "Datetime") {
      return U.coerceToGregorianDateTime(raw) || U.normalizeModelDateTime(raw);
    }
    const d = U.coerceToGregorianDateTime(raw) || U.normalizeModelDate(raw);
    return d ? String(d).slice(0, 10) : null;
  }

  /** Parse storage ISO only — never ambiguous DD-MM-YYYY display text. */
  function gregorianIsoToPickerDate(iso, fieldtype) {
    if (!iso) {
      return null;
    }
    const s = String(iso).trim();
    const isDt = fieldtype === "Datetime";
    if (isDt) {
      let m = moment(s, ["YYYY-MM-DD HH:mm:ss", "YYYY-MM-DD HH:mm"], true);
      if (!m.isValid()) {
        const U = getDateUtils();
        const c = U?.coerceToGregorianDateTime(s);
        if (c) {
          m = moment(c, "YYYY-MM-DD HH:mm:ss", true);
        }
      }
      return m.isValid() ? m.toDate() : null;
    }
    const m = moment(s.slice(0, 10), "YYYY-MM-DD", true);
    return m.isValid() ? m.toDate() : null;
  }

  function syncGregorianNativePickerFromModel(field) {
    if (!field || shouldUseJalaliCalendar() || !field.datepicker) {
      return;
    }
    if (field._pcInPickerSync) {
      pcLoopTrace("syncGregorianNativePickerFromModel reentry blocked", {
        field: field.df?.fieldname,
      });
      return;
    }
    const iso = getGregorianControlModelIso(field);
    if (!iso) {
      return;
    }
    const dateObj = gregorianIsoToPickerDate(iso, field.df?.fieldtype);
    if (!dateObj) {
      return;
    }
    const existing =
      Array.isArray(field.datepicker.selectedDates) &&
      field.datepicker.selectedDates.length
        ? field.datepicker.selectedDates[0]
        : null;
    const sameSelected =
      existing instanceof Date && existing.getTime() === dateObj.getTime();
    field._pcInPickerSync = true;
    try {
      if (!sameSelected) {
        field.datepicker.selectDate(dateObj);
      }
      // air-datepicker v2: the nav title is rendered from `currentDate`, and only the
      // `date` setter updates currentDate AND re-renders the nav (`nav._render()`).
      // Assigning `viewDate`/`selectDate` alone leaves a stale title (showed "today").
      // The `date` setter does NOT fire onSelect, so this cannot re-enter set_value.
      field.datepicker.viewDate = dateObj;
      try {
        field.datepicker.date = dateObj;
      } catch (e) {
        const $dp = field.datepicker.$datepicker;
        if ($dp && $dp.length && typeof moment !== "undefined") {
          $dp
            .find(".datepicker--nav-title")
            .text(moment(dateObj).format("MMMM, YYYY"));
        }
      }
    } catch (e) {
      pcTrace("syncGregorianNativePickerFromModel failed", {
        field: field.df?.fieldname,
        iso,
        error: String(e),
      });
    } finally {
      field._pcInPickerSync = false;
    }
  }

  function hookGregorianPickerOnShow(field) {
    if (!field?.datepicker || shouldUseJalaliCalendar()) {
      return;
    }
    const dp = field.datepicker;
    if (dp._pcGregorianOnShowHooked) {
      return;
    }
    dp._pcGregorianOnShowHooked = true;
    const origOnShow = dp.opts && dp.opts.onShow;
    const wrappedOnShow = () => {
      pcLoopTrace("gregorianPickerOnShow", { field: field.df?.fieldname });
      syncGregorianNativePickerFromModel(field);
      if (typeof origOnShow === "function") {
        try {
          origOnShow.call(dp);
        } catch (e) {
          /* ignore */
        }
      }
    };
    if (typeof dp.update === "function") {
      dp.update({ onShow: wrappedOnShow });
    } else if (dp.opts) {
      dp.opts.onShow = wrappedOnShow;
    }
  }

  /**
   * Gregorian display in user format, but Air Datepicker selected/view date from ISO model.
   */
  function setGregorianFormattedInputFromModel(control, value) {
    const ft = control.df?.fieldtype;
    const BaseSet =
      ft === "Datetime"
        ? BaseControlDatetime.prototype.set_formatted_input
        : BaseControlDate.prototype.set_formatted_input;
    if (!value) {
      return BaseSet.call(control, value);
    }
    ensureGregorianNativeDatepicker(control);
    const U = getDateUtils();
    let iso = getGregorianControlModelIso(control);
    if (!iso && U) {
      iso =
        ft === "Datetime"
          ? U.coerceToGregorianDateTime(value) || U.normalizeModelDateTime(value)
          : U.coerceToGregorianDateTime(value) || U.normalizeModelDate(value);
      if (iso && ft === "Date") {
        iso = String(iso).slice(0, 10);
      }
    }
    if (!iso) {
      return BaseSet.call(control, value);
    }
    const display =
      ft === "Datetime"
        ? BaseControlDatetime.prototype.format_for_input.call(control, iso)
        : BaseControlDate.prototype.format_for_input.call(control, iso);
    if (control.$input?.length) {
      control.$input.val(display);
    }
    if (control.datepicker) {
      const dateObj = gregorianIsoToPickerDate(iso, ft);
      if (dateObj) {
        control.datepicker.selectDate(dateObj);
        control.datepicker.viewDate = dateObj;
      }
    }
    control.last_value = display;
  }

  /** Gregorian mode: ensure native Air Datepicker exists (passive — no custom click/focus hooks). */
  function ensureGregorianNativeDatepicker(field) {
    ensureGregorianNativeDatepickerActive(field);
  }

  function reinitializeGregorianDateControl(field) {
    if (!field || !field.$input || !field.$input.length || !field.df) {
      return;
    }
    const ft = field.df.fieldtype;
    if (ft !== "Date" && ft !== "Datetime") {
      return;
    }
    pcLoopTrace("reinitializeGregorianDateControl", {
      field: field.df.fieldname,
      fieldtype: ft,
      doctype: field.df.parent,
    });
    const ControlClass =
      ft === "Datetime"
        ? frappe.ui.form.ControlDatetime
        : frappe.ui.form.ControlDate;
    if (!ControlClass || !ControlClass.prototype.make_input) {
      return;
    }
    const savedVal =
      (field.doc && field.df.fieldname ? field.doc[field.df.fieldname] : null) ??
      field.value ??
      (typeof field.get_value === "function" ? field.get_value() : null);
    stripJalaliPickerFromField(field);
    if (field.$input?.length && !isTimeFieldInput(field.$input)) {
      destroyAirDatepickerForInput(field.$input);
    }
    ControlClass.prototype.make_input.call(field);
    // Display only — never write back to the model here. Calling set_value from picker
    // (re)init would re-trigger refresh_field → ensure → reinit and freeze the page.
    if (savedVal != null && savedVal !== "" && typeof field.set_formatted_input === "function") {
      field.set_formatted_input(savedVal);
    }
    hookGregorianPickerOnShow(field);
  }

  function teardownGregorianCalendarUI() {
    closeAllJalaliDatepickers();
    $(".jalali-datepicker").remove();
    $('input[data-has-jalali-datepicker="true"]').each(function () {
      const $input = $(this);
      const inst = $input.data("jalaliDatepickerInstance");
      if (inst && inst.close) {
        inst.close();
      }
      $input.removeData("jalaliDatepickerInstance");
      $input.removeAttr("data-has-jalali-datepicker");
      $input.removeData("hasJalaliDatepicker");
      $input.siblings(".jalali-datepicker").remove();
    });
    const frm = typeof cur_frm !== "undefined" ? cur_frm : null;
    if (frm) {
      frm.refresh_fields();
    }
  }

  function ensureJalaliPickerForControl(field, ctx) {
    if (!field || !field.df) return;
    const ft = field.df.fieldtype;
    if (ft !== "Date" && ft !== "Datetime") return;
    if (!shouldUseJalaliCalendar()) {
      stripJalaliPickerFromField(field);
      ensureGregorianNativeDatepickerActive(field);
      return;
    }

    const logCtx = buildGridPickerContext(field, ctx);
    jalaliGridLog("ensure control", logCtx, {
      has_picker: !!field.jalaliDatepicker,
      input: field.$input && field.$input[0],
    });

    if (field.jalaliDatepicker) {
      const inputEl = field.$input && field.$input[0];
      if (inputEl && field.jalaliDatepicker.input === inputEl) {
        if (field.$input && field.$input.length) {
          destroyAirDatepickerForInput(field.$input);
        }
        return;
      }
      stripJalaliPickerFromField(field);
    }

    if (field.$input && field.$input.length) {
      destroyAirDatepickerForInput(field.$input);
    }

    if (typeof field.replaceWithJalaliDatepicker === "function") {
      field.removeAirDatepickerInstances?.();
      if (typeof field.setupInputWithoutAirDatepicker === "function") {
        field.setupInputWithoutAirDatepicker();
      }
      field.replaceWithJalaliDatepicker();
      const val =
        field.value != null && field.value !== ""
          ? field.value
          : field.doc && field.df.fieldname
            ? field.doc[field.df.fieldname]
            : null;
      if (val && field.set_formatted_input) {
        field.set_formatted_input(val);
      }
      jalaliGridLog("attached via control", logCtx, { raw: val });
      return;
    }

    if (field.$input && field.$input.length) {
      attachJalaliPickerToGridInput(
        field.$input,
        ft,
        field.df.fieldname,
        ctx?.grid_row || field.grid_row,
        ctx?.frm || field.frm,
        field
      );
    }
  }

  function scanGridRowVisibleInputs(grid_row, frm) {
    const $row = getGridRowWrapper(grid_row);
    if (!$row.length) return;
    $row
      .find('.field-area:visible .frappe-control[data-fieldtype="Datetime"] input, .field-area:visible .frappe-control[data-fieldtype="Date"] input')
      .each(function () {
        const $input = $(this);
        if ($input.data("jalaliDatepickerInstance")) return;
        const $fc = $input.closest(".frappe-control");
        const fieldname = $fc.attr("data-fieldname");
        const fieldtype = $fc.attr("data-fieldtype");
        const control = grid_row.on_grid_fields_dict?.[fieldname];
        if (control) {
          ensureJalaliPickerForControl(control, {
            frm,
            grid: grid_row.grid,
            grid_row,
          });
        } else {
          jalaliGridLog("orphan grid input", {
            fieldname,
            fieldtype,
            row_name: grid_row.doc?.name,
          });
          attachJalaliPickerToGridInput(
            $input,
            fieldtype,
            fieldname,
            grid_row,
            frm
          );
        }
      });
  }

  async function scanFormJalaliFields(frm) {
    if (!frm) return;
    await getCalendarSettings();
    if (!shouldUseJalaliCalendar()) return;

    Object.values(frm.fields_dict || {}).forEach((f) => {
      if (!f || !f.grid) return;
      const grid = f.grid;
      (grid.grid_rows || []).forEach((row) => {
        (row.on_grid_fields || []).forEach((field) => {
          ensureJalaliPickerForControl(field, { frm, grid, grid_row: row });
        });
        scanGridRowVisibleInputs(row, frm);
      });
      const openRow = grid.open_grid_row;
      if (openRow?.grid_form?.fields) {
        openRow.grid_form.fields.forEach((field) => {
          ensureJalaliPickerForControl(field, {
            frm,
            grid,
            grid_row: openRow,
          });
        });
      }
    });
  }

  function scheduleScanFormJalaliFields(frm) {
    if (!frm) return;
    const run = () => scanFormJalaliFields(frm);
    setTimeout(run, 0);
    scheduleJalaliGridDisplayPasses(frm);
    scheduleMainFormJalaliDisplayPasses(frm);
    if (frappe.after_ajax) {
      frappe.after_ajax(run);
    }
  }

  function bindJalaliGridFormEvents(frm) {
    if (!frm || frm._jalaliGridEventsBound) return;
    const $wrapper = getFormWrapper(frm);
    if (!$wrapper.length) return;
    frm._jalaliGridEventsBound = true;
    $wrapper.on("grid-row-render.jalali", function (e, grid_row) {
      scheduleScanFormJalaliFields(frm);
      setTimeout(() => {
        if (!shouldUseJalaliCalendar()) {
          normalizeGregorianDatetimesInForm(frm);
        } else {
          scanGridRowVisibleInputs(grid_row, frm);
          applyJalaliGridRowDisplay(grid_row);
        }
      }, 0);
      setTimeout(() => {
        if (shouldUseJalaliCalendar()) {
          applyJalaliGridRowDisplay(grid_row);
        }
      }, 100);
    });
    bindGridDisplayMutationObserver(frm);
    installGregorianGridPickerDebug();
    $wrapper.on(
      "focusin.jalali-grid-datetime",
      '.form-grid .frappe-control[data-fieldtype="Datetime"] input, .form-grid .frappe-control[data-fieldtype="Date"] input, .form-in-grid .frappe-control[data-fieldtype="Datetime"] input, .form-in-grid .frappe-control[data-fieldtype="Date"] input',
      function () {
        const $input = $(this);
        const $fc = $input.closest(".frappe-control");
        const fieldname = $fc.attr("data-fieldname");
        const fieldtype = $fc.attr("data-fieldtype");
        let grid_row = null;
        let grid = null;
        if (cur_frm) {
          for (const f of Object.values(cur_frm.fields_dict || {})) {
            if (!f?.grid?.grid_rows) continue;
            for (const r of f.grid.grid_rows) {
              if (gridRowContainsInput(r, $input)) {
                grid_row = r;
                grid = f.grid;
                break;
              }
            }
            if (grid_row) break;
          }
        }
        const control = grid_row?.on_grid_fields_dict?.[fieldname];
        if (!shouldUseJalaliCalendar()) {
          logGregorianGridPickerClick($input, control, { phase: "focusin" });
          return;
        }
        destroyAirDatepickerForInput($input);
        if (control) {
          ensureJalaliPickerForControl(control, { frm: cur_frm, grid: grid_row?.grid, grid_row });
        } else if (fieldname && fieldtype) {
          attachJalaliPickerToGridInput($input, fieldtype, fieldname, grid_row, cur_frm, null);
        }
      }
    );
    $(document).on("visibilitychange.jalali-grid-picker", function () {
      if (!document.hidden) {
        $(".jalali-datepicker").each(function () {
          const inst = $(this).data("jalaliDatepickerInstance");
          if (inst && inst.isOpen && inst._useBodyPopup) {
            inst.repositionPicker();
          }
        });
      }
    });
  }

  let makeControlJalaliPatched = false;

  function installMakeControlJalaliHook() {
    if (makeControlJalaliPatched || !frappe.ui.form.make_control) return;
    makeControlJalaliPatched = true;
    const origMakeControl = frappe.ui.form.make_control;
    frappe.ui.form.make_control = function (opts) {
      const field = origMakeControl.apply(this, arguments);
      if (
        field &&
        field.df &&
        (field.df.fieldtype === "Date" || field.df.fieldtype === "Datetime")
      ) {
        const ctx = {
          frm: opts.frm,
          grid: opts.grid,
          grid_row: opts.grid_row,
        };
        const applyMain = () => {
          ensureJalaliPickerForControl(field, ctx);
          if (!shouldUseJalaliCalendar()) {
            ensureGregorianNativeDatepicker(field);
          } else if (!opts.grid && !opts.grid_row) {
            applyJalaliControlDisplay(field);
          }
        };
        setTimeout(applyMain, 0);
        if (frappe.after_ajax) {
          frappe.after_ajax(applyMain);
        }
      }
      return field;
    };
  }

  function isUnsafeJalaliDisplayString(text) {
    if (text == null || text === "") {
      return false;
    }
    const s = String(text);
    return /NaN/i.test(s) || /Invalid\s*date/i.test(s);
  }

  function sanitizeGregorianNumericField(row, fieldname, fieldtype) {
    if (!row || row[fieldname] == null || row[fieldname] === "") {
      return;
    }
    const raw = row[fieldname];
    if (typeof raw === "number" && !Number.isNaN(raw)) {
      return;
    }
    let text = String(raw).trim();
    if (!text || /invalid\s*date|nan/i.test(text)) {
      row[fieldname] = fieldtype === "Int" ? 0 : 0;
      return;
    }
    text = text.replace(/[^0-9.\-+eE]/g, "");
    if (!text) {
      row[fieldname] = 0;
      return;
    }
    if (text.includes(",") && text.includes(".")) {
      text = text.replace(/,/g, "");
    } else if (text.includes(",") && !text.includes(".")) {
      const parts = text.split(",");
      if (parts.length === 2 && parts[1].length === 3) {
        text = parts[0] + parts[1];
      } else {
        text = text.replace(/,/g, "");
      }
    }
    let n = parseFloat(text);
    if (Number.isNaN(n)) {
      row[fieldname] = 0;
      return;
    }
    row[fieldname] = fieldtype === "Int" ? parseInt(n, 10) : n;
  }

  function coerceGridRowDatetimeField(grid_row, fieldname, fieldtype) {
    const U = getDateUtils();
    if (!U || !grid_row?.doc || !fieldname) {
      return null;
    }
    const raw = grid_row.doc[fieldname];
    if (raw == null || raw === "") {
      return null;
    }
    let iso =
      fieldtype === "Datetime"
        ? U.coerceToGregorianDateTime(raw) || U.normalizeModelDateTime(raw)
        : U.coerceToGregorianDateTime(raw) || U.normalizeModelDate(raw);
    // Date fields must stay YYYY-MM-DD. coerceToGregorianDateTime always returns a
    // datetime, so without slicing, a Date value oscillated against the native Date
    // picker (date ⇄ datetime) and froze the page on selection.
    if (fieldtype === "Date" && iso) {
      iso = String(iso).slice(0, 10);
    }
    if (iso && iso !== raw) {
      grid_row.doc[fieldname] = iso;
    }
    return iso || raw;
  }

  /** Coerce CSV/import child row values before grid render (setup_columns → frappe.format). */
  function normalizeImportedChildTableRows(frm, tableFieldname) {
    if (!frm?.doc || !tableFieldname) {
      return;
    }
    const rows = frm.doc[tableFieldname];
    if (!rows?.length) {
      return;
    }
    const tableDf = frm.get_docfield?.(tableFieldname);
    if (!tableDf?.options) {
      return;
    }
    const childMeta = frappe.get_meta(tableDf.options);
    if (!childMeta?.fields) {
      return;
    }
    const U = getDateUtils();
    if (!U) {
      return;
    }
    for (const row of rows) {
      for (const cdf of childMeta.fields) {
        const v = row[cdf.fieldname];
        if (v == null || v === "") {
          continue;
        }
        if (cdf.fieldtype === "Datetime") {
          const c =
            U.coerceToGregorianDateTime(v) || U.normalizeModelDateTime(v);
          if (c) {
            row[cdf.fieldname] = c;
          }
        } else if (cdf.fieldtype === "Date") {
          const c =
            U.coerceToGregorianDateTime(v) || U.normalizeModelDate(v);
          if (c) {
            row[cdf.fieldname] = String(c).slice(0, 10);
          }
        } else if (
          cdf.fieldtype === "Float" ||
          cdf.fieldtype === "Int" ||
          cdf.fieldtype === "Currency"
        ) {
          sanitizeGregorianNumericField(row, cdf.fieldname, cdf.fieldtype);
        }
      }
    }
  }

  function normalizeGregorianDatetimesInForm(frm) {
    const U = getDateUtils();
    if (!U || !frm?.doc || shouldUseJalaliCalendar()) {
      return;
    }
    const meta = frm.meta;
    if (!meta?.fields) {
      return;
    }
    for (const df of meta.fields) {
      if (df.fieldtype === "Datetime" && frm.doc[df.fieldname]) {
        const c =
          U.coerceToGregorianDateTime(frm.doc[df.fieldname]) ||
          U.normalizeModelDateTime(frm.doc[df.fieldname]);
        if (c) {
          frm.doc[df.fieldname] = c;
        }
      } else if (df.fieldtype === "Date" && frm.doc[df.fieldname]) {
        const c =
          U.coerceToGregorianDateTime(frm.doc[df.fieldname]) ||
          U.normalizeModelDate(frm.doc[df.fieldname]);
        if (c) {
          frm.doc[df.fieldname] = String(c).slice(0, 10);
        }
      } else if (df.fieldtype === "Table" && frm.doc[df.fieldname]?.length) {
        const childMeta = frappe.get_meta(df.options);
        if (!childMeta) {
          continue;
        }
        for (const row of frm.doc[df.fieldname]) {
          for (const cdf of childMeta.fields) {
            if (cdf.fieldtype === "Datetime" && row[cdf.fieldname]) {
              const c =
                U.coerceToGregorianDateTime(row[cdf.fieldname]) ||
                U.normalizeModelDateTime(row[cdf.fieldname]);
              if (c) {
                row[cdf.fieldname] = c;
              }
            } else if (cdf.fieldtype === "Date" && row[cdf.fieldname]) {
              const c =
                U.coerceToGregorianDateTime(row[cdf.fieldname]) ||
                U.normalizeModelDate(row[cdf.fieldname]);
              if (c) {
                row[cdf.fieldname] = String(c).slice(0, 10);
              }
            } else if (
              (cdf.fieldtype === "Float" ||
                cdf.fieldtype === "Int" ||
                cdf.fieldtype === "Currency") &&
              row[cdf.fieldname] != null &&
              row[cdf.fieldname] !== ""
            ) {
              sanitizeGregorianNumericField(row, cdf.fieldname, cdf.fieldtype);
            }
          }
        }
        const grid = frm.fields_dict[df.fieldname]?.grid;
        if (grid?.grid_rows) {
          for (const gr of grid.grid_rows) {
            for (const cdf of childMeta.fields) {
              if (cdf.fieldtype === "Datetime" || cdf.fieldtype === "Date") {
                coerceGridRowDatetimeField(gr, cdf.fieldname, cdf.fieldtype);
              }
            }
          }
        }
      }
    }
  }

  function isBadTimeOrDateString(value) {
    return /invalid\s*date|nan/i.test(String(value || ""));
  }

  function sanitizeTimeFieldsBeforeSave(frm) {
    if (!frm?.doc || !frm.meta?.fields || !shouldUseJalaliCalendar()) {
      return;
    }
    for (const df of frm.meta.fields) {
      if (df.fieldtype !== "Time") {
        continue;
      }
      const raw = frm.doc[df.fieldname];
      if (raw == null || raw === "") {
        continue;
      }
      if (!isBadTimeOrDateString(raw)) {
        continue;
      }
      const ctrl = frm.fields_dict[df.fieldname];
      let repaired = null;
      if (ctrl?.get_input_value) {
        repaired = ctrl.get_input_value();
      } else if (ctrl?.$input?.length) {
        repaired = ctrl.$input.val();
      }
      if (repaired && !isBadTimeOrDateString(repaired)) {
        frm.doc[df.fieldname] = repaired;
        continue;
      }
      if (frappe.datetime?.now_time) {
        frm.doc[df.fieldname] = frappe.datetime.now_time();
      }
    }
  }

  function syncDateFieldsFromControlsBeforeSave(frm) {
    if (!frm?.doc || !frm.meta?.fields || !shouldUseJalaliCalendar()) {
      return;
    }
    const U = getDateUtils();
    if (!U) {
      return;
    }
    for (const df of frm.meta.fields) {
      if (df.fieldtype !== "Date" && df.fieldtype !== "Datetime") {
        continue;
      }
      const ctrl = frm.fields_dict[df.fieldname];
      if (!ctrl || ctrl.grid) {
        continue;
      }
      let greg = null;
      if (ctrl.jalaliDatepicker && typeof ctrl.get_value === "function") {
        try {
          greg = ctrl.get_value();
        } catch (e) {
          greg = null;
        }
      } else if (frm.doc[df.fieldname]) {
        greg =
          df.fieldtype === "Datetime"
            ? U.coerceToGregorianDateTime(frm.doc[df.fieldname]) ||
              U.normalizeModelDateTime(frm.doc[df.fieldname])
            : U.coerceToGregorianDateTime(frm.doc[df.fieldname]) ||
              U.normalizeModelDate(frm.doc[df.fieldname]);
      }
      if (!greg || isBadTimeOrDateString(greg)) {
        continue;
      }
      frm.doc[df.fieldname] =
        df.fieldtype === "Datetime" ? greg : String(greg).slice(0, 10);
    }
  }

  function normalizeFormDatetimesBeforeSave(frm) {
    if (!shouldUseJalaliCalendar()) {
      normalizeGregorianDatetimesInForm(frm);
      return;
    }
    sanitizeTimeFieldsBeforeSave(frm);
    syncDateFieldsFromControlsBeforeSave(frm);
    const U = getDateUtils();
    if (!U || !frm?.doc) {
      return;
    }
    const meta = frm.meta;
    if (!meta?.fields) {
      return;
    }
    for (const df of meta.fields) {
      if (df.fieldtype === "Datetime" && frm.doc[df.fieldname]) {
        const c = U.normalizeModelDateTime(frm.doc[df.fieldname]);
        if (c) {
          frm.doc[df.fieldname] = c;
        }
      } else if (df.fieldtype === "Date" && frm.doc[df.fieldname]) {
        const c = U.coerceToGregorianDateTime(frm.doc[df.fieldname]);
        if (c) {
          frm.doc[df.fieldname] = c.slice(0, 10);
        }
      } else if (df.fieldtype === "Table" && frm.doc[df.fieldname]?.length) {
        const childMeta = frappe.get_meta(df.options);
        if (!childMeta) {
          continue;
        }
        for (const row of frm.doc[df.fieldname]) {
          for (const cdf of childMeta.fields) {
            if (cdf.fieldtype === "Datetime" && row[cdf.fieldname]) {
              const c = U.normalizeModelDateTime(row[cdf.fieldname]);
              if (c) {
                row[cdf.fieldname] = c;
              }
            } else if (cdf.fieldtype === "Date" && row[cdf.fieldname]) {
              const c = U.coerceToGregorianDateTime(row[cdf.fieldname]);
              if (c) {
                row[cdf.fieldname] = c.slice(0, 10);
              }
            }
          }
        }
      }
    }
  }

  let refreshFieldPreNormalizePatched = false;

  function installRefreshFieldPreNormalize() {
    if (refreshFieldPreNormalizePatched || !frappe.ui?.form?.Form?.prototype?.refresh_field) {
      return;
    }
    refreshFieldPreNormalizePatched = true;
    const orig = frappe.ui.form.Form.prototype.refresh_field;
    frappe.ui.form.Form.prototype.refresh_field = function (fieldname) {
      const df = this.get_docfield?.(fieldname);
      if (df?.fieldtype === "Table" && this?.doc) {
        normalizeImportedChildTableRows(this, fieldname);
      }
      const result = orig.apply(this, arguments);
      if (!shouldUseJalaliCalendar() && df?.fieldtype === "Table") {
        normalizeGregorianDatetimesInForm(this);
      }
      return result;
    };
  }

  function installFormGridJalaliHooks() {
    installMakeControlJalaliHook();
    installGridRowRefreshPatch();
    installRefreshFieldPreNormalize();
    frappe.ui.form.on("*", {
      refresh(frm) {
        if (!shouldUseJalaliCalendar()) {
          stripAllJalaliPickersInForm(frm);
          normalizeGregorianDatetimesInForm(frm);
          Object.values(frm.fields_dict || {}).forEach((f) => {
            if (f?.grid?.grid_rows) {
              f.grid.grid_rows.forEach((row) => {
                const dict = row.on_grid_fields_dict || {};
                Object.values(dict).forEach((gf) => {
                  if (
                    gf?.df &&
                    (gf.df.fieldtype === "Date" || gf.df.fieldtype === "Datetime")
                  ) {
                    ensureGregorianNativeDatepickerActive(gf);
                  }
                });
              });
            } else if (
              f?.df &&
              (f.df.fieldtype === "Date" || f.df.fieldtype === "Datetime")
            ) {
              ensureGregorianNativeDatepickerActive(f);
            }
          });
        }
        bindJalaliGridFormEvents(frm);
        if (shouldUseJalaliCalendar()) {
          scheduleScanFormJalaliFields(frm);
          scheduleJalaliGridDisplayPasses(frm);
          scheduleMainFormJalaliDisplayPasses(frm);
        }
      },
      before_save(frm) {
        normalizeFormDatetimesBeforeSave(frm);
      },
      after_save(frm) {
        if (!shouldUseJalaliCalendar()) {
          return;
        }
        const runDisplayOnly = () => refreshMainFormJalaliFields(frm);
        if (typeof requestAnimationFrame === "function") {
          requestAnimationFrame(runDisplayOnly);
        }
        setTimeout(runDisplayOnly, 0);
      },
    });
  }

  // Override Frappe's ControlDate and ControlDatetime
  function overrideControlsWhenReady() {
    const hasControls = frappe && frappe.ui && frappe.ui.form && 
                        frappe.ui.form.ControlDate && frappe.ui.form.ControlDatetime;
    if (!hasControls) {
      // Try again after a short delay
      setTimeout(overrideControlsWhenReady, 50);
      return;
    }

    // Check if already overridden
    if (frappe.ui.form.ControlDate.prototype.replaceWithJalaliDatepicker) {
      return;
    }

    const BaseControlDate = frappe.ui.form.ControlDate;
    const BaseControlDatetime = frappe.ui.form.ControlDatetime;

    class JalaliControlDate extends BaseControlDate {
      make_input() {
        const useJalali = shouldUseJalaliCalendar();
        this.display_calendar = getEffectiveCalendarMode();
        syncEffectiveCalendarFromBoot();
        if (calendarSettingsCache !== null) {
          if (calendarSettingsCache.calendar) {
            EFFECTIVE_CALENDAR = calendarSettingsCache.calendar;
            EFFECTIVE_CALENDAR.display_calendar = this.display_calendar;
          }
          if (calendarSettingsCache.firstDay !== undefined) {
            FIRST_DAY = calendarSettingsCache.firstDay;
          }
        } else {
          getCalendarSettings().then(() => {
            const wantJalali = shouldUseJalaliCalendar();
            this.display_calendar = getEffectiveCalendarMode();
            if (wantJalali && !this.jalaliDatepicker) {
              this.removeAirDatepickerInstances();
              this.setupInputWithoutAirDatepicker();
              this.replaceWithJalaliDatepicker();
            }
            if (wantJalali && !this.grid_row) {
              applyJalaliControlDisplay(this);
            } else if (!wantJalali && this.jalaliDatepicker) {
              stripJalaliPickerFromField(this);
              this.jalaliDatepicker = null;
            }
          });
        }

        if (useJalali) {
          if (!this.jalaliDatepicker) {
            this.setupInputWithoutAirDatepicker();
            this.replaceWithJalaliDatepicker();
          } else {
            this.setupInputWithoutAirDatepicker();
          }
          if (!this.grid_row) {
            applyJalaliControlDisplay(this);
          }
        } else {
          stripJalaliPickerFromField(this);
          if (this.df && this.df.fieldtype === "Datetime") {
            BaseControlDatetime.prototype.make_input.call(this);
          } else {
            BaseControlDate.prototype.make_input.call(this);
          }
        }
      }
      
      setupInputWithoutAirDatepicker() {
        // Find or create control-input-wrapper and control-input (like Frappe does)
        // First, ensure $wrapper exists - for query reports/page forms, it might not be set
        if (!this.$wrapper || !this.$wrapper.length) {
          // Try to find wrapper from form-group containing the input
          if (this.$input && this.$input.length) {
            this.$wrapper = this.$input.closest('.frappe-control, .form-group');
          } else if (this.df && this.df.fieldname) {
            // Try to find by fieldname
            this.$wrapper = $(`.frappe-control[data-fieldname="${this.df.fieldname}"], .form-group[data-fieldname="${this.df.fieldname}"]`);
          }
        }
        
        // If still no wrapper, try to find it from the input
        if ((!this.$wrapper || !this.$wrapper.length) && this.$input && this.$input.length) {
          this.$wrapper = this.$input.closest('.frappe-control, .form-group');
        }
        
        // Find existing input if not already set
        if (!this.$input || !this.$input.length) {
          if (this.$wrapper && this.$wrapper.length) {
            this.$input = this.$wrapper.find('input');
          } else if (this.df && this.df.fieldname) {
            // Try to find input by fieldname
            this.$input = $(`input[data-fieldname="${this.df.fieldname}"]`);
          }
        }
        
        if (!this.$input || !this.$input.length) {
          // Create new input only if wrapper exists
          if (this.$wrapper && this.$wrapper.length) {
            this.$input = $(`<input class="form-control" type="text">`);
          } else {
            return;
          }
        }
        
        // Ensure wrapper exists
        if (!this.$wrapper || !this.$wrapper.length) {
          this.$wrapper = this.$input.closest('.frappe-control, .form-group');
          if (!this.$wrapper || !this.$wrapper.length) {
            // Create a minimal wrapper if none exists
            this.$wrapper = this.$input.parent();
          }
        }
        
        // Make sure wrapper and input are visible (not hidden)
        if (this.$wrapper && this.$wrapper.length) {
          this.$wrapper.show();
        }
        if (this.$input && this.$input.length) {
          this.$input.show();
        }
        
        // For query reports/page forms, inputs are usually directly in the form-group
        // Don't try to wrap them in control-input-wrapper if they're already positioned correctly
        const isInPageForm = this.$wrapper.closest('.page-form, .query-report').length > 0;
        
        let $controlInputWrapper = this.$wrapper.find('.control-input-wrapper');
        let $controlInput = $controlInputWrapper.length ? $controlInputWrapper.find('.control-input') : null;
        
        // For page forms/query reports, if input is already positioned correctly, don't wrap it
        if (isInPageForm && (this.$input.parent().hasClass('form-group') || 
            this.$input.parent().is('.frappe-control, .form-group'))) {
          // Input is already in the right place, just ensure it's visible
          // Don't wrap it in control-input-wrapper
        } else {
          // Ensure control-input-wrapper exists
          if (!$controlInputWrapper.length) {
            $controlInputWrapper = $('<div class="control-input-wrapper"></div>');
            // Try to find form-group or append to wrapper
            const $formGroup = this.$wrapper.find('.form-group').first();
            if ($formGroup.length) {
              $formGroup.append($controlInputWrapper);
            } else {
              this.$wrapper.append($controlInputWrapper);
            }
          }
          
          // Ensure control-input exists
          if (!$controlInput || !$controlInput.length) {
            $controlInput = $('<div class="control-input"></div>');
            $controlInputWrapper.append($controlInput);
          }
          
          // Move input into control-input if it's not already there
          if (!this.$input.closest('.control-input').length) {
            this.$input.detach().appendTo($controlInput);
          }
        }
        
        // Set up basic attributes but prevent air-datepicker initialization
        if (this.df && this.df.fieldtype) {
          this.$input.attr('data-fieldtype', this.df.fieldtype);
        } else {
          this.$input.attr('data-fieldtype', this.$input.attr('data-fieldtype') || 'Date');
        }
        this.$input.removeClass('datepicker-input hasDatepicker');
        this.$input.removeAttr('data-date-format');
        this.$input.removeAttr('data-alt-input');
        this.$input.removeAttr('data-alt-format');
        this.$input.removeData('datepicker');
      }
      
      replaceWithJalaliDatepicker() {
        if (!shouldUseJalaliCalendar()) {
          return;
        }
        // If Jalali datepicker already exists, don't recreate it
        // This prevents calendar from closing when set_value is called
        if (this.jalaliDatepicker) {
          installJalaliDatepickerShim(this);
          return;
        }
        
        
        // Ensure input exists (should already be created by setupInputWithoutAirDatepicker)
        if (!this.$input || !this.$input.length) {
          this.setupInputWithoutAirDatepicker();
        }
        
        // Make sure no air-datepicker exists (cleanup just in case)
        this.removeAirDatepickerInstances();
        
        // Ensure no air-datepicker classes or attributes
        this.$input.removeAttr('data-date-format');
        this.$input.removeAttr('data-alt-input');
        this.$input.removeAttr('data-alt-format');
        this.$input.removeClass('datepicker-input hasDatepicker');
        this.$input.removeData('datepicker');
        
        // Make input editable for better UX
        this.$input.attr('readonly', false);
        
        // Don't override any styling - let Frappe handle all layout, spacing, and alignment
        
        // Remove any existing air-datepicker instances BEFORE creating Jalali datepicker
        this.removeAirDatepickerInstances();
        
        // Check if this is a datetime field
        const isDateTime = this.df && this.df.fieldtype === "Datetime";
        
        // Mark input as having Jalali datepicker BEFORE creating it
        this.$input.data('hasJalaliDatepicker', true);
        this.$input.attr('data-has-jalali-datepicker', 'true');
        
        // Create Jalali datepicker (with datetime support if needed)
        this.jalaliDatepicker = new JalaliDatepicker(this.$input[0], this, isDateTime);
        
        // Store reference on input for easy access
        this.$input.data('jalaliDatepickerInstance', this.jalaliDatepicker);

        installJalaliDatepickerShim(this);
        if (this.df && this.df.max_date) {
          try {
            this._jalaliMaxDate = frappe.datetime.str_to_obj(this.df.max_date);
          } catch (e) {
            /* ignore */
          }
        }
        if (this.df && this.df.min_date) {
          try {
            this._jalaliMinDate = frappe.datetime.str_to_obj(this.df.min_date);
          } catch (e) {
            /* ignore */
          }
        }
        
        // Prevent Frappe from creating air-datepicker on this input
        this.$input.removeClass('datepicker-input hasDatepicker');
        this.$input.off('.datepicker');
        
        // Fix alignment after datepicker creation
        this.fixFieldAlignment();
        
      }
      
      fixFieldAlignment() {
        // Don't override spacing - let Frappe settings control margins and paddings
        // Only ensure essential positioning for datepicker to work correctly
      }

      set_disp_area(value) {
        if (shouldUseJalaliCalendar() && !this.grid_row && this.df) {
          const ft = this.df.fieldtype;
          if ((ft === "Date" || ft === "Datetime") && value != null && value !== "") {
            const raw = getControlModelValue(this) ?? value;
            const display = modelValueToDisplayInput(raw, ft === "Datetime");
            if (display) {
              value = display;
            }
          }
        }
        return frappe.ui.form.ControlData.prototype.set_disp_area.call(this, value);
      }
      
      removeAirDatepickerInstances() {
        // Remove any existing air-datepicker instances
        if (this.datepicker) {
          try {
            this.datepicker.destroy();
            this.datepicker = null;
          } catch(e) {
          }
        }
        
        if (this.$input && this.$input.length) {
          destroyAirDatepickerForInput(this.$input);
        }
        $('.datepicker-input').removeClass('datepicker-input');
        $('.hasDatepicker').removeClass('hasDatepicker');
        
        // Remove any datepicker icons or buttons
        $('.datepicker-icon').remove();
        $('.datepicker-btn').remove();
        
        // Clear any datepicker-related data
        if (this.$input && this.$input.length) {
          this.$input.removeData('datepicker');
        }
        
        // Remove any air-datepicker event listeners
        if (this.$input && this.$input.length) {
          this.$input.off('.datepicker');
        }
        
      }

      set_formatted_input(value) {
        pcLoopGuard("ControlDate.set_formatted_input", { field: this.df?.fieldname });
        try {
          // Check cache first
          const useJalali = shouldUseJalaliCalendar();

          if (!useJalali) {
            if (this.jalaliDatepicker) {
              stripJalaliPickerFromField(this);
              this.jalaliDatepicker = null;
            }
            pcLoopTrace("JalaliControlDate.set_formatted_input(Gregorian)", {
              field: this.df?.fieldname,
              value,
            });
            const forBase = gregorianInputValueForBase(this, value);
            const BaseSet =
              this.df?.fieldtype === "Datetime"
                ? BaseControlDatetime.prototype.set_formatted_input
                : BaseControlDate.prototype.set_formatted_input;
            return BaseSet.call(this, forBase);
          }

          if (!value) {
            frappe.ui.form.ControlData.prototype.set_formatted_input.call(this, "");
            return;
          }

          const isDateTimeField = this.df && this.df.fieldtype === "Datetime";
          if (this.grid_row && this.df?.fieldname) {
            coerceGridRowDatetimeField(
              this.grid_row,
              this.df.fieldname,
              this.df.fieldtype
            );
          }
          const modelVal = getControlModelValue(this) ?? value;
          const display = modelValueToDisplayInput(modelVal, isDateTimeField);
          jalaliDateLog("set_formatted_input displayed value", display);
          frappe.ui.form.ControlData.prototype.set_formatted_input.call(this, display || "");
          applyJalaliControlDisplay(this);
          return;
        } catch (e) {
          return super.set_formatted_input(value);
        }
      }

      format_for_input(value) {
        pcLoopGuard("ControlDate.format_for_input", { field: this.df?.fieldname });
        if (!shouldUseJalaliCalendar()) {
          if (this.jalaliDatepicker) {
            stripJalaliPickerFromField(this);
            this.jalaliDatepicker = null;
          }
          // Passive: never mutate the model from a formatting call. The earlier coerce
          // here rewrote Date values into datetime strings, which never stabilized
          // against the native picker and looped on selection.
          return BaseControlDate.prototype.format_for_input.call(this, value);
        }
        if (!this.grid_row) {
          const isDateTimeField = this.df && this.df.fieldtype === "Datetime";
          return modelValueToDisplayInput(value, isDateTimeField);
        }
        if (!this.jalaliDatepicker) {
          return BaseControlDate.prototype.format_for_input.call(this, value);
        }
        const isDateTimeField = this.df && this.df.fieldtype === "Datetime";
        return modelValueToDisplayInput(value, isDateTimeField);
      }

      set_value(value) {
        pcLoopGuard("ControlDate.set_value", { field: this.df?.fieldname });
        if (this.jalaliDatepicker && value != null && value !== "") {
          const isDateTime = this.df && this.df.fieldtype === "Datetime";
          const U = getDateUtils();
          const greg = isDateTime
            ? U?.normalizeModelDateTime(value)
            : U?.normalizeModelDate(value);
          const cur = this.get_model_value?.();
          if (
            greg &&
            modelValuesEqualForField(cur, greg, this.df?.fieldtype || "Date")
          ) {
            setControlInputDisplayOnly(
              this,
              modelValueToDisplayInput(greg, isDateTime)
            );
            return Promise.resolve();
          }
          jalaliDateLog("set_value", { in: value, gregorian: greg });
          const result = BaseControlDate.prototype.set_value.call(this, greg);
          if (this.$input && greg) {
            setControlInputDisplayOnly(
              this,
              modelValueToDisplayInput(greg, isDateTime)
            );
          }
          return result;
        }
        return BaseControlDate.prototype.set_value.call(this, value);
      }

      get_value() {
        if (this.jalaliDatepicker && this.$input && this.$input.length) {
          const raw = this.$input.val();
          if (raw) {
            const greg = getDateUtils().normalizeModelDate(String(raw).trim());
            jalaliDateLog("get_value", { input: raw, gregorian: greg });
            return greg;
          }
        }
        return BaseControlDate.prototype.get_value.call(this);
      }

      refresh_input() {
        pcLoopGuard("ControlDate.refresh_input", { field: this.df?.fieldname });
        if (shouldUseJalaliCalendar()) {
          if (this.$input?.length) {
            destroyAirDatepickerForInput(this.$input);
          }
          if (!this.jalaliDatepicker) {
            this.setupInputWithoutAirDatepicker();
            this.replaceWithJalaliDatepicker();
          }
        }
        const result =
          BaseControlDate.prototype.refresh_input &&
          BaseControlDate.prototype.refresh_input.call(this);
        if (shouldUseJalaliCalendar()) {
          applyJalaliControlDisplay(this);
        } else {
          // Passive: Frappe's own refresh_input/make_input owns the native Air
          // Datepicker. Only remove a stale Jalali picker when switching modes —
          // never rebuild the native one here (that re-fired change → Grid.set_value
          // → refresh_field → refresh_input and froze the page). Re-attach the cheap,
          // loop-safe onShow hook so the picker view/title syncs to the model when the
          // user opens it (datepicker may not have existed yet at make_input time).
          cleanupStaleJalaliInGregorian(this);
          hookGregorianPickerOnShow(this);
        }
        return result;
      }

      parse(value) {
        if (this.jalaliDatepicker && value) {
          return BaseControlDate.prototype.parse.call(this, getDateUtils().normalizeModelDate(value));
        }
        return BaseControlDate.prototype.parse.call(this, value);
      }
    }

    // Override ControlDate
    frappe.ui.form.ControlDate = JalaliControlDate;
    
    // Override ControlDatetime - it should inherit from JalaliControlDate
    // But we need to make sure datetime-specific methods are preserved
    class JalaliControlDatetime extends JalaliControlDate {
      make_input() {
        super.make_input();
        if (!shouldUseJalaliCalendar()) {
          removeJalaliFromField(this);
          ensureGregorianNativeDatepickerActive(this);
          return;
        }
        if (!this.jalaliDatepicker) {
          this.setupInputWithoutAirDatepicker();
          this.replaceWithJalaliDatepicker();
        }
      }

      set_date_options() {
        if (this.jalaliDatepicker) {
          return;
        }
        return BaseControlDatetime.prototype.set_date_options.call(this);
      }

      get_now_date() {
        return frappe.datetime.now_datetime(true);
      }

      format_for_input(value) {
        pcLoopGuard("ControlDatetime.format_for_input", { field: this.df?.fieldname });
        if (!shouldUseJalaliCalendar()) {
          if (this.jalaliDatepicker) {
            stripJalaliPickerFromField(this);
            this.jalaliDatepicker = null;
          }
          // Passive: do not mutate the model from a formatting call (see ControlDate).
          return BaseControlDatetime.prototype.format_for_input.call(this, value);
        }
        if (!this.grid_row) {
          return modelValueToDisplayInput(value, true);
        }
        if (!this.jalaliDatepicker) {
          return BaseControlDatetime.prototype.format_for_input.call(this, value);
        }
        return modelValueToDisplayInput(value, true);
      }

      refresh_input() {
        pcLoopGuard("ControlDatetime.refresh_input", { field: this.df?.fieldname });
        if (!shouldUseJalaliCalendar()) {
          cleanupStaleJalaliInGregorian(this);
          const result =
            BaseControlDatetime.prototype.refresh_input &&
            BaseControlDatetime.prototype.refresh_input.call(this);
          // Loop-safe: only wraps the picker's onShow callback (fires on user open),
          // never rebuilds the picker or writes the model.
          hookGregorianPickerOnShow(this);
          return result;
        }
        if (shouldUseJalaliCalendar()) {
          if (this.$input?.length) {
            destroyAirDatepickerForInput(this.$input);
          }
          if (!this.jalaliDatepicker) {
            this.setupInputWithoutAirDatepicker();
            this.replaceWithJalaliDatepicker();
          }
        }
        const result =
          BaseControlDate.prototype.refresh_input &&
          BaseControlDate.prototype.refresh_input.call(this);
        if (shouldUseJalaliCalendar()) {
          applyJalaliControlDisplay(this);
        }
        return result;
      }

      set_formatted_input(value) {
        pcLoopGuard("ControlDatetime.set_formatted_input", { field: this.df?.fieldname });
        try {
          const useJalali = shouldUseJalaliCalendar();

          if (!useJalali) {
            if (this.jalaliDatepicker) {
              stripJalaliPickerFromField(this);
              this.jalaliDatepicker = null;
            }
            pcLoopTrace("JalaliControlDatetime.set_formatted_input(Gregorian)", {
              field: this.df?.fieldname,
              value,
            });
            const forBase = gregorianInputValueForBase(this, value);
            return BaseControlDatetime.prototype.set_formatted_input.call(this, forBase);
          }

          if (!value) {
            frappe.ui.form.ControlData.prototype.set_formatted_input.call(this, "");
            return;
          }

          if (this.grid_row && this.df?.fieldname) {
            coerceGridRowDatetimeField(
              this.grid_row,
              this.df.fieldname,
              this.df.fieldtype
            );
          }
          const modelVal = getControlModelValue(this) ?? value;
          const display = modelValueToDisplayInput(modelVal, true);
          const safeDisplay =
            display && !isUnsafeJalaliDisplayString(display) ? display : "";
          frappe.ui.form.ControlData.prototype.set_formatted_input.call(
            this,
            safeDisplay
          );
          applyJalaliControlDisplay(this);
        } catch (e) {
          return BaseControlDatetime.prototype.set_formatted_input.call(this, value);
        }
      }

      set_value(value) {
        pcLoopGuard("ControlDatetime.set_value", { field: this.df?.fieldname });
        if (this.jalaliDatepicker && value != null && value !== "") {
          const greg = getDateUtils().normalizeModelDateTime(value);
          const cur = this.get_model_value?.();
          if (
            greg &&
            modelValuesEqualForField(cur, greg, this.df?.fieldtype || "Datetime")
          ) {
            setControlInputDisplayOnly(this, modelValueToDisplayInput(greg, true));
            return Promise.resolve();
          }
          jalaliDatetimeLog("set_value", { in: value, gregorian: greg });
          const result = BaseControlDatetime.prototype.set_value.call(this, greg);
          if (this.$input && greg) {
            setControlInputDisplayOnly(this, modelValueToDisplayInput(greg, true));
          }
          return result;
        }
        const result = BaseControlDatetime.prototype.set_value.call(this, value);
        if (shouldUseJalaliCalendar() && !this.grid_row) {
          applyJalaliControlDisplay(this);
        }
        return result;
      }

      get_value() {
        if (!this.jalaliDatepicker) {
          return BaseControlDatetime.prototype.get_value.call(this);
        }
        if (this.$input && this.$input.length) {
          const raw = this.$input.val();
          if (raw) {
            const greg = getDateUtils().normalizeModelDateTime(String(raw).trim());
            jalaliDatetimeLog("get_value", { input: raw, gregorian: greg });
            return greg;
          }
        }
        return BaseControlDatetime.prototype.get_value.call(this);
      }

      parse(value) {
        if (this.jalaliDatepicker && value) {
          return BaseControlDatetime.prototype.parse.call(
            this,
            getDateUtils().normalizeModelDateTime(value)
          );
        }
        return BaseControlDatetime.prototype.parse.call(this, value);
      }
    }
    
    frappe.ui.form.ControlDatetime = JalaliControlDatetime;

    installFormGridJalaliHooks();
  }

  // Function to remove all existing air-datepicker instances from the page
  function removeAllAirDatepickerInstances() {
    // Only target inputs that don't have jalali-datepicker
    const $airDatepickerInputs = $('input.datepicker-input, input.hasDatepicker').filter(function() {
      // Skip inputs that already have jalali-datepicker instance
      const $input = $(this);
      if (isTimeFieldInput($input)) {
        return false;
      }
      // Check multiple ways to identify Jalali datepicker
      const hasJalaliAttr = $input.attr('data-has-jalali-datepicker') === 'true';
      const hasJalaliData = $input.data('hasJalaliDatepicker') === true;
      const jalaliInstance = $input.siblings('.jalali-datepicker').data('jalaliDatepickerInstance');
      const jalaliDataInstance = $input.data('jalaliDatepickerInstance');
      
      // Skip if any Jalali datepicker indicator is present
      return !hasJalaliAttr && !hasJalaliData && !jalaliInstance && !jalaliDataInstance;
    });
    
    // Only proceed if there are actual air-datepicker instances to remove
    const hasAirDatepicker = $('.air-datepicker').length > 0 || $airDatepickerInputs.length > 0;
    
    if (!hasAirDatepicker) {
      // No air-datepicker instances found, skip removal to avoid unnecessary processing
      return;
    }
    
    // Remove all air-datepicker calendars (but not jalali-datepicker)
    $('.air-datepicker').not('.jalali-datepicker').remove();
    
    // Remove air-datepicker classes and attributes from filtered inputs only
    $airDatepickerInputs.each(function() {
      const $input = $(this);
      // Double check this input doesn't have jalali-datepicker
      const hasJalaliAttr = $input.attr('data-has-jalali-datepicker') === 'true';
      const hasJalaliData = $input.data('hasJalaliDatepicker') === true;
      const jalaliInstance = $input.siblings('.jalali-datepicker').data('jalaliDatepickerInstance');
      const jalaliDataInstance = $input.data('jalaliDatepickerInstance');
      
      if (hasJalaliAttr || hasJalaliData || jalaliInstance || jalaliDataInstance) {
        return; // Skip this input
      }
      
      $input.removeClass('datepicker-input hasDatepicker');
      $input.removeAttr('data-date-format');
      $input.removeAttr('data-alt-input');
      $input.removeAttr('data-alt-format');
      $input.removeData('datepicker');
      
      // Remove event listeners
      $input.off('.datepicker');
    });
    
    // Remove any datepicker icons or buttons (but not jalali datepicker buttons)
    $('.datepicker-icon, .datepicker-btn').not('.jalali-datepicker .today-btn, .jalali-datepicker .now-btn').remove();
    
    // Remove any air-datepicker instances from global scope
    if (window.Datepicker && window.Datepicker.instances) {
      try {
        // Try to destroy all instances that are not our Jalali datepickers
        Object.keys(window.Datepicker.instances).forEach(key => {
          try {
            const instance = window.Datepicker.instances[key];
            // Only destroy if it's a real air-datepicker instance
            // Check if the input has jalali-datepicker sibling
            if (instance && instance.el) {
              const $el = $(instance.el);
              if (isTimeFieldInput($el)) {
                return;
              }
              const hasJalaliSibling = $el.siblings('.jalali-datepicker').length > 0;
              if (!hasJalaliSibling && !$el.data('jalaliDatepickerInstance')) {
                instance.destroy();
              }
            }
          } catch(e) {
            // Silently ignore errors for individual instances
          }
        });
      } catch(e) {
        // Silently ignore errors accessing instances
      }
    }
  }
  
  // Remove existing air-datepicker instances immediately
  removeAllAirDatepickerInstances();
  
  // Also remove them periodically to catch any dynamically created ones
  // Use longer interval and only remove if needed
  setInterval(function() {
    // Only run cleanup if there are actual air-datepicker instances
    if ($('.air-datepicker').not('.jalali-datepicker').length > 0 || 
        $('input.datepicker-input, input.hasDatepicker').filter(function() {
          const $input = $(this);
          // Check all ways to identify Jalali datepicker
          const hasJalaliAttr = $input.attr('data-has-jalali-datepicker') === 'true';
          const hasJalaliData = $input.data('hasJalaliDatepicker') === true;
          const jalaliSiblingInstance = $input.siblings('.jalali-datepicker').data('jalaliDatepickerInstance');
          const jalaliDataInstance = $input.data('jalaliDatepickerInstance');
          
          // Return true only if NO Jalali datepicker indicators are present
          return !hasJalaliAttr && !hasJalaliData && !jalaliSiblingInstance && !jalaliDataInstance;
        }).length > 0) {
      removeAllAirDatepickerInstances();
    }
  }, 2000); // Changed from 1000ms to 2000ms to be less aggressive

  // Pre-normalize child tables before grid render (CSV import); do not wait for control override.
  installRefreshFieldPreNormalize();

  // Start overriding
  overrideControlsWhenReady();

  // Function to handle date fields in query reports and page forms
  async function initializeDateFieldsInPageForms() {
    try {
      const settings = await getCalendarSettings();
      if (!settings.enabled || !shouldUseJalaliCalendar()) {
        return;
      }

      // Find all date inputs that don't have Jalali datepicker yet
      const $dateInputs = $('input[data-fieldtype="Date"], input[data-fieldtype="Datetime"]').filter(function() {
        const $input = $(this);
        // Skip if already has Jalali datepicker
        const hasJalaliAttr = $input.attr('data-has-jalali-datepicker') === 'true';
        const hasJalaliData = $input.data('hasJalaliDatepicker') === true;
        const jalaliInstance = $input.siblings('.jalali-datepicker').data('jalaliDatepickerInstance');
        const jalaliDataInstance = $input.data('jalaliDatepickerInstance');
        
        // Skip if already has Jalali datepicker
        if (hasJalaliAttr || hasJalaliData || jalaliInstance || jalaliDataInstance) {
          return false;
        }
        
        // Check if this input is inside a page-form (query reports) or standalone
        // We want to handle these inputs
        const $frappeControl = $input.closest('.frappe-control');
        if ($frappeControl.length > 0) {
          // Check if this is inside a page-form (query reports)
          const $pageForm = $input.closest('.page-form, .query-report');
          if ($pageForm.length > 0) {
            // This is in a query report, we should initialize it
            return true;
          }
          
          // Check if this is clearly part of a regular form (has .form-section as ancestor but not .page-form)
          const $formSection = $input.closest('.form-section, .form-layout');
          if ($formSection.length > 0 && $pageForm.length === 0) {
            // This is likely a form field, let make_input handle it
            return false;
          }
        }
        
        return true;
      });

      if ($dateInputs.length === 0) {
        return;
      }


      $dateInputs.each(function() {
        const $input = $(this);
        const fieldtype = $input.attr('data-fieldtype') || 'Date';
        const fieldname = $input.attr('data-fieldname') || '';
        
        // Make sure input and its wrapper are visible
        const $wrapper = $input.closest('.frappe-control, .form-group');
        if ($wrapper.length) {
          $wrapper.show();
        }
        $input.show();
        
        // Skip if already has Jalali datepicker
        if ($input.attr('data-has-jalali-datepicker') === 'true' || 
            $input.data('hasJalaliDatepicker') === true ||
            $input.siblings('.jalali-datepicker').length > 0) {
          return;
        }

        try {
          // Create a minimal control object for compatibility
          const fakeControl = {
            df: {
              fieldtype: fieldtype,
              fieldname: fieldname
            },
            $wrapper: $wrapper.length ? $wrapper : $input.parent(),
            $input: $input,
            set_value: function(value) {
              const U = getDateUtils();
              let v = value;
              if (U && fieldtype === "Datetime" && value) {
                v = U.normalizeModelDateTime(value);
              } else if (U && fieldtype === "Date" && value) {
                v = U.normalizeModelDate(value);
              }
              if (v != null && v !== "") {
                $input.data("jalali-model-value", v);
              } else {
                $input.removeData("jalali-model-value");
              }
              $input.val(
                fieldtype === "Datetime" && U
                  ? modelValueToDisplayInput(v, true)
                  : fieldtype === "Date" && U
                    ? modelValueToDisplayInput(v, false)
                    : v
              ).trigger("change");
            },
            get_value: function() {
              const stored = $input.data("jalali-model-value");
              if (stored) {
                return stored;
              }
              const U = getDateUtils();
              const raw = $input.val();
              if (!raw || !U) {
                return raw;
              }
              if (fieldtype === "Datetime") {
                return U.normalizeModelDateTime(String(raw).trim());
              }
              if (fieldtype === "Date") {
                return U.normalizeModelDate(String(raw).trim());
              }
              return raw;
            }
          };

          // Create Jalali datepicker
          const isDateTime = fieldtype === "Datetime";
          const jalaliDatepicker = new JalaliDatepicker($input[0], fakeControl, isDateTime);
          
          // Store references
          $input.data('hasJalaliDatepicker', true);
          $input.attr('data-has-jalali-datepicker', 'true');
          $input.data('jalaliDatepickerInstance', jalaliDatepicker);
          
          // Convert existing value if present
          const currentValue = $input.val();
          if (currentValue) {
            const display = modelValueToDisplayInput(currentValue, isDateTime);
            if (display) {
              $input.val(display);
              jalaliDatepicker.updateDisplay();
            }
          }
          
        } catch(e) {
        }
      });
    } catch(e) {
    }
  }

  // Initialize date fields in page forms/query reports
  // Run after a delay to ensure DOM is ready
  setTimeout(function() {
    initializeDateFieldsInPageForms();
  }, 500);

  // Also run when page content changes (for dynamic content)
  $(document).on('frappe.breadcrumbs.loaded frappe.route.loaded page-change', function() {
    setTimeout(function() {
      initializeDateFieldsInPageForms();
    }, 300);
  });

  // Also run periodically to catch dynamically added fields
  setInterval(function() {
    initializeDateFieldsInPageForms();
  }, 3000);

  // Override Fiscal Year defaults to Jalali year boundaries when enabled
  try {
    frappe.ui.form.on('Fiscal Year', {
      onload: async function(frm) {
        try {
          if (!frm.doc.__islocal) return; // only for new docs
          
          // Get calendar settings
          const settings = await getCalendarSettings();
          if (!settings.enabled) return;
          if (!shouldUseJalaliCalendar()) return;

          // If user already set a start date, don't override
          if (frm.doc.year_start_date) return;

          // Determine current Jalali year from today
          const todayG = new Date();
          const todayJ = gToJ(todayG);

          const jy = todayJ.jy;
          // Start: jy-01-01 (Jalali) => Gregorian
          const startG = jToG(jy, 1, 1);
          const nextStartG = jToG(jy + 1, 1, 1);
          if (!startG || !nextStartG) return;
          const startStr = `${startG.gy}-${String(startG.gm).padStart(2,'0')}-${String(startG.gd).padStart(2,'0')}`;
          const nextStartDate = new Date(nextStartG.gy, nextStartG.gm - 1, nextStartG.gd);
          const endDate = new Date(nextStartDate.getTime() - 24 * 60 * 60 * 1000);
          const endStr = `${endDate.getFullYear()}-${String(endDate.getMonth()+1).padStart(2,'0')}-${String(endDate.getDate()).padStart(2,'0')}`;

          frm.set_value('year_start_date', startStr);
          // If not short year, Frappe's handler sets end automatically; force set to Jalali end regardless
          frm.set_value('year_end_date', endStr);
        } catch (e) {
        }
      }
    });
  } catch (e) {
  }

  try {
    frappe.ui.form.on("User", {
      calendar_preference(frm) {
        if (
          frm.doc.name !== frappe.session.user ||
          frm.doc.calendar_preference === undefined
        ) {
          return;
        }
        const rt = frappe.persian_calendar?.runtime;
        if (rt) {
          rt.invalidateCalendarSettingsCache();
          rt.updateBootFromUserCalendarPreference(frm.doc.calendar_preference);
        }
        calendarSettingsCache = null;
      },
      after_save: function (frm) {
        if (
          frm.doc.calendar_preference === undefined ||
          frm.doc.name !== frappe.session.user
        ) {
          return;
        }
        const rt = frappe.persian_calendar?.runtime;
        if (rt) {
          rt.invalidateCalendarSettingsCache();
          rt.updateBootFromUserCalendarPreference(frm.doc.calendar_preference);
        }
        calendarSettingsCache = null;
        calendarSettingsPromise = null;
        if (rt?.fetchCalendarSettings) {
          rt.fetchCalendarSettings().then(function () {
            teardownGregorianCalendarUI();
            if (cur_frm) {
              cur_frm.refresh_fields();
            }
          });
        } else {
          teardownGregorianCalendarUI();
          if (cur_frm) {
            cur_frm.refresh_fields();
          }
        }
      },
    });
  } catch (e) {
    /* ignore */
  }

})();