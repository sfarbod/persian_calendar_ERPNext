(function () {
  const fmt = new Intl.DateTimeFormat("en-u-ca-persian", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });

  function toJalaliPartsFromGregorianDate(gDate) {
    const parts = fmt.formatToParts(gDate);
    const map = Object.fromEntries(parts.map((p) => [p.type, p.value]));
    return {
      jy: parseInt(map.year, 10),
      jm: parseInt(map.month, 10),
      jd: parseInt(map.day, 10),
    };
  }

  function toJalali(gy, gm, gd) {
    return toJalaliPartsFromGregorianDate(new Date(gy, gm - 1, gd));
  }

  function toGregorian(jy, jm, jd) {
    jy = parseInt(jy, 10);
    jm = parseInt(jm, 10);
    jd = parseInt(jd, 10);
    if (!jy || !jm || !jd) return null;

    jm = Math.max(1, Math.min(12, jm));
    jd = Math.max(1, Math.min(31, jd));

    const startGy = jy + 621 - 4;
    const endGy = jy + 622 + 4;

    for (let gy = startGy; gy <= endGy; gy++) {
      for (let gm = 1; gm <= 12; gm++) {
        const daysInMonth = new Date(gy, gm, 0).getDate();
        for (let gd = 1; gd <= daysInMonth; gd++) {
          const gDate = new Date(gy, gm - 1, gd);
          const j = toJalaliPartsFromGregorianDate(gDate);
          if (j.jy === jy && j.jm === jm && j.jd === jd) {
            return { gy, gm, gd };
          }
        }
      }
    }
    return null;
  }

  function parseYMD(value) {
    if (value == null || value === "") return null;
    const m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(String(value).trim());
    if (!m) return null;
    return { y: parseInt(m[1], 10), m: parseInt(m[2], 10), d: parseInt(m[3], 10) };
  }

  function stripMicroseconds(value) {
    if (value == null || value === "") return value;
    let s = String(value).trim().replace("T", " ");
    s = s.replace(/(\d{1,2}:\d{2}:\d{2})\.\d+/, "$1");
    s = s.replace(/(\d{1,2}:\d{2})\.\d+/, "$1:00");
    return s;
  }

  function formatTimeHMS(h, i, s) {
    const hh = Math.max(0, Math.min(23, parseInt(h, 10) || 0));
    const mm = Math.max(0, Math.min(59, parseInt(i, 10) || 0));
    const ss = Math.max(0, Math.min(59, parseInt(s, 10) || 0));
    return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
  }

  const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
  const ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩";

  function toAsciiDigits(text) {
    return String(text).replace(/[۰-۹٠-٩]/g, (ch) => {
      const i = PERSIAN_DIGITS.indexOf(ch);
      return String(i !== -1 ? i : ARABIC_DIGITS.indexOf(ch));
    });
  }

  function currentJalaliYear() {
    try {
      return toJalaliPartsFromGregorianDate(new Date()).jy;
    } catch (e) {
      return null;
    }
  }

  /**
   * Expand typed shorthand to ISO-like form before parsing:
   *   "۱۴۰۵/۰۱/۲۰" → "1405-01-20"  (digit translation + year-first separators)
   *   "14050120"   → "1405-01-20"  (YYYYMMDD)
   *   "0120"       → "<current jy>-01-20"  (MMDD, Jalali UI only)
   * Optional trailing " HH:mm[:ss]" is preserved. Non-matching input is
   * returned with digits translated only.
   */
  function expandDateInputShorthand(value) {
    if (value == null || value === "") return value;
    let s = toAsciiDigits(String(value).trim());
    s = s.replace(/^(\d{4})[/.](\d{1,2})[/.](\d{1,2})/, "$1-$2-$3");
    const m = /^(\d{4}|\d{8})(\s+\d{1,2}:\d{2}(?::\d{2})?)?$/.exec(s);
    if (!m) return s;
    const digits = m[1];
    const time = m[2] || "";
    let y, mo, d;
    if (digits.length === 8) {
      y = parseInt(digits.slice(0, 4), 10);
      mo = parseInt(digits.slice(4, 6), 10);
      d = parseInt(digits.slice(6, 8), 10);
    } else {
      if (!jalaliUiActive()) return s;
      y = currentJalaliYear();
      mo = parseInt(digits.slice(0, 2), 10);
      d = parseInt(digits.slice(2, 4), 10);
    }
    if (!y || mo < 1 || mo > 12 || d < 1 || d > 31) return s;
    return `${y}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}${time}`;
  }

  /** Parse YYYY-MM-DD[ HH:mm[:ss][.fraction]] — no Date() on full string. */
  function parseDateTimeParts(value) {
    const s = stripMicroseconds(value);
    if (!s) return null;
    const m =
      /^(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/.exec(s) ||
      /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(s);
    if (!m) return null;
    return {
      y: parseInt(m[1], 10),
      m: parseInt(m[2], 10),
      d: parseInt(m[3], 10),
      h: m[4] != null ? parseInt(m[4], 10) : 0,
      i: m[5] != null ? parseInt(m[5], 10) : 0,
      s: m[6] != null ? parseInt(m[6], 10) : 0,
    };
  }

  function isLikelyGregorianISO(value) {
    const p = parseYMD(value);
    return !!(p && p.y >= 1700);
  }

  function isLikelyJalaliISO(value) {
    const p = parseYMD(value);
    return !!(p && p.y >= 1200 && p.y <= 1600);
  }

  function isLikelyGregorianDateTime(value) {
    const p = parseDateTimeParts(value);
    return !!(p && p.y >= 1700);
  }

  function isLikelyJalaliDateTime(value) {
    const p = parseDateTimeParts(value);
    return !!(p && p.y >= 1200 && p.y <= 1600);
  }

  const US_DATETIME_PARSE_FORMATS = [
    "M/D/YYYY H:mm",
    "M/D/YYYY HH:mm",
    "MM/DD/YYYY H:mm",
    "MM/DD/YYYY HH:mm",
    "M/D/YYYY h:mm A",
    "MM/DD/YYYY h:mm A",
    "D/M/YYYY H:mm",
    "DD/MM/YYYY H:mm",
    "D/M/YYYY HH:mm",
    "DD/MM/YYYY HH:mm",
    "YYYY-MM-DD HH:mm:ss",
    "YYYY-MM-DD HH:mm",
    "YYYY-MM-DD H:mm",
  ];

  /**
   * Parse assorted Gregorian datetime strings (import / user format) to model storage form.
   * Returns YYYY-MM-DD HH:mm:ss or null. Never treats Jalali years as Gregorian.
   */
  function coerceToGregorianDateTime(value) {
    if (value == null || value === "") {
      return null;
    }
    const str = expandDateInputShorthand(stripMicroseconds(String(value).trim()));
    if (!str) {
      return null;
    }

    if (isLikelyGregorianDateTime(str)) {
      const p = parseDateTimeParts(str);
      if (p) {
        return `${formatGregorianParts(p.y, p.m, p.d)} ${formatTimeHMS(p.h, p.i, p.s)}`;
      }
    }
    if (isLikelyJalaliDateTime(str)) {
      return jalaliDateTimeToGregorian(str);
    }

    if (typeof moment !== "undefined") {
      const formats = [...US_DATETIME_PARSE_FORMATS];
      try {
        const dateFmt = (
          frappe.boot?.sysdefaults?.date_format ||
          frappe.sys_defaults?.date_format ||
          "yyyy-mm-dd"
        ).toUpperCase();
        const timeFmt =
          (typeof frappe !== "undefined" &&
            frappe.datetime &&
            frappe.datetime.get_user_time_fmt &&
            frappe.datetime.get_user_time_fmt()) ||
          frappe.boot?.sysdefaults?.time_format ||
          "HH:mm:ss";
        formats.unshift(`${dateFmt} ${timeFmt}`);
        if (typeof frappe !== "undefined" && frappe.defaultDatetimeFormat) {
          formats.push(frappe.defaultDatetimeFormat);
        }
      } catch (e) {
        /* ignore */
      }

      let m = moment(str, formats, true);
      if (!m.isValid()) {
        m = moment(str, formats, false);
      }
      if (m.isValid()) {
        return m.format("YYYY-MM-DD HH:mm:ss");
      }
    }
    return null;
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

  function jalaliUiActive() {
    try {
      const rt = typeof frappe !== "undefined" && frappe.persian_calendar?.runtime;
      if (rt?.shouldUseJalaliCalendarSync) {
        return rt.shouldUseJalaliCalendarSync();
      }
    } catch (e) {
      /* ignore */
    }
    return true;
  }

  function formatJalaliParts(jy, jm, jd) {
    const y = parseInt(jy, 10);
    const m = parseInt(jm, 10);
    const d = parseInt(jd, 10);
    if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(d)) {
      if (typeof console !== "undefined" && console.warn) {
        console.warn("[persian_calendar] formatJalaliParts rejected invalid parts", {
          jy,
          jm,
          jd,
        });
      }
      return "";
    }
    return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  }

  function formatGregorianParts(gy, gm, gd) {
    return `${gy}-${String(gm).padStart(2, "0")}-${String(gd).padStart(2, "0")}`;
  }

  function gregorianToJalaliISO(value) {
    if (!jalaliUiActive()) return null;
    if (!isLikelyGregorianISO(value)) return null;
    const p = parseYMD(value);
    if (!p) return null;
    const j = toJalali(p.y, p.m, p.d);
    return formatJalaliParts(j.jy, j.jm, j.jd);
  }

  function jalaliPartsToGregorianISO(jy, jm, jd) {
    const g = toGregorian(jy, jm, jd);
    if (!g) return null;
    return formatGregorianParts(g.gy, g.gm, g.gd);
  }

  function jalaliToGregorianISO(value) {
    if (!isLikelyJalaliISO(value)) return null;
    const p = parseYMD(value);
    if (!p) return null;
    return jalaliPartsToGregorianISO(p.y, p.m, p.d);
  }

  function gregorianDateTimeToJalali(value) {
    if (!jalaliUiActive()) {
      return null;
    }
    const p = parseDateTimeParts(value);
    if (!p || p.y < 1700) return null;
    const j = toJalali(p.y, p.m, p.d);
    if (!j || !Number.isFinite(j.jy) || !Number.isFinite(j.jm) || !Number.isFinite(j.jd)) {
      return null;
    }
    const dateStr = formatJalaliParts(j.jy, j.jm, j.jd);
    if (!dateStr) {
      return null;
    }
    return `${dateStr} ${formatTimeHMS(p.h, p.i, p.s)}`;
  }

  /**
   * Grid/list display: model stays Gregorian; show Jalali. Handles ISO, Jalali, and user formats (dd-mm-yyyy).
   */
  function valueToJalaliDisplay(value, fieldtype) {
    incCallCount("valueToJalaliDisplay");
    if (!jalaliUiActive()) {
      return value == null ? "" : String(value);
    }
    if (value == null || value === "") {
      return "";
    }
    const str = stripMicroseconds(String(value).trim());
    const isDatetime = fieldtype === "Datetime";

    if (isDatetime && isLikelyJalaliDateTime(str)) {
      const p = parseDateTimeParts(str);
      if (p) {
        return `${formatJalaliParts(p.y, p.m, p.d)} ${formatTimeHMS(p.h, p.i, p.s)}`;
      }
      return str;
    }
    const datePart = str.indexOf(" ") === -1 ? str : str.slice(0, str.indexOf(" "));
    if (!isDatetime && isLikelyJalaliISO(datePart)) {
      return datePart;
    }
    if (isDatetime && isLikelyGregorianDateTime(str)) {
      return gregorianDateTimeToJalali(str) || str;
    }
    if (isLikelyGregorianISO(datePart)) {
      const j = gregorianToJalaliISO(datePart);
      if (!j) {
        return str;
      }
      if (isDatetime && str.length > datePart.length) {
        const tp = parseDateTimeParts(`2000-01-01 ${str.slice(datePart.length + 1)}`);
        const t = tp ? formatTimeHMS(tp.h, tp.i, tp.s) : "";
        return t ? `${j} ${t}` : j;
      }
      return j;
    }

    const coerced = coerceToGregorianDateTime(str);
    if (coerced) {
      return valueToJalaliDisplay(coerced, fieldtype);
    }

    if (typeof moment !== "undefined" && frappe?.datetime) {
      try {
        const dateFmt = (
          frappe.boot?.sysdefaults?.date_format ||
          frappe.sys_defaults?.date_format ||
          "yyyy-mm-dd"
        ).toUpperCase();
        const timeFmt = frappe.datetime.get_user_time_fmt
          ? frappe.datetime.get_user_time_fmt()
          : "HH:mm:ss";
        let m;
        if (isDatetime) {
          m = moment(str, [
            `${dateFmt} ${timeFmt}`,
            ...US_DATETIME_PARSE_FORMATS,
            frappe.defaultDatetimeFormat,
            "YYYY-MM-DD HH:mm:ss",
            moment.ISO_8601,
          ]);
        } else {
          m = moment(str, [dateFmt, frappe.defaultDateFormat, "YYYY-MM-DD", moment.ISO_8601]);
        }
        if (m.isValid()) {
          const iso = isDatetime
            ? m.format("YYYY-MM-DD HH:mm:ss")
            : m.format("YYYY-MM-DD");
          return valueToJalaliDisplay(iso, fieldtype);
        }
      } catch (e) {
        /* ignore */
      }
    }
    return str;
  }

  function looksLikeGregorianUserDisplay(text) {
    if (!text) {
      return false;
    }
    const t = String(text).trim();
    if (/^\d{4}-\d{1,2}-\d{1,2}/.test(t)) {
      const y = parseInt(t.slice(0, 4), 10);
      return y >= 1700;
    }
    return /^\d{1,2}-\d{1,2}-\d{4}/.test(t) || /^\d{1,2}\/\d{1,2}\/\d{4}/.test(t);
  }

  function jalaliDateTimeToGregorian(value) {
    const p = parseDateTimeParts(value);
    if (!p || p.y < 1200 || p.y > 1600) return null;
    const gDate = jalaliPartsToGregorianISO(p.y, p.m, p.d);
    if (!gDate) return null;
    return `${gDate} ${formatTimeHMS(p.h, p.i, p.s)}`;
  }

  function jalaliPartsDateTimeToGregorian(jy, jm, jd, h, i, s) {
    const gDate = jalaliPartsToGregorianISO(jy, jm, jd);
    if (!gDate) return null;
    return `${gDate} ${formatTimeHMS(h, i, s)}`;
  }

  function normalizeModelDate(value) {
    if (value == null || value === "") return value;
    const str = expandDateInputShorthand(stripMicroseconds(String(value).trim()));
    const spaceIdx = str.indexOf(" ");
    const datePart = spaceIdx === -1 ? str : str.slice(0, spaceIdx);
    let timePart = spaceIdx === -1 ? "" : str.slice(spaceIdx + 1);
    if (timePart) {
      const tp = parseDateTimeParts(`2000-01-01 ${timePart}`);
      if (tp) timePart = formatTimeHMS(tp.h, tp.i, tp.s);
    }

    if (isLikelyGregorianISO(datePart)) {
      return timePart ? `${datePart} ${timePart}` : datePart;
    }
    if (isLikelyJalaliISO(datePart)) {
      const g = jalaliToGregorianISO(datePart);
      if (!g) return str;
      return timePart ? `${g} ${timePart}` : g;
    }
    return str;
  }

  function normalizeModelDateTime(value) {
    if (value == null || value === "") {
      return value;
    }
    const coerced = coerceToGregorianDateTime(value);
    if (coerced) {
      return coerced;
    }
    if (typeof console !== "undefined" && console.warn) {
      console.warn(
        "[persian_calendar] could not coerce datetime; preserving original value:",
        value
      );
    }
    return value;
  }

  window.toJalali = toJalali;
  window.toGregorian = toGregorian;
  window.toJalaliPartsFromGregorianDate = toJalaliPartsFromGregorianDate;

  window.jalaliDateUtils = {
    parseYMD,
    parseDateTimeParts,
    stripMicroseconds,
    isLikelyGregorianISO,
    isLikelyJalaliISO,
    isLikelyGregorianDateTime,
    isLikelyJalaliDateTime,
    gregorianToJalaliISO,
    jalaliToGregorianISO,
    jalaliPartsToGregorianISO,
    gregorianDateTimeToJalali,
    jalaliDateTimeToGregorian,
    jalaliPartsDateTimeToGregorian,
    normalizeModelDate,
    normalizeModelDateTime,
    coerceToGregorianDateTime,
    expandDateInputShorthand,
    toAsciiDigits,
    valueToJalaliDisplay,
    looksLikeGregorianUserDisplay,
    formatJalaliParts,
    formatGregorianParts,
    formatTimeHMS,
  };
})();
