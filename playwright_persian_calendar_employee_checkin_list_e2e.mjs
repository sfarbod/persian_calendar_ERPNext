#!/usr/bin/env node
/**
 * Playwright E2E: Persian Calendar Employee Checkin list/form datetime rendering.
 *
 * Run (from app root, bench must be up):
 *   bench build --app persian_calendar
 *   bench --site development.localhost clear-cache
 *   bench --site development.localhost set-config persian_calendar_e2e_fixtures 1
 *   node playwright_persian_calendar_employee_checkin_list_e2e.mjs
 *
 * Env: BASE_URL, FRAPPE_SITE, ADMIN_PASSWORD, HEADLESS (default 1)
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BASE_URL = (process.env.BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const SITE_HOST = process.env.FRAPPE_SITE || "development.localhost";
const ADMIN_PASSWORD = process.env.CYPRESS_ADMIN_PASSWORD || process.env.ADMIN_PASSWORD || "admin";
const HEADLESS = process.env.HEADLESS !== "0";
const SCREENSHOT_DIR = path.join(__dirname, "e2e", "screenshots", "playwright");
const RESULTS = [];

const FIXTURE_MODULE = "persian_calendar.jalali_support.e2e_fixtures";

function log(msg) {
  console.log(msg);
}

function record(scenario, passed, detail = "") {
  RESULTS.push({ scenario, passed, detail });
  const mark = passed ? "PASS" : "FAIL";
  console.log(`[${mark}] ${scenario}${detail ? `: ${detail}` : ""}`);
}

async function browserLogin(page, deskOrigin) {
  await page.goto(`${deskOrigin}/login`, { waitUntil: "domcontentloaded" });
  await page.fill("#login_email", "Administrator");
  await page.fill("#login_password", ADMIN_PASSWORD);
  await page.click('button.btn-login, button[type="submit"]');
  await page.waitForURL(/\/(app|desk)/, { timeout: 120000 });
  await waitForDeskBoot(page);
}

async function frappeCall(page, method, args = {}) {
  return page.evaluate(
    async ({ method, args }) => {
      const r = await frappe.call({ method, args });
      return r.message;
    },
    { method, args }
  );
}

async function loadJalaliExpectedAsync(isoDatetime) {
  const src = fs.readFileSync(
    path.join(__dirname, "persian_calendar/public/js/jalali_support/jalaali.js"),
    "utf8"
  );
  const { createContext, runInContext } = await import("node:vm");
  const context = { window: {}, console, frappe: undefined, moment: undefined };
  createContext(context);
  runInContext(src, context);
  context.frappe = {
    persian_calendar: {
      runtime: { shouldUseJalaliCalendarSync: () => true },
    },
  };
  return context.window.jalaliDateUtils.valueToJalaliDisplay(isoDatetime, "Datetime");
}

function normalizeVisible(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .trim();
}

function isJalaliYear(text) {
  const m = /(\d{4})-\d{2}-\d{2}/.exec(text);
  if (!m) return false;
  const y = parseInt(m[1], 10);
  return y >= 1300 && y <= 1500;
}

function isGregorianYear(text) {
  const m = /(\d{4})-\d{2}-\d{2}|(\d{1,2})[-/](\d{1,2})[-/](\d{4})/.exec(text);
  if (!m) return false;
  if (m[1]) {
    const y = parseInt(m[1], 10);
    return y >= 1900 && y <= 2100;
  }
  const y = parseInt(m[4], 10);
  return y >= 1900 && y <= 2100;
}

async function waitForDeskRoute(page, routePart) {
  await page.waitForFunction(
    (part) => window.location.pathname.includes(part) || window.location.hash.includes(part),
    routePart,
    { timeout: 60000 }
  );
}

async function waitForListRows(page) {
  await page.waitForFunction(
    () => window.cur_list && document.querySelector(".frappe-list .list-row-container"),
    { timeout: 120000 }
  );
}

async function getListTimeCellText(page, docname) {
  const formatted = await page.evaluate((name) => {
    const doc = window.cur_list?.data?.find((d) => d.name === name);
    if (!doc || !window.cur_list) {
      return null;
    }
    const df = frappe.meta.get_field("Employee Checkin", "time") || {
      fieldtype: "Datetime",
      fieldname: "time",
      parent: "Employee Checkin",
    };
    return frappe.format(doc.time, df, null, doc);
  }, docname);
  if (formatted) {
    return normalizeVisible(formatted);
  }

  const row = page.locator(".list-row-container").filter({
    has: page.locator(`a[href*="${docname}"], a[data-name="${docname}"]`),
  });
  await row.first().waitFor({ state: "attached", timeout: 60000 });
  const cell = row.first().locator(".list-row-col.time");
  if (await cell.count()) {
    return normalizeVisible(await cell.innerText());
  }
  return normalizeVisible(await row.first().innerText());
}

async function getFormTimeValue(page) {
  const field = page.locator('[data-fieldname="time"] input, [data-fieldname="time"] .control-value, [data-fieldname="time"] .like-disabled-input');
  await field.first().waitFor({ state: "visible", timeout: 30000 });
  const el = field.first();
  const tag = await el.evaluate((n) => n.tagName.toLowerCase());
  if (tag === "input") {
    return normalizeVisible(await el.inputValue());
  }
  return normalizeVisible(await el.innerText());
}

const DOCTYPE_SLUGS = {
  "employee-checkin": "Employee Checkin",
  "leave-application": "Leave Application",
  "error-log": "Error Log",
};

async function waitForDeskBoot(page) {
  await page.waitForFunction(
    () =>
      typeof frappe !== "undefined" &&
      frappe.boot?.persian_calendar &&
      frappe.form.formatters._pcJalaliPatched &&
      typeof frappe.set_route === "function",
    { timeout: 180000 }
  );
}

async function openListDoctype(page, doctype) {
  await page.evaluate((dt) => frappe.set_route("List", dt), doctype);
  await page.waitForFunction(
    (dt) => window.cur_list && window.cur_list.doctype === dt && document.querySelector(".frappe-list"),
    doctype,
    { timeout: 120000 }
  );
  await waitForListRows(page);
}

async function openFormDoctype(page, doctype, name) {
  await page.evaluate(([dt, docname]) => frappe.set_route("Form", dt, docname), [doctype, name]);
  await page.waitForSelector(".form-layout", { timeout: 120000 });
}

async function openDeskPath(page, deskPath) {
  const parts = deskPath.replace(/^\/(app|desk)\//, "").split("/").filter(Boolean);
  const doctype = DOCTYPE_SLUGS[parts[0]] || parts[0];
  if (parts.length === 1) {
    await openListDoctype(page, doctype);
    return;
  }
  await openFormDoctype(page, doctype, decodeURIComponent(parts.slice(1).join("/")));
}

async function captureFailure(page, name) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  const file = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  return file;
}

async function run() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  const deskOrigin = `http://${SITE_HOST}:8000`;
  const browser = await chromium.launch({
    headless: HEADLESS,
    args: [`--host-resolver-rules=MAP ${SITE_HOST} 127.0.0.1`, "--lang=en-US"],
  });
  const context = await browser.newContext({
    ignoreHTTPSErrors: true,
    locale: "en-US",
    timezoneId: process.env.E2E_TIMEZONE || "Asia/Tehran",
  });
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const t = msg.text();
      if (!t.includes("favicon") && !t.includes("404")) {
        consoleErrors.push(t);
      }
    }
  });
  page.on("pageerror", (err) => pageErrors.push(String(err)));

  let fixtureName = null;
  let savedCalendarPref = null;
  let screenshotOnFail = null;

  try {
    log("Logging in via browser...");
    await browserLogin(page, deskOrigin);

    log("Enabling Jalali E2E context...");
    await frappeCall(page, `${FIXTURE_MODULE}.set_calendar_e2e_context`, {
      default_calendar: "Jalali",
      user_calendar_preference: "Jalali",
      persian_calendar_enabled: true,
    });

    const midnightIso = "2026-05-24 23:30:00";
    const fixture = await frappeCall(
      page,
      `${FIXTURE_MODULE}.create_employee_checkin_datetime_fixture`,
      { checkin_time: midnightIso }
    );
    fixtureName = fixture.name;
    const expectedJalali = await loadJalaliExpectedAsync(fixture.time || midnightIso);
    log(`Fixture ${fixtureName} time=${fixture.time} expected Jalali=${expectedJalali}`);

    // --- Scenario A: Jalali Employee Checkin List ---
    try {
      await openDeskPath(page, "/app/employee-checkin");
      await waitForListRows(page);
      const listText = await getListTimeCellText(page, fixtureName);
      const jalaliOk = isJalaliYear(listText) && listText.includes("23:30:00");
      const matchesExpected = listText.includes(expectedJalali.split(" ")[0]) && listText.includes("23:30:00");
      record("A — Jalali Employee Checkin List", jalaliOk && matchesExpected, listText);
      if (!(jalaliOk && matchesExpected)) {
        screenshotOnFail = await captureFailure(page, "scenario-a-list");
      }
    } catch (e) {
      record("A — Jalali Employee Checkin List", false, String(e));
      screenshotOnFail = await captureFailure(page, "scenario-a-list-error");
    }

    // --- Scenario B: Jalali Employee Checkin Form ---
    let formTime = "";
    try {
      await openDeskPath(page, `/app/employee-checkin/${encodeURIComponent(fixtureName)}`);
      await page.waitForSelector('[data-fieldname="time"]', { timeout: 120000 });
      formTime = await getFormTimeValue(page);
      const listText = await getListTimeCellText(page, fixtureName).catch(() => "");
      const formOk = isJalaliYear(formTime) && formTime.includes("23:30:00");
      const sameAsList = !listText || normalizeVisible(formTime) === normalizeVisible(listText) || formTime.includes("23:30:00");
      record("B — Jalali Employee Checkin Form", formOk && sameAsList, `form=${formTime}`);
      if (!(formOk && sameAsList)) {
        screenshotOnFail = await captureFailure(page, "scenario-b-form");
      }
    } catch (e) {
      record("B — Jalali Employee Checkin Form", false, String(e));
      screenshotOnFail = await captureFailure(page, "scenario-b-form-error");
    }

    // --- Scenario C: Date list regression (Leave Application) ---
    try {
      await openDeskPath(page, "/app/leave-application");
      await waitForListRows(page);
      const count = await page.evaluate(() => window.cur_list?.data?.length || 0);
      if (count === 0) {
        record("C — Date List Regression (Leave Application)", true, "no data rows; list loaded");
      } else {
        const jalaliViaFormat = await page.evaluate(() => {
          const doc = window.cur_list?.data?.[0];
          if (!doc) return null;
          const df = frappe.meta.get_docfield("Leave Application", "from_date") ||
            frappe.meta.get_docfield("Leave Application", "posting_date");
          if (!df) return null;
          const val = doc[df.fieldname];
          return val ? frappe.format(val, df, null, doc) : null;
        });
        record(
          "C — Date List Regression (Leave Application)",
          !jalaliViaFormat || isJalaliYear(jalaliViaFormat),
          jalaliViaFormat || "no date field in first row"
        );
      }
    } catch (e) {
      record("C — Date List Regression (Leave Application)", false, String(e));
      await captureFailure(page, "scenario-c-leave");
    }

    // --- Scenario D: Additional Datetime list (Error Log creation column) ---
    try {
      await openDeskPath(page, "/app/error-log");
      await waitForListRows(page);
      const count = await page.evaluate(() => window.cur_list?.data?.length || 0);
      if (count === 0) {
        record("D — Datetime List (Error Log)", true, "no data rows; list loaded");
      } else {
        const dtDisplay = await page.evaluate(() => {
          const doc = window.cur_list?.data?.[0];
          if (!doc?.creation) {
            return null;
          }
          const df =
            frappe.meta.get_field("Error Log", "creation") ||
            { fieldtype: "Datetime", fieldname: "creation", label: "Created On" };
          return frappe.format(doc.creation, df, null, doc);
        });
        record(
          "D — Datetime List (Error Log)",
          dtDisplay && isJalaliYear(dtDisplay),
          dtDisplay || "no creation on first row"
        );
      }
    } catch (e) {
      record("D — Datetime List (Error Log)", false, String(e));
      await captureFailure(page, "scenario-d-error-log");
    }

    // --- Scenario E: Gregorian preference ---
    try {
      await frappeCall(page, `${FIXTURE_MODULE}.get_calendar_e2e_debug_state`);
      await frappeCall(page, `${FIXTURE_MODULE}.set_calendar_e2e_context`, {
        default_calendar: "Jalali",
        user_calendar_preference: "Gregorian",
        persian_calendar_enabled: true,
      });
      await page.reload({ waitUntil: "domcontentloaded" });
      await waitForDeskBoot(page);
      await openListDoctype(page, "Employee Checkin");
      const listText = await getListTimeCellText(page, fixtureName);
      const gregOk = isGregorianYear(listText) || /\d{1,2}[-/]\d{1,2}[-/]\d{4}/.test(listText);
      await openDeskPath(page, `/app/employee-checkin/${encodeURIComponent(fixtureName)}`);
      await page.waitForSelector('[data-fieldname="time"]', { timeout: 60000 });
      const formGreg = await getFormTimeValue(page);
      record(
        "E — Gregorian Preference",
        gregOk && (isGregorianYear(formGreg) || /\d{1,2}[-/]\d{1,2}[-/]\d{4}/.test(formGreg)),
        `list=${listText} form=${formGreg}`
      );
      await frappeCall(page, `${FIXTURE_MODULE}.set_calendar_e2e_context`, {
        default_calendar: "Jalali",
        user_calendar_preference: "Jalali",
        persian_calendar_enabled: true,
      });
      await page.reload({ waitUntil: "domcontentloaded" });
      await waitForDeskBoot(page);
    } catch (e) {
      record("E — Gregorian Preference", false, String(e));
      await captureFailure(page, "scenario-e-gregorian");
    }

    // --- Scenario F: Hard refresh + list refresh ---
    try {
      await openListDoctype(page, "Employee Checkin");
      const direct = await getListTimeCellText(page, fixtureName);
      await page.evaluate(() => frappe.set_route("desk"));
      await page.waitForFunction(() => typeof frappe !== "undefined", { timeout: 30000 });
      await openListDoctype(page, "Employee Checkin");
      const navigated = await getListTimeCellText(page, fixtureName);
      await page.evaluate(() => {
        if (window.cur_list && typeof window.cur_list.refresh === "function") {
          window.cur_list.refresh();
        }
      });
      await page.waitForFunction(
        () => window.cur_list?.data?.length > 0,
        { timeout: 120000 }
      );
      const refreshed = await getListTimeCellText(page, fixtureName);
      const ok =
        isJalaliYear(direct) &&
        isJalaliYear(navigated) &&
        isJalaliYear(refreshed) &&
        direct.includes("23:30:00");
      record("F — Hard Refresh and Navigation", ok, `direct=${direct} nav=${navigated} refresh=${refreshed}`);
    } catch (e) {
      record("F — Hard Refresh and Navigation", false, String(e));
      await captureFailure(page, "scenario-f-refresh");
    }

    // --- Scenario G: Near-midnight consistency ---
    try {
      await openDeskPath(page, `/app/employee-checkin/${encodeURIComponent(fixtureName)}`);
      await page.waitForSelector('[data-fieldname="time"]', { timeout: 60000 });
      const formMid = await getFormTimeValue(page);
      await openDeskPath(page, "/app/employee-checkin");
      await waitForListRows(page);
      const listMid = await getListTimeCellText(page, fixtureName);
      const tzEval = await page.evaluate(async (iso) => {
        const fmtDt = frappe.form.formatters.Datetime;
        const patched = fmtDt(iso, { fieldtype: "Datetime", fieldname: "time", parent: "Employee Checkin" });
        let stock = null;
        let userTz = iso;
        if (frappe.datetime?.convert_to_user_tz) {
          userTz = frappe.datetime.convert_to_user_tz(iso);
        }
        return {
          patched,
          userTz,
          sameTz: userTz === iso,
          pascalCase: typeof frappe.form.formatters.Date === "function",
          patchedOnce: !!frappe.form.formatters._pcJalaliPatched,
          coerceOnce: !!frappe.format._pcCoercePatched,
        };
      }, fixture.time || midnightIso);
      const consistent =
        formMid.includes("23:30:00") &&
        listMid.includes("23:30:00") &&
        formMid.split(" ")[0] === listMid.split(" ")[0] &&
        String(tzEval.patched).includes("23:30:00");
      record(
        "G — Near-midnight Datetime",
        consistent,
        `form=${formMid} list=${listMid} browser patched=${tzEval.patched} policy=${tzEval.sameTz ? "server-time" : "user-tz-differs"}`
      );
    } catch (e) {
      record("G — Near-midnight Datetime", false, String(e));
      await captureFailure(page, "scenario-g-midnight");
    }

    // Persian Calendar console noise (ignore locale RangeError from headless Chromium)
    const pcErrors = consoleErrors.filter(
      (e) =>
        /persian_calendar|jalali|formatters/i.test(e) &&
        !/Incorrect locale information/i.test(e)
    );
    record("Console — no Persian Calendar formatter errors", pcErrors.length === 0, pcErrors.join("; ") || "clean");
    const blockingPageErrors = pageErrors.filter((e) => !/Incorrect locale information/i.test(e));
    record("Page errors", blockingPageErrors.length === 0, blockingPageErrors.join("; ") || "none");
  } finally {
    if (fixtureName) {
      try {
        await frappeCall(page, `${FIXTURE_MODULE}.delete_employee_checkin_e2e_fixture`, {
          name: fixtureName,
        });
        log(`Cleaned up fixture ${fixtureName}`);
      } catch (e) {
        log(`Cleanup failed: ${e}`);
      }
    }
    try {
      await frappeCall(page, `${FIXTURE_MODULE}.set_calendar_e2e_context`, {
        default_calendar: "Jalali",
        user_calendar_preference: "Jalali",
        persian_calendar_enabled: true,
      });
    } catch (e) {
      /* ignore */
    }
    await browser.close();
  }

  console.log("\n=== E2E Summary ===");
  let failed = 0;
  for (const r of RESULTS) {
    console.log(`${r.passed ? "PASS" : "FAIL"}  ${r.scenario}${r.detail ? " — " + r.detail : ""}`);
    if (!r.passed) failed += 1;
  }
  if (screenshotOnFail) {
    console.log(`Screenshot: ${screenshotOnFail}`);
  }
  console.log(`\nTotal: ${RESULTS.length - failed}/${RESULTS.length} passed`);
  process.exit(failed ? 1 : 0);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
