(async function() {
  let jalaliEnabled = false;

  try {
    const result = await frappe.call({ method: "persian_calendar.jalali_support.api.is_jalali_enabled" });
    jalaliEnabled = result && result.message;
  } catch (e) {
    jalaliEnabled = false;
  }

  if (!jalaliEnabled) {
    return;
  }

  let EFFECTIVE_CALENDAR = {
    display_calendar: "Jalali",
    week_start: 6,
    week_end: 5,
  };

  try {
    const r = await frappe.call({ method: "persian_calendar.jalali_support.api.get_effective_calendar" });
    if (r && r.message) {
      EFFECTIVE_CALENDAR = r.message;
    }
  } catch (e) {
    /* keep defaults */
  }

  function g2j_str(value) {
    try {
      const toJ = typeof window !== "undefined" && window.toJalali;
      if (!toJ) return value;
      const d = new Date(value + (value.length === 10 ? "T00:00:00Z" : "Z"));
      if (isNaN(d)) return value;
      const j = toJ(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
      return `${j.jy}-${String(j.jm).padStart(2, "0")}-${String(j.jd).padStart(2, "0")}`;
    } catch (e) {
      return value;
    }
  }

  function j2g_str(value) {
    if (!value) return value;

    try {
      const dateMatch = value.match(/^(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{2}):(\d{2}):(\d{2}))?/);
      if (!dateMatch) {
        return value;
      }

      const jy = parseInt(dateMatch[1], 10);
      const jm = parseInt(dateMatch[2], 10);
      const jd = parseInt(dateMatch[3], 10);
      const hour = dateMatch[4] ? parseInt(dateMatch[4], 10) : 0;
      const minute = dateMatch[5] ? parseInt(dateMatch[5], 10) : 0;
      const second = dateMatch[6] ? parseInt(dateMatch[6], 10) : 0;

      if (jy < 1300 || jy > 1500) {
        return value;
      }

      const toG = typeof window !== "undefined" && window.toGregorian;
      if (!toG) {
        return value;
      }

      const g = toG(jy, jm, jd);
      if (!g) return value;

      const gregorianDate = `${g.gy}-${String(g.gm).padStart(2, "0")}-${String(g.gd).padStart(2, "0")}`;

      if (dateMatch[4]) {
        return `${gregorianDate} ${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}:${String(second).padStart(2, "0")}`;
      }

      return gregorianDate;
    } catch (e) {
      return value;
    }
  }

  function shouldConvertToJalali() {
    return EFFECTIVE_CALENDAR && EFFECTIVE_CALENDAR.display_calendar === "Jalali";
  }

  const dt = frappe.datetime;
  const orig_str_to_user = dt.str_to_user?.bind(dt);
  const orig_str_to_user_with_default = dt.str_to_user_with_default?.bind(dt);
  const orig_user_to_str = dt.user_to_str?.bind(dt);
  const orig_format_date = dt.format_date?.bind(dt);
  const orig_format_datetime = dt.format_datetime?.bind(dt);

  if (orig_str_to_user) {
    dt.str_to_user = function (value) {
      if (!value) return value;
      if (!shouldConvertToJalali()) {
        return orig_str_to_user(value);
      }
      if (typeof window !== "undefined" && !window.toJalali) {
        return orig_str_to_user(value);
      }
      const is_datetime = typeof value === "string" && value.length > 10 && value.includes(":");
      if (is_datetime) {
        const date = value.slice(0, 10);
        const time = value.slice(11, 19);
        return `${g2j_str(date)} ${time}`.trim();
      }
      return g2j_str(value);
    };
  }
  if (orig_str_to_user_with_default) {
    dt.str_to_user_with_default = function (value) {
      if (!value) return value;
      if (!shouldConvertToJalali()) {
        return orig_str_to_user_with_default(value);
      }
      return dt.str_to_user(value);
    };
  }
  if (orig_user_to_str) {
    dt.user_to_str = function (value) {
      if (!value) return value;
      if (!shouldConvertToJalali()) {
        return orig_user_to_str(value);
      }
      if (typeof window !== "undefined" && !window.toGregorian) {
        return orig_user_to_str(value);
      }
      return j2g_str(value);
    };
  }
  if (orig_format_date) {
    dt.format_date = function (date_str) {
      if (!shouldConvertToJalali()) {
        return orig_format_date(date_str);
      }
      const j = g2j_str(date_str);
      if (j === date_str && typeof window !== "undefined" && !window.toJalali) {
        return orig_format_date(date_str);
      }
      return j;
    };
  }
  if (orig_format_datetime) {
    dt.format_datetime = function (value) {
      if (!value) return value;
      if (!shouldConvertToJalali()) {
        return orig_format_datetime(value);
      }
      const date = value.slice(0, 10);
      const time = value.slice(11, 19) || "";
      const j = g2j_str(date);
      if (j === date && typeof window !== "undefined" && !window.toJalali) {
        return orig_format_datetime(value);
      }
      return `${j} ${time}`.trim();
    };
  }

  const orig_date_formatter = frappe.form.formatters.date;
  const orig_datetime_formatter = frappe.form.formatters.datetime;

  frappe.form.formatters.date = function (value, df, options, doc) {
    if (!value) return value;
    if (!shouldConvertToJalali()) {
      if (orig_date_formatter) {
        return orig_date_formatter(value, df, options, doc);
      }
      return value;
    }
    const j = g2j_str(value);
    if (j === value && typeof window !== "undefined" && !window.toJalali) {
      if (orig_date_formatter) {
        return orig_date_formatter(value, df, options, doc);
      }
      return value;
    }
    return j;
  };

  frappe.form.formatters.datetime = function (value, df, options, doc) {
    if (!value) return value;
    if (!shouldConvertToJalali()) {
      if (orig_datetime_formatter) {
        return orig_datetime_formatter(value, df, options, doc);
      }
      return value;
    }
    const toJ = typeof window !== "undefined" && window.toJalali;
    if (!toJ) {
      if (orig_datetime_formatter) {
        return orig_datetime_formatter(value, df, options, doc);
      }
      return value;
    }
    const d = new Date(value);
    if (isNaN(d)) return value;
    const j = toJ(d.getFullYear(), d.getMonth() + 1, d.getDate());
    const time = value.slice(11, 19) || "";
    return `${j.jy}-${String(j.jm).padStart(2, "0")}-${String(j.jd).padStart(2, "0")} ${time}`;
  };
})();
