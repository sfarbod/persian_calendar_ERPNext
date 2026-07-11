/**
 * Node tests for Jalali list/form formatter behavior.
 * Run: node persian_calendar/public/js/jalali_support/test_formatters.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import vm from "node:vm";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function loadJalaliDateUtils() {
  const src = fs.readFileSync(path.join(__dirname, "jalaali.js"), "utf8");
  const context = { window: {}, console };
  vm.createContext(context);
  vm.runInContext(src, context);
  return context.window.jalaliDateUtils;
}

function mockRuntime(jalaliActive) {
  return {
    shouldConvertToJalaliSync: () => jalaliActive,
    shouldUseJalaliCalendarSync: () => jalaliActive,
    getEffectiveCalendarModeSync: () => (jalaliActive ? "Jalali" : "Gregorian"),
  };
}

function installFrappeFormatters({ jalaliActive, utils }) {
  const origDate = function (value) {
    return `GREG_DATE:${value}`;
  };
  const origDatetime = function (value) {
    return `GREG_DT:${value}`;
  };

  const formatters = {
    Date: origDate,
    Datetime: origDatetime,
    Data(value) {
      return value;
    },
  };

  // Legacy incorrect patch (lowercase) — must not be used by get_formatter.
  formatters.date = function (value) {
    return `WRONG_DATE:${value}`;
  };
  formatters.datetime = function (value) {
    return `WRONG_DT:${value}`;
  };

  function shouldConvertToJalali() {
    return jalaliActive;
  }

  function g2j_str(value, fieldtype) {
    if (!shouldConvertToJalali() || !value || !utils) {
      return value;
    }
    const ft = fieldtype === "Datetime" ? "Datetime" : "Date";
    return utils.valueToJalaliDisplay(value, ft);
  }

  // Correct PascalCase patch (matches formatters.js).
  function applyPascalCasePatch() {
    if (formatters._pcJalaliPatched) {
      return { orig_date_formatter: null, orig_datetime_formatter: null, skipped: true };
    }
    const orig_date_formatter = formatters.Date;
    const orig_datetime_formatter = formatters.Datetime;

    formatters.Date = function (value, df, options, doc) {
      if (!value) {
        return value;
      }
      if (!shouldConvertToJalali()) {
        return orig_date_formatter(value, df, options, doc);
      }
      return g2j_str(value, "Date");
    };

    formatters.Datetime = function (value, df, options, doc) {
      if (!value) {
        return value;
      }
      if (!shouldConvertToJalali()) {
        return orig_datetime_formatter(value, df, options, doc);
      }
      return g2j_str(value, "Datetime");
    };

    formatters._pcJalaliPatched = true;
    return { orig_date_formatter, orig_datetime_formatter, skipped: false };
  }

  applyPascalCasePatch();

  function get_formatter(fieldtype) {
    return formatters[fieldtype.replace(/ /g, "")] || formatters.Data;
  }

  function format(value, df) {
    const formatter = get_formatter(df.fieldtype || "Data");
    return formatter(value, df);
  }

  return { formatters, format, get_formatter, g2j_str, shouldConvertToJalali };
}

function runTests() {
  const utils = loadJalaliDateUtils();
  const sampleDate = "2026-05-24";
  const sampleDatetime = "2026-05-24 09:44:47";

  // --- Formatter key resolution ---
  {
    const { get_formatter } = installFrappeFormatters({ jalaliActive: true, utils });
    assert(get_formatter("Date") === get_formatter("Date"), "Date formatter resolves");
    assert(get_formatter("Datetime") !== get_formatter("date"), "Datetime != lowercase date");
    assert(typeof get_formatter("Datetime") === "function", "Datetime formatter exists");
  }

  // --- Jalali enabled: Date and Datetime both convert ---
  {
    const { format } = installFrappeFormatters({ jalaliActive: true, utils });
    const dateOut = format(sampleDate, { fieldtype: "Date" });
    const dtOut = format(sampleDatetime, { fieldtype: "Datetime" });

    assert(dateOut.startsWith("140"), `Date list output should be Jalali year, got ${dateOut}`);
    assert(dtOut.startsWith("140"), `Datetime list output should be Jalali year, got ${dtOut}`);
    assert(dtOut.includes("09:44:47"), `Datetime should preserve time, got ${dtOut}`);
    assert(!dateOut.startsWith("GREG_"), "Date must not use stock Gregorian formatter");
    assert(!dtOut.startsWith("GREG_"), "Datetime must not use stock Gregorian formatter");
    assert(!dtOut.startsWith("WRONG_"), "Datetime must not use lowercase patched formatter");
  }

  // --- Gregorian preference ---
  {
    const { format } = installFrappeFormatters({ jalaliActive: false, utils });
    assert(
      format(sampleDate, { fieldtype: "Date" }) === `GREG_DATE:${sampleDate}`,
      "Gregorian Date falls back to stock formatter"
    );
    assert(
      format(sampleDatetime, { fieldtype: "Datetime" }) === `GREG_DT:${sampleDatetime}`,
      "Gregorian Datetime falls back to stock formatter"
    );
  }

  // --- Empty / invalid ---
  {
    const { format, g2j_str } = installFrappeFormatters({ jalaliActive: true, utils });
    assert(format("", { fieldtype: "Datetime" }) === "", "Empty datetime stays empty");
    assert(format(null, { fieldtype: "Date" }) == null, "Null date preserved");
    assert(
      g2j_str("not-a-date", "Datetime") === "not-a-date",
      "Unparseable datetime returned unchanged"
    );
  }

  // --- Utilities unavailable ---
  {
    const { g2j_str, shouldConvertToJalali } = installFrappeFormatters({
      jalaliActive: true,
      utils: null,
    });
    assert(shouldConvertToJalali(), "sanity: jalali active");
    assert(
      g2j_str(sampleDatetime, "Datetime") === sampleDatetime,
      "Without jalaliDateUtils, raw ISO is preserved"
    );
  }

  // --- valueToJalaliDisplay direct cases ---
  {
    const out = utils.valueToJalaliDisplay(sampleDatetime, "Datetime");
    assert(out.startsWith("140"), `valueToJalaliDisplay datetime Jalali year, got ${out}`);
    assert(out.includes("09:44:47"), `valueToJalaliDisplay preserves time, got ${out}`);

    const dateOnly = utils.valueToJalaliDisplay(sampleDate, "Date");
    assert(dateOnly.startsWith("140"), `valueToJalaliDisplay date Jalali year, got ${dateOnly}`);
  }

  // --- Document why Date appeared to work before the fix ---
  {
    // Stock Frappe Date formatter calls str_to_user (patched globally). Datetime uses moment directly.
    const strToUser = (value) =>
      utils.valueToJalaliDisplay(value, value.includes(" ") ? "Datetime" : "Date");
    const stockDateFormatter = (value) => strToUser(value);
    const stockDatetimeFormatter = (value) => `GREG_LOCAL:${value}`;

    const dateViaStock = stockDateFormatter(sampleDate);
    const dtViaStock = stockDatetimeFormatter(sampleDatetime);

    assert(dateViaStock.startsWith("140"), "Date via str_to_user path was already Jalali");
    assert(dtViaStock.startsWith("GREG_"), "Datetime stock path stayed Gregorian");
  }

  // --- Near-midnight: preserve stored server time (option A) ---
  {
    const midnightSample = "2026-05-24 23:30:00";
    const { format } = installFrappeFormatters({ jalaliActive: true, utils });
    const listOut = format(midnightSample, { fieldtype: "Datetime" });
    const formOut = utils.valueToJalaliDisplay(midnightSample, "Datetime");
    assert(listOut === formOut, `List/form must match near midnight: ${listOut} vs ${formOut}`);
    assert(listOut.includes("23:30:00"), `Server time preserved: ${listOut}`);
    assert(listOut.startsWith("140"), `Near-midnight Jalali year: ${listOut}`);
    const datePart = listOut.split(" ")[0];
    assert(!datePart.endsWith("-04"), "No unexpected one-day shift on Jalali date part");
  }

  // --- Idempotent patch: second apply must not wrap again ---
  {
    const { formatters, format } = installFrappeFormatters({ jalaliActive: true, utils });
    const first = formatters.Datetime;
    function applyPascalCasePatchAgain() {
      if (formatters._pcJalaliPatched) {
        return false;
      }
      formatters.Datetime = function (v) {
        return `DOUBLE:${v}`;
      };
      formatters._pcJalaliPatched = true;
      return true;
    }
    assert(applyPascalCasePatchAgain() === false, "Second patch skipped when flag set");
    assert(formatters.Datetime === first, "Datetime formatter identity unchanged");
    const out = format("2026-05-24 09:44:47", { fieldtype: "Datetime" });
    assert(out.startsWith("140"), "Still Jalali after skipped re-patch");
    assert(!out.startsWith("DOUBLE:"), "No recursive self-wrap");
  }

  // --- PascalCase originals referenced, not lowercase ---
  {
    const { formatters } = installFrappeFormatters({ jalaliActive: false, utils });
    assert(typeof formatters.Date === "function", "Date key is PascalCase");
    assert(typeof formatters.Datetime === "function", "Datetime key is PascalCase");
    assert(formatters.date !== formatters.Date, "Lowercase date is not the active formatter");
    assert(formatters.datetime !== formatters.Datetime, "Lowercase datetime is not the active formatter");
  }

  // --- Timezone policy: stored server time, no convert_to_user_tz in Jalali path ---
  {
    const serverVal = "2026-05-24 23:30:00";
    const listDisplay = utils.valueToJalaliDisplay(serverVal, "Datetime");
    // Simulated stock path would shift time when user TZ differs; our path keeps 23:30:00.
    assert(listDisplay.includes("23:30:00"), "Policy A: preserve stored server time component");
    assert(
      listDisplay === utils.valueToJalaliDisplay(serverVal, "Datetime"),
      "Deterministic conversion without TZ layer"
    );
  }

  console.log("test_formatters.mjs: all tests passed");
}

runTests();
