/**
 * Single source of truth for active Date/Datetime calendar mode (Gregorian vs Jalali).
 * Reads frappe.boot.persian_calendar synchronously; refreshes via API when invalidated.
 */
(function () {
  if (typeof frappe === "undefined") {
    return;
  }
  frappe.provide("frappe.persian_calendar");
  frappe.persian_calendar = frappe.persian_calendar || {};

  let settingsCache = null;
  let settingsPromise = null;

  function readBoot() {
    return frappe.boot?.persian_calendar || null;
  }

  /** @returns {"Jalali"|"Gregorian"} */
  function normalizeCalendarMode(mode) {
    if (mode === "Jalali" || mode === "Persian") {
      return "Jalali";
    }
    return "Gregorian";
  }

  function normalizeDefaultCalendar(defaultCalendar) {
    return normalizeCalendarMode(defaultCalendar);
  }

  function resolveDisplayCalendar(userPref, defaultCalendar, jalaliEnabled) {
    if (!jalaliEnabled) {
      return "Gregorian";
    }
    const pref = String(userPref || "System Default").trim();
    if (pref === "Gregorian") {
      return "Gregorian";
    }
    if (pref === "Jalali" || pref === "Persian") {
      return "Jalali";
    }
    if (pref === "System Default") {
      return normalizeDefaultCalendar(defaultCalendar);
    }
    return "Gregorian";
  }

  /** Canonical effective mode: only "Jalali" or "Gregorian". */
  function getEffectiveCalendarModeSync() {
    const boot = readBoot();
    if (!boot?.enabled) {
      return "Gregorian";
    }
    const mode = resolveDisplayCalendar(
      boot.calendar_preference,
      boot.default_calendar,
      boot.enabled
    );
    const normalized = normalizeCalendarMode(mode);
    boot.display_calendar = normalized;
    return normalized;
  }

  function getCalendarPreferenceDebugSync() {
    const boot = readBoot() || {};
    const effective = getEffectiveCalendarModeSync();
    return {
      enabled: !!boot.enabled,
      calendar_preference: boot.calendar_preference || "System Default",
      default_calendar: boot.default_calendar || null,
      display_calendar: boot.display_calendar || effective,
      effective_calendar_mode: effective,
      shouldUseJalaliCalendar: shouldUseJalaliCalendarSync(),
    };
  }

  function syncBootDisplayCalendar() {
    const boot = readBoot();
    if (!boot) {
      return;
    }
    boot.display_calendar = normalizeCalendarMode(
      resolveDisplayCalendar(
        boot.calendar_preference,
        boot.default_calendar,
        boot.enabled
      )
    );
  }

  function getActiveCalendarPreferenceSync() {
    const boot = readBoot();
    if (boot) {
      const display = getEffectiveCalendarModeSync();
      return {
        enabled: !!boot.enabled,
        calendar_preference: boot.calendar_preference || "System Default",
        default_calendar: boot.default_calendar || "Jalali",
        display_calendar: display,
        week_start: boot.week_start ?? 6,
        week_end: boot.week_end ?? 5,
      };
    }
    if (settingsCache) {
      return {
        enabled: !!settingsCache.enabled,
        calendar_preference: settingsCache.calendar_preference || "System Default",
        default_calendar: settingsCache.default_calendar || "Jalali",
        display_calendar:
          settingsCache.calendar?.display_calendar || "Gregorian",
        week_start: settingsCache.firstDay ?? settingsCache.calendar?.week_start ?? 6,
        week_end: settingsCache.calendar?.week_end ?? 5,
      };
    }
    return {
      enabled: false,
      calendar_preference: "System Default",
      default_calendar: "Jalali",
      display_calendar: "Gregorian",
      week_start: 6,
      week_end: 5,
    };
  }

  function shouldUseJalaliCalendarSync() {
    const boot = readBoot();
    if (!boot?.enabled) {
      return false;
    }
    return getEffectiveCalendarModeSync() === "Jalali";
  }

  function shouldConvertToJalaliSync() {
    return shouldUseJalaliCalendarSync();
  }

  function invalidateCalendarSettingsCache() {
    settingsCache = null;
    settingsPromise = null;
  }

  function updateBootFromUserCalendarPreference(calendarPreference) {
    const boot = readBoot();
    if (!boot) {
      return;
    }
    boot.calendar_preference = calendarPreference || "System Default";
    syncBootDisplayCalendar();
    invalidateCalendarSettingsCache();
  }

  function configureSystemDefaultCalendarSync(defaultCalendar) {
    const boot = readBoot();
    if (!boot) {
      return;
    }
    boot.calendar_preference = "System Default";
    if (defaultCalendar) {
      boot.default_calendar = normalizeDefaultCalendar(defaultCalendar);
    }
    syncBootDisplayCalendar();
    invalidateCalendarSettingsCache();
  }

  function applyFetchedSettings(enabled, calendar, firstDay, defaultCalendar) {
    const boot = readBoot();
    if (boot && calendar) {
      boot.enabled = !!enabled;
      boot.week_start = calendar.week_start;
      boot.week_end = calendar.week_end;
      if (defaultCalendar) {
        boot.default_calendar = defaultCalendar;
      }
      syncBootDisplayCalendar();
    }
    settingsCache = {
      enabled: !!enabled,
      calendar,
      firstDay,
      default_calendar: defaultCalendar,
    };
  }

  async function fetchCalendarSettings() {
    if (settingsCache !== null) {
      return settingsCache;
    }
    if (settingsPromise) {
      return settingsPromise;
    }
    settingsPromise = (async () => {
      try {
        const enabledRes = await frappe.call({
          method: "persian_calendar.jalali_support.api.is_jalali_enabled",
        });
        const enabled = !!(enabledRes && enabledRes.message);
        if (!enabled) {
          applyFetchedSettings(false, { display_calendar: "Gregorian" }, 0, "Jalali");
          return settingsCache;
        }
        const r = await frappe.call({
          method: "persian_calendar.jalali_support.api.get_effective_calendar",
        });
        const calendar = (r && r.message) || { display_calendar: "Gregorian" };
        const firstDay = calendar.week_start ?? 6;
        const boot = readBoot();
        applyFetchedSettings(
          enabled,
          calendar,
          firstDay,
          boot?.default_calendar || "Jalali"
        );
        return settingsCache;
      } catch (e) {
        applyFetchedSettings(false, { display_calendar: "Gregorian" }, 0, "Jalali");
        return settingsCache;
      } finally {
        settingsPromise = null;
      }
    })();
    return settingsPromise;
  }

  const runtime = (frappe.persian_calendar.runtime =
    frappe.persian_calendar.runtime || {});
  syncBootDisplayCalendar();

  function getEffectiveCalendarMode() {
    return getEffectiveCalendarModeSync();
  }

  Object.assign(runtime, {
    getActiveCalendarPreferenceSync,
    getEffectiveCalendarMode,
    getEffectiveCalendarModeSync,
    getCalendarPreferenceDebugSync,
    shouldUseJalaliCalendarSync,
    shouldConvertToJalaliSync,
    invalidateCalendarSettingsCache,
    updateBootFromUserCalendarPreference,
    configureSystemDefaultCalendarSync,
    syncBootDisplayCalendar,
    fetchCalendarSettings,
    getSettingsCache: () => settingsCache,
    resolveDisplayCalendar,
    normalizeCalendarMode,
    enableTrace() {
      try {
        localStorage.setItem("persian_calendar_trace", "1");
      } catch (e) {
        /* ignore */
      }
    },
    disableTrace() {
      try {
        localStorage.removeItem("persian_calendar_trace");
      } catch (e) {
        /* ignore */
      }
    },
    resetDestroyLog() {
      if (typeof window !== "undefined") {
        window.__persianCalendarDestroyLog = [];
      }
    },
    getDestroyLog() {
      return (typeof window !== "undefined" && window.__persianCalendarDestroyLog) || [];
    },
    resetCallCounts() {
      if (typeof window !== "undefined") {
        window.__persianCalendarCallCounts = {};
      }
    },
    getCallCounts() {
      return (typeof window !== "undefined" && window.__persianCalendarCallCounts) || {};
    },
    inspectDatetimeInput(inputEl) {
      const $input = window.jQuery ? window.jQuery(inputEl) : null;
      if (!$input?.length) {
        return { ok: false, reason: "no input" };
      }
      const inst = $input.data("jalaliDatepickerInstance");
      const val = String($input.val() || "");
      return {
        ok: true,
        value: val,
        hasNaN: /NaN/i.test(val),
        hasInvalid: /Invalid\s*date/i.test(val),
        hasJalaliAttr: $input.attr("data-has-jalali-datepicker") === "true",
        hasJalaliInstance: !!inst,
        jalaliOpen: !!(inst && inst.isOpen),
        gregorianMode: !shouldUseJalaliCalendarSync(),
        eventNs: $input.data("jalaliInputEventNs") || null,
      };
    },
  });
})();
