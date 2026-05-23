#!/usr/bin/env python3
"""
Headless browser E2E for Gregorian + Persian Calendar (no Cypress/npm required).

Uses chromium-headless-shell + Chrome DevTools Protocol (websockets in bench venv).

Run from bench root:
  bench --site development.localhost set-config persian_calendar_e2e_fixtures 1
  ./env/bin/python apps/persian_calendar/e2e/run_cdp_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE_URL = os.environ.get("CYPRESS_BASE_URL", "http://development.localhost:8000").rstrip("/")
SITE = os.environ.get("FRAPPE_SITE", "development.localhost")
ADMIN_PASSWORD = os.environ.get("CYPRESS_ADMIN_PASSWORD", "admin")
CHROME = os.environ.get("CHROME_BIN", "/usr/bin/chromium-headless-shell")
CDP_PORT = int(os.environ.get("CDP_PORT", "9223"))
E2E_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FIXTURE = os.path.join(E2E_DIR, "fixtures", "Time Logs (46)(1).csv")

# A–G calendar mode matrix (persian_calendar_enabled, user_pref, site default_calendar)
CALENDAR_MODE_MATRIX: list[tuple[str, bool, str, str]] = [
	("A", True, "System Default", "Jalali"),
	("B", True, "System Default", "Gregorian"),
	("C", True, "Gregorian", "Jalali"),
	("D", True, "Jalali", "Jalali"),
	("E", False, "System Default", "Jalali"),
	("F", False, "Gregorian", "Jalali"),
	("G", False, "Jalali", "Jalali"),
]

# Grid picker click tests (app enabled): user/system × Gregorian/Jalali
GRID_PICKER_MODE_MATRIX: list[tuple[str, bool, str, str]] = [
	("B", True, "System Default", "Gregorian"),
	("C", True, "Gregorian", "Jalali"),
	("D", True, "Jalali", "Jalali"),
	("A", True, "System Default", "Jalali"),
]


class E2EFailure(Exception):
	pass


def http_json(url: str, data: dict | None = None, headers: dict | None = None, cookies: str = "") -> Any:
	req_headers = {"Content-Type": "application/json", **(headers or {})}
	if cookies:
		req_headers["Cookie"] = cookies
	body = None if data is None else json.dumps(data).encode()
	req = urllib.request.Request(url, data=body, headers=req_headers, method="POST" if data else "GET")
	try:
		with urllib.request.urlopen(req, timeout=120) as resp:
			raw = resp.read().decode()
			set_cookie = resp.headers.get("Set-Cookie", "")
			out = json.loads(raw) if raw else {}
			return out, set_cookie, resp.headers
	except urllib.error.HTTPError as e:
		raise E2EFailure(f"HTTP {e.code} for {url}: {e.read().decode()[:500]}") from e


import http.cookiejar


def frappe_login_sid() -> str:
	url = f"{BASE_URL}/api/method/login"
	payload = json.dumps({"usr": "Administrator", "pwd": ADMIN_PASSWORD}).encode()
	last_err: Exception | None = None
	for attempt in range(5):
		try:
			cj = http.cookiejar.CookieJar()
			opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
			req = urllib.request.Request(
				url,
				data=payload,
				headers={"Content-Type": "application/json"},
				method="POST",
			)
			with opener.open(req, timeout=180) as resp:
				body = resp.read().decode()
				if "Logged In" not in body and "message" not in body:
					raise E2EFailure(f"Login failed: {body[:300]}")
			for cookie in cj:
				if cookie.name == "sid":
					return cookie.value
			raise E2EFailure("Login succeeded but no sid cookie")
		except Exception as e:
			last_err = e
			time.sleep(2 * (attempt + 1))
	raise E2EFailure(f"Login failed after retries: {last_err}") from last_err


def jalali_bundle_url() -> str:
	assets_path = os.path.join(
		os.environ.get("BENCH_PATH", "/workspace/development/frappe-bench"),
		"sites/assets/assets.json",
	)
	with open(assets_path, encoding="utf-8") as f:
		data = json.load(f)
	path = data.get("jalali_support.bundle.js")
	if not path:
		raise E2EFailure("jalali_support.bundle.js not in assets.json")
	return f"{BASE_URL}{path}"


def _bench_cmd() -> str:
	return os.environ.get("BENCH_BIN", "/home/frappe/.local/bin/bench")


def bench_get_job_card() -> str:
	if os.environ.get("E2E_JOB_CARD"):
		return os.environ["E2E_JOB_CARD"]
	bench = _bench_cmd()
	bench_path = os.environ.get("BENCH_PATH", "/workspace/development/frappe-bench")
	exe = subprocess.run(
		[
			bench,
			"--site",
			SITE,
			"mariadb",
			"-e",
			"SELECT name FROM `tabJob Card` WHERE docstatus=0 ORDER BY modified DESC LIMIT 1;",
		],
		capture_output=True,
		text=True,
		cwd=bench_path,
		timeout=60,
	)
	if exe.returncode != 0:
		raise E2EFailure(exe.stderr)
	for line in exe.stdout.splitlines():
		line = line.strip()
		if line and line != "name":
			return line
	raise E2EFailure("No open Job Card found for E2E")


def bench_get_draft_purchase_receipt() -> str:
	if os.environ.get("E2E_PURCHASE_RECEIPT"):
		return os.environ["E2E_PURCHASE_RECEIPT"]
	bench = _bench_cmd()
	bench_path = os.environ.get("BENCH_PATH", "/workspace/development/frappe-bench")
	exe = subprocess.run(
		[
			bench,
			"--site",
			SITE,
			"mariadb",
			"-e",
			"SELECT name FROM `tabPurchase Receipt` WHERE docstatus=0 ORDER BY modified DESC LIMIT 1;",
		],
		capture_output=True,
		text=True,
		cwd=bench_path,
		timeout=60,
	)
	if exe.returncode != 0:
		raise E2EFailure(exe.stderr)
	for line in exe.stdout.splitlines():
		line = line.strip()
		if line and line != "name":
			return line
	return ""


def bench_set_calendar_test_context(
	default_calendar: str,
	user_calendar_preference: str = "System Default",
	persian_calendar_enabled: bool | None = True,
) -> None:
	"""Set Administrator calendar preference and Jalali Settings default_calendar."""
	bench = _bench_cmd()
	bench_path = os.environ.get("BENCH_PATH", "/workspace/development/frappe-bench")
	enabled_arg = "None" if persian_calendar_enabled is None else ("True" if persian_calendar_enabled else "False")
	exe = subprocess.run(
		[
			bench,
			"--site",
			SITE,
			"execute",
			"frappe.get_attr('persian_calendar.jalali_support.e2e_fixtures.set_calendar_e2e_context')"
			f"({json.dumps(default_calendar)}, {json.dumps(user_calendar_preference)}, {enabled_arg})",
		],
		capture_output=True,
		text=True,
		cwd=bench_path,
		timeout=120,
	)
	if exe.returncode != 0:
		raise E2EFailure(f"bench calendar context failed:\n{exe.stdout}\n{exe.stderr}")
	bench_path = os.environ.get("BENCH_PATH", "/workspace/development/frappe-bench")
	clear = subprocess.run(
		[_bench_cmd(), "--site", SITE, "clear-cache"],
		capture_output=True,
		text=True,
		cwd=bench_path,
		timeout=120,
	)
	if clear.returncode != 0:
		raise E2EFailure(f"bench clear-cache failed:\n{clear.stdout}\n{clear.stderr}")


def bench_get_default_employee() -> str:
	if os.environ.get("E2E_EMPLOYEE"):
		return os.environ["E2E_EMPLOYEE"]
	# Avoid slow mariadb during CDP runs; override with E2E_EMPLOYEE when needed.
	return os.environ.get("E2E_DEFAULT_EMPLOYEE", "HR-EMP-00075")


def load_time_logs_csv_text() -> str:
	if not os.path.isfile(CSV_FIXTURE):
		raise E2EFailure(f"Missing CSV fixture: {CSV_FIXTURE}")
	with open(CSV_FIXTURE, encoding="utf-8") as f:
		return f.read()


def bench_create_fixture() -> dict:
	"""Optional; prefer bench_get_job_card when manufacturing fixture is heavy."""
	if os.environ.get("E2E_SKIP_FIXTURE_CREATE"):
		return {"job_card": bench_get_job_card()}
	bench = _bench_cmd()
	bench_path = os.environ.get("BENCH_PATH", "/workspace/development/frappe-bench")
	exe = subprocess.run(
		[
			bench,
			"--site",
			SITE,
			"execute",
			"frappe.get_attr('persian_calendar.jalali_support.e2e_fixtures.create_job_card_time_log_fixture')()",
		],
		capture_output=True,
		text=True,
		cwd=bench_path,
		timeout=300,
	)
	if exe.returncode != 0:
		raise E2EFailure(f"Fixture create failed:\n{exe.stdout}\n{exe.stderr}")
	for line in reversed(exe.stdout.splitlines()):
		line = line.strip()
		if line.startswith("{"):
			return json.loads(line)
	raise E2EFailure(f"Could not parse fixture JSON:\n{exe.stdout}")


class CDPClient:
	def __init__(self, ws_url: str):
		self.ws_url = ws_url
		self.ws = None
		self._id = 0
		self._pending: dict[int, asyncio.Future] = {}

	async def connect(self):
		import websockets

		self.ws = await websockets.connect(self.ws_url, max_size=50 * 1024 * 1024)
		asyncio.create_task(self._reader())

	async def _reader(self):
		assert self.ws
		async for message in self.ws:
			msg = json.loads(message)
			if "id" in msg and msg["id"] in self._pending:
				self._pending[msg["id"]].set_result(msg)

	async def call(self, method: str, params: dict | None = None) -> Any:
		self._id += 1
		msg_id = self._id
		fut = asyncio.get_event_loop().create_future()
		self._pending[msg_id] = fut
		await self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
		resp = await asyncio.wait_for(fut, timeout=120)
		if "error" in resp:
			raise E2EFailure(f"CDP {method}: {resp['error']}")
		return resp.get("result")

	async def evaluate(self, expression: str) -> Any:
		res = await self.call(
			"Runtime.evaluate",
			{
				"expression": expression,
				"awaitPromise": True,
				"returnByValue": True,
			},
		)
		if res.get("exceptionDetails"):
			raise E2EFailure(f"JS error: {res['exceptionDetails']}")
		return res.get("result", {}).get("value")

	async def close(self):
		if self.ws:
			await self.ws.close()

	async def click_at(self, x: float, y: float) -> None:
		for event_type in ("mousePressed", "mouseReleased"):
			await self.call(
				"Input.dispatchMouseEvent",
				{
					"type": event_type,
					"x": x,
					"y": y,
					"button": "left",
					"clickCount": 1,
				},
			)


E2E_CONSOLE_HOOK_JS = """
(function () {
	if (window.__pcE2EConsoleHooked) return;
	window.__pcE2EConsoleHooked = true;
	window.__pcE2EConsoleErrors = [];
	window.__pcMomentDeprecation = [];
	window.__pcRawCsvInFormatter = [];
	var origWarn = console.warn;
	console.warn = function () {
		var msg = Array.prototype.slice.call(arguments).join(' ');
		if (/moment/i.test(msg) && /deprecat/i.test(msg)) {
			window.__pcMomentDeprecation.push(msg);
		}
		if (/4\\/20\\/2026|4\\/20\\/2026 8:30/i.test(msg)) {
			window.__pcRawCsvInFormatter.push(msg);
		}
		return origWarn.apply(console, arguments);
	};
	window.addEventListener("error", function (ev) {
		var msg =
			ev.message ||
			(ev.error && (ev.error.stack || ev.error.message)) ||
			String(ev.error || "error");
		window.__pcE2EConsoleErrors.push(msg);
	});
	window.addEventListener("unhandledrejection", function (ev) {
		window.__pcE2EConsoleErrors.push(String(ev.reason || ev));
	});
})();
"""

E2E_SAVE_HOOKS_JS = """
(function () {
	function __pcRecordSavedocsFromXhr(xhr, url) {
		if (String(url || '').indexOf('savedocs') < 0) return;
		window.__pcE2ELastSavedocs = {
			ok: xhr.status >= 200 && xhr.status < 300,
			httpStatus: xhr.status,
			body: (xhr.responseText || '').slice(0, 4000)
		};
	}
	if (!window.__pcJquerySavedocsHooked) {
		window.__pcJquerySavedocsHooked = true;
		$(document).on('ajaxComplete', function(ev, xhr, settings) {
			__pcRecordSavedocsFromXhr(xhr, settings && settings.url);
		});
	}
	if (!window.__pcXhrSavedocsHooked) {
		window.__pcXhrSavedocsHooked = true;
		var open = XMLHttpRequest.prototype.open;
		var send = XMLHttpRequest.prototype.send;
		XMLHttpRequest.prototype.open = function(method, url) {
			this.__pcUrl = url;
			return open.apply(this, arguments);
		};
		XMLHttpRequest.prototype.send = function() {
			var xhr = this;
			xhr.addEventListener('load', function() {
				__pcRecordSavedocsFromXhr(xhr, xhr.__pcUrl);
			});
			return send.apply(this, arguments);
		};
	}
	if (!window.__pcE2ESaveHooked) {
		window.__pcE2ESaveHooked = true;
		var origCall = frappe.call;
		frappe.call = function(opts) {
			var method = opts && (opts.method || '');
			if (String(method).indexOf('savedocs') >= 0) {
				var origErr = opts.error;
				opts.error = function(r) {
					var xhr = r && r.xhr;
					__pcRecordSavedocsFromXhr(
						xhr || { status: (r && r.status) || 500, responseText: (r && r.message) || '' },
						'/api/method/frappe.desk.form.save.savedocs'
					);
					if (origErr) return origErr(r);
				};
				var origCb = opts.callback;
				opts.callback = function(r) {
					__pcRecordSavedocsFromXhr(
						{ status: 200, responseText: JSON.stringify(r || {}) },
						'/api/method/frappe.desk.form.save.savedocs'
					);
					if (origCb) return origCb(r);
				};
			}
			return origCall.apply(this, arguments);
		};
	}
})();
"""

FORBIDDEN_CONSOLE_MARKERS = (
	"frm.wrapper.find is not a function",
	"TypeError",
)

# Unrelated browser / desk noise (not Persian Calendar regressions)
BENIGN_CONSOLE_PATTERNS = (
	"NotAllowedError: play()",
)


def _is_benign_console_error(err: str) -> bool:
	for pattern in BENIGN_CONSOLE_PATTERNS:
		if pattern in err:
			return True
	return False


async def assert_console_clean(cdp_page: CDPClient, context: str) -> None:
	result = await cdp_page.evaluate(
		"""
		(function () {
			return {
				errors: window.__pcE2EConsoleErrors || [],
				count: (window.__pcE2EConsoleErrors || []).length,
			};
		})();
		"""
	)
	errors = [str(e) for e in (result.get("errors") or [])]
	relevant = [e for e in errors if not _is_benign_console_error(e)]
	if not relevant:
		benign_n = len(errors) - len(relevant)
		suffix = f" ({benign_n} benign ignored)" if benign_n else ""
		print(f"Console OK ({context}): 0 relevant uncaught errors{suffix}")
		return
	text = "\n".join(relevant)
	for err_s in relevant:
		for marker in FORBIDDEN_CONSOLE_MARKERS:
			if marker in err_s:
				raise E2EFailure(
					f"Forbidden console error at {context} ({marker}):\n{err_s}\n\nAll relevant:\n{text}"
				)
	raise E2EFailure(f"Uncaught console errors at {context} ({len(relevant)}):\n{text}")


def _gregorian_picker_e2e_modes(user_pref: str, default_cal: str) -> bool:
	return user_pref == "Gregorian" or (
		user_pref == "System Default" and default_cal == "Gregorian"
	)


def expected_effective_mode(
	persian_calendar_enabled: bool, user_pref: str, default_cal: str
) -> str:
	if user_pref in ("Jalali", "Persian"):
		return "Jalali"
	if user_pref == "Gregorian":
		return "Gregorian"
	if not persian_calendar_enabled:
		return "Gregorian"
	return "Gregorian" if default_cal == "Gregorian" else "Jalali"


def _client_boot_apply_js(
	persian_calendar_enabled: bool, user_pref: str, default_cal: str
) -> str:
	"""Apply calendar boot + runtime after desk reload (enabled must be set before pref sync)."""
	return f"""
	(function() {{
		try {{
			localStorage.clear();
			sessionStorage.clear();
		}} catch (e) {{}}
		frappe.boot.persian_calendar = frappe.boot.persian_calendar || {{}};
		frappe.boot.persian_calendar.enabled = {json.dumps(persian_calendar_enabled)};
		frappe.boot.persian_calendar.calendar_preference = {json.dumps(user_pref)};
		frappe.boot.persian_calendar.default_calendar = {json.dumps(default_cal)};
		var rt = frappe.persian_calendar.runtime;
		if (rt.invalidateCalendarSettingsCache) rt.invalidateCalendarSettingsCache();
		var pref = {json.dumps(user_pref)};
		if (!{json.dumps(persian_calendar_enabled)}) {{
			frappe.boot.persian_calendar.enabled = false;
		}}
		if (pref === 'System Default' && rt.configureSystemDefaultCalendarSync) {{
			rt.configureSystemDefaultCalendarSync({json.dumps(default_cal)});
		}} else if (rt.updateBootFromUserCalendarPreference) {{
			rt.updateBootFromUserCalendarPreference(pref);
		}}
		if (rt.syncBootDisplayCalendar) rt.syncBootDisplayCalendar();
		return {{
			boot: frappe.boot.persian_calendar,
			debug: rt.getCalendarPreferenceDebugSync ? rt.getCalendarPreferenceDebugSync() : null,
			effective: rt.getEffectiveCalendarModeSync ? rt.getEffectiveCalendarModeSync() : null
		}};
	}})();
	"""


async def assert_effective_mode_at_mode_start(
	cdp_page: CDPClient,
	mode_label: str,
	expected: str,
	persian_calendar_enabled: bool,
	user_pref: str,
	default_cal: str,
) -> None:
	"""Assert effective mode matches matrix row; dump server/client state on failure."""
	await cdp_page.evaluate(
		_client_boot_apply_js(persian_calendar_enabled, user_pref, default_cal)
	)
	diag = await cdp_page.evaluate(
		f"""
		(function() {{
			var rt = frappe.persian_calendar.runtime;
			var ls = {{}};
			try {{
				for (var i = 0; i < localStorage.length; i++) {{
					var k = localStorage.key(i);
					if (k) ls[k] = localStorage.getItem(k);
				}}
			}} catch (e) {{}}
			var server = null;
			try {{
				frappe.call({{
					method: 'persian_calendar.jalali_support.e2e_fixtures.get_calendar_e2e_debug_state',
					async: false,
					callback: function(r) {{ server = r.message; }}
				}});
			}} catch (e) {{ server = {{ error: String(e) }}; }}
			return {{
				effective: rt.getEffectiveCalendarModeSync(),
				boot_persian_calendar: frappe.boot.persian_calendar,
				debug: rt.getCalendarPreferenceDebugSync(),
				runtime_settings_cache: rt.getSettingsCache ? rt.getSettingsCache() : null,
				localStorage: ls,
				server: server
			}};
		}})();
		"""
	)
	actual = diag.get("effective")
	if actual == expected:
		print(f"Mode {mode_label}: effective={actual} (boot OK)")
		return
	raise E2EFailure(
		f"Mode {mode_label}: expected effective {expected!r}, got {actual!r}. "
		f"Full dump:\\n{json.dumps(diag, indent=2, default=str)}"
	)


async def isolate_calendar_mode_for_e2e(
	cdp_page: CDPClient,
	mode_label: str,
	persian_calendar_enabled: bool,
	user_pref: str,
	default_cal: str,
) -> None:
	"""Server DB + cache, client storage, hard reload, boot apply, effective assertion."""
	expected = expected_effective_mode(persian_calendar_enabled, user_pref, default_cal)
	bench_set_calendar_test_context(default_cal, user_pref, persian_calendar_enabled)
	await cdp_page.evaluate(
		"""
		(function() {
			try {
				localStorage.clear();
				sessionStorage.clear();
			} catch (e) {}
		})();
		"""
	)
	await cdp_page.call("Page.reload", {"ignoreCache": True})
	for _ in range(100):
		await asyncio.sleep(0.5)
		ready = await cdp_page.evaluate("typeof frappe !== 'undefined' && !!frappe.boot")
		if ready:
			break
	else:
		raise E2EFailure(f"{mode_label}: desk did not reload after isolation")
	await asyncio.sleep(2)
	bundle_url = jalali_bundle_url() + f"?_={int(time.time())}"
	await cdp_page.evaluate(
		f"""
		(function() {{
			var s = document.createElement('script');
			s.src = {json.dumps(bundle_url)};
			document.head.appendChild(s);
		}})();
		"""
	)
	await asyncio.sleep(4)
	await cdp_page.evaluate(E2E_CONSOLE_HOOK_JS)
	await cdp_page.evaluate(E2E_SAVE_HOOKS_JS)
	await assert_effective_mode_at_mode_start(
		cdp_page, mode_label, expected, persian_calendar_enabled, user_pref, default_cal
	)


def _picker_nav_title_is_april_2026(title: str) -> bool:
	t = (title or "").strip()
	if re.search(r"\bMay\b", t, re.I):
		return False
	if re.search(r"April", t, re.I):
		return True
	if re.search(r"2026", t) and re.search(r"(^|[^\d])04([^\d]|$)|Apr", t, re.I):
		return True
	return False


async def assert_gregorian_datetime_picker_month(
	cdp_page: CDPClient,
	mode_label: str,
	row_idx: int,
	fieldname: str,
	iso_value: str,
	expected_month0: int = 3,
	expected_year: int = 2026,
) -> None:
	"""April = month index 3; May = 4 (bug when DD-MM parsed as MM-DD)."""
	result = await cdp_page.evaluate(
		f"""
		(async function() {{
			var rowIdx = {row_idx};
			var fieldname = {json.dumps(fieldname)};
			var isoValue = {json.dumps(iso_value)};
			var row = cur_frm.doc.time_logs[rowIdx];
			if (!row) return {{ ok: false, error: 'no row' }};
			row[fieldname] = isoValue;
			cur_frm.refresh_field('time_logs');
			await new Promise(function(r) {{ setTimeout(r, 900); }});
			var grid = cur_frm.fields_dict.time_logs.grid;
			var gr = grid.grid_rows[rowIdx];
			if (!gr) return {{ ok: false, error: 'no grid row' }};
			if (gr.doc) gr.doc[fieldname] = isoValue;
			if (typeof gr.toggle_editable_row === 'function') {{
				gr.toggle_editable_row(true);
			}}
			await new Promise(function(r) {{ setTimeout(r, 700); }});
			var field = gr.on_grid_fields_dict && gr.on_grid_fields_dict[fieldname];
			var input = field && field.$input && field.$input.length ? field.$input[0] : null;
			if (!input) {{
				var $w = gr.wrapper && gr.wrapper.jquery ? gr.wrapper : $(gr.wrapper);
				input = $w.find('.frappe-control[data-fieldname="' + fieldname + '"] input')[0];
			}}
			if (!input) {{
				return {{ ok: false, error: 'no field input', keys: Object.keys(gr.on_grid_fields_dict || {{}}) }};
			}}
			field = field || {{ $input: $(input), datepicker: $(input).data('datepicker') }};
			if (!field.datepicker) {{
				field.datepicker = $(input).data('datepicker');
			}}
			input.focus();
			input.click();
			await new Promise(function(r) {{ setTimeout(r, 700); }});
			var dp = field.datepicker;
			if (!dp || !dp.viewDate) {{
				return {{
					ok: false,
					error: 'no datepicker or viewDate',
					visible: field.$input.val(),
					model: gr.doc && gr.doc[fieldname],
					jalali: !!field.jalaliDatepicker
				}};
			}}
			var m = dp.viewDate.getMonth();
			var y = dp.viewDate.getFullYear();
			var title = (dp.$datepicker && dp.$datepicker.find('.datepicker--nav-title').text()) || '';
			var sel = dp.selectedDates && dp.selectedDates[0];
			var selM = sel ? sel.getMonth() : m;
			var selY = sel ? sel.getFullYear() : y;
			function titleOkApril(t) {{
				t = (t || '').trim();
				if (/\\bMay\\b/i.test(t)) return false;
				if (/April/i.test(t)) return true;
				if (/2026/.test(t) && /(04|April|Apr)/i.test(t)) return true;
				return false;
			}}
			var titleOk = titleOkApril(title);
			return {{
				ok: m === {expected_month0} && y === {expected_year} && selM === {expected_month0} && selY === {expected_year} && titleOk,
				month: m,
				year: y,
				selMonth: selM,
				selYear: selY,
				title: title,
				titleOk: titleOk,
				visible: field.$input.val(),
				model: gr.doc[fieldname]
			}};
		}})();
		"""
	)
	print(f"{mode_label} picker {fieldname}: {result}")
	if not result or not result.get("ok"):
		raise E2EFailure(
			f"{mode_label}: picker must open month index {expected_month0} (April) "
			f"year {expected_year} for {iso_value}; got {result}"
		)
	if result.get("month") == 4 or result.get("selMonth") == 4:
		raise E2EFailure(
			f"{mode_label}: picker opened May (month index 4) for {fieldname}; "
			f"visible={result.get('visible')!r} model={result.get('model')!r}"
		)
	if expected_month0 == 3 and not result.get("titleOk"):
		raise E2EFailure(
			f"{mode_label}: picker nav title must show April 2026, not May: {result}"
		)


async def assert_grid_datetime_popup_on_user_click(
	cdp_page: CDPClient,
	mode_label: str,
	row_idx: int,
	fieldname: str,
	expect_jalali: bool,
	iso_value: str = "2026-04-20 12:00:00",
) -> None:
	"""CDP mouse click on grid Datetime input; assert visible native or Jalali popup."""
	prep = await cdp_page.evaluate(
		f"""
		(async function() {{
			var rowIdx = {row_idx};
			var fieldname = {json.dumps(fieldname)};
			var isoValue = {json.dumps(iso_value)};
			var row = cur_frm.doc.time_logs[rowIdx];
			if (!row) return {{ ok: false, error: 'no row' }};
			row[fieldname] = isoValue;
			cur_frm.refresh_field('time_logs');
			await new Promise(function(r) {{ setTimeout(r, 900); }});
			var grid = cur_frm.fields_dict.time_logs.grid;
			var gr = grid.grid_rows[rowIdx];
			if (!gr) return {{ ok: false, error: 'no grid row' }};
			if (typeof gr.toggle_editable_row === 'function') gr.toggle_editable_row(true);
			await new Promise(function(r) {{ setTimeout(r, 600); }});
			var field = gr.on_grid_fields_dict && gr.on_grid_fields_dict[fieldname];
			var input = field && field.$input && field.$input.length ? field.$input[0] : null;
			if (!input) {{
				var $w = gr.wrapper && gr.wrapper.jquery ? gr.wrapper : $(gr.wrapper);
				input = $w.find('.frappe-control[data-fieldname="' + fieldname + '"] input')[0];
			}}
			if (!input) return {{ ok: false, error: 'no input' }};
			field = field || {{ $input: $(input) }};
			input.scrollIntoView({{ block: 'center', inline: 'nearest' }});
			await new Promise(function(r) {{ setTimeout(r, 200); }});
			input.focus();
			input.click();
			await new Promise(function(r) {{ setTimeout(r, 1000); }});
			return {{ ok: true, fieldname: fieldname }};
		}})();
		"""
	)
	if not prep or not prep.get("ok"):
		raise E2EFailure(f"{mode_label}: grid {fieldname} prep failed: {prep}")
	result = await cdp_page.evaluate(
		f"""
		(function() {{
			function popupVisible() {{
				var air = false;
				var nodes = document.querySelectorAll('.datepicker');
				for (var i = 0; i < nodes.length; i++) {{
					var s = window.getComputedStyle(nodes[i]);
					if (s.display !== 'none' && s.visibility !== 'hidden' && nodes[i].offsetParent) {{
						air = true;
						break;
					}}
				}}
				var jalali = false;
				document.querySelectorAll('.jalali-datepicker').forEach(function(el) {{
					var s = window.getComputedStyle(el);
					if (s.display !== 'none' && s.visibility !== 'hidden') {{
						jalali = true;
					}}
				}});
				return {{ air: air, jalali: jalali }};
			}}
			var fieldname = {json.dumps(fieldname)};
			var gr = cur_frm.fields_dict.time_logs.grid.grid_rows[{row_idx}];
			var field = gr.on_grid_fields_dict[fieldname];
			var input = field && field.$input && field.$input[0];
			var dp = field && (field.datepicker || $(input).data('datepicker'));
			var vis = popupVisible();
			var jalaliInst = field && (field.jalaliDatepicker || (input && $(input).data('jalaliDatepickerInstance')));
			if (jalaliInst && jalaliInst.isOpen) {{
				vis.jalali = true;
			}}
			var title = '';
			var month = null;
			if (vis.air && dp && dp.$datepicker) {{
				title = (dp.$datepicker.find('.datepicker--nav-title').text() || '').trim();
				if (dp.viewDate) month = dp.viewDate.getMonth();
			}}
			function titleOkApril(t) {{
				t = (t || '').trim();
				if (/\\bMay\\b/i.test(t)) return false;
				if (/April/i.test(t)) return true;
				if (/2026/.test(t) && /(04|April|Apr)/i.test(t)) return true;
				return false;
			}}
			var expectJalali = {json.dumps(expect_jalali)};
			var ok = expectJalali ? vis.jalali && !vis.air : vis.air && !vis.jalali;
			if (!expectJalali && vis.air && !titleOkApril(title)) ok = false;
			return {{
				ok: ok,
				expectJalali: expectJalali,
				visibility: vis,
				jalaliIsOpen: !!(jalaliInst && jalaliInst.isOpen),
				readOnly: input && input.readOnly,
				disabled: input && input.disabled,
				hasDatepickerClass: input && input.classList.contains('hasDatepicker'),
				dataDatepicker: input && !!$(input).data('datepicker'),
				controlDatepicker: !!field.datepicker,
				jalaliOnField: !!field.jalaliDatepicker,
				effective: frappe.persian_calendar.runtime.getEffectiveCalendarModeSync(),
				title: title,
				month: month,
				visible: field.$input ? field.$input.val() : (input && input.value)
			}};
		}})();
		"""
	)
	print(f"{mode_label} grid click {fieldname}: {result}")
	if not result or not result.get("ok"):
		raise E2EFailure(
			f"{mode_label}: grid {fieldname} click must open "
			f"{'Jalali' if expect_jalali else 'native Air'} picker popup; got {result}"
		)
async def assert_effective_calendar_mode(
	cdp_page: CDPClient, mode_label: str, expected: str
) -> None:
	actual = await cdp_page.evaluate(
		"frappe.persian_calendar.runtime.getEffectiveCalendarModeSync()"
	)
	if actual != expected:
		raise E2EFailure(f"{mode_label}: expected effective {expected}, got {actual}")


async def assert_gregorian_main_datetime_picker(
	cdp_page: CDPClient,
	mode_label: str,
	fieldname: str,
	iso_value: str,
	expected_month0: int = 3,
	expected_year: int = 2026,
) -> None:
	result = await cdp_page.evaluate(
		f"""
		(async function() {{
			var fieldname = {json.dumps(fieldname)};
			var isoValue = {json.dumps(iso_value)};
			if (cur_frm.set_value) {{
				try {{ cur_frm.set_value(fieldname, isoValue); }} catch (e) {{}}
			}}
			if (cur_frm.doc) cur_frm.doc[fieldname] = isoValue;
			cur_frm.refresh_field(fieldname);
			await new Promise(function(r) {{ setTimeout(r, 900); }});
			var field = cur_frm.fields_dict[fieldname];
			var input = field && field.$input && field.$input.length
				? field.$input[0]
				: document.querySelector('.frappe-control[data-fieldname="' + fieldname + '"] input');
			if (!input) {{
				return {{ ok: false, error: 'no main field input', hasDict: !!field }};
			}}
			if (!field) {{
				field = {{ $input: $(input), datepicker: $(input).data('datepicker') }};
			}}
			input.focus();
			input.click();
			await new Promise(function(r) {{ setTimeout(r, 700); }});
			var dp = field.datepicker || $(input).data('datepicker');
			if (!dp || !dp.viewDate) {{
				return {{
					ok: false,
					error: 'no datepicker',
					visible: field.$input.val(),
					model: cur_frm.doc[fieldname],
					jalali: !!field.jalaliDatepicker
				}};
			}}
			var m = dp.viewDate.getMonth();
			var y = dp.viewDate.getFullYear();
			var title = (dp.$datepicker && dp.$datepicker.find('.datepicker--nav-title').text()) || '';
			var sel = dp.selectedDates && dp.selectedDates[0];
			var selM = sel ? sel.getMonth() : m;
			var selY = sel ? sel.getFullYear() : y;
			function titleOkApril(t) {{
				t = (t || '').trim();
				if (/\\bMay\\b/i.test(t)) return false;
				if (/April/i.test(t)) return true;
				if (/2026/.test(t) && /(04|April|Apr)/i.test(t)) return true;
				return false;
			}}
			var titleOk = titleOkApril(title);
			return {{
				ok: m === {expected_month0} && y === {expected_year} && selM === {expected_month0} && selY === {expected_year} && titleOk,
				month: m, year: y, selMonth: selM, selYear: selY, title: title, titleOk: titleOk,
				visible: field.$input.val(),
				model: cur_frm.doc[fieldname]
			}};
		}})();
		"""
	)
	print(f"{mode_label} main picker {fieldname}: {result}")
	if not result or not result.get("ok"):
		raise E2EFailure(f"{mode_label}: main {fieldname} picker April 2026 failed: {result}")
	if expected_month0 == 3 and not result.get("titleOk"):
		raise E2EFailure(f"{mode_label}: main {fieldname} nav title must be April 2026: {result}")


async def assert_jalali_picker_on_field(
	cdp_page: CDPClient,
	mode_label: str,
	context: str,
	fieldname: str,
	*,
	grid: bool = False,
	row_idx: int = 0,
	child_table: str = "time_logs",
) -> None:
	result = await cdp_page.evaluate(
		f"""
		(async function() {{
			var fieldname = {json.dumps(fieldname)};
			var grid = {json.dumps(grid)};
			var rowIdx = {row_idx};
			var childTable = {json.dumps(child_table)};
			var field;
			if (grid) {{
				var gridObj = cur_frm.fields_dict[childTable].grid;
				var gr = gridObj.grid_rows[rowIdx];
				if (typeof gr.toggle_editable_row === 'function') gr.toggle_editable_row(true);
				await new Promise(function(r) {{ setTimeout(r, 500); }});
				field = gr.on_grid_fields_dict[fieldname];
			}} else {{
				field = cur_frm.fields_dict[fieldname];
			}}
			if (!field || !field.$input || !field.$input.length) {{
				return {{ ok: false, error: 'no field' }};
			}}
			field.$input[0].focus();
			field.$input[0].click();
			await new Promise(function(r) {{ setTimeout(r, 600); }});
			return {{
				ok: !!field.jalaliDatepicker,
				jalali: !!field.jalaliDatepicker,
				visible: field.$input.val(),
				hasAir: !!(field.datepicker && field.datepicker.viewDate)
			}};
		}})();
		"""
	)
	if not result.get("ok"):
		raise E2EFailure(f"{mode_label} {context}: expected Jalali picker on {fieldname}: {result}")


async def assert_main_date_pr(
	cdp_page: CDPClient,
	mode_label: str,
	effective: str,
) -> None:
	await cdp_page.evaluate(
		"""
		(function() {
			var chk = document.querySelector(
				'.frappe-control[data-fieldname="edit_posting_date_and_time"] input[type="checkbox"]'
			);
			if (chk && !chk.checked) chk.click();
		})();
		"""
	)
	await asyncio.sleep(0.5)
	iso = "2026-04-20"
	await cdp_page.evaluate(f"cur_frm.set_value('posting_date', {json.dumps(iso)});")
	await asyncio.sleep(0.8)
	probe = await cdp_page.evaluate(
		"""
		(function() {
			var inp = document.querySelector('.frappe-control[data-fieldname="posting_date"] input');
			return {
				visible: inp ? inp.value : null,
				model: cur_frm.doc.posting_date
			};
		})();
		"""
	)
	pd_mod = str(probe.get("model") or "")
	pd_vis = str(probe.get("visible") or "")
	if "Invalid date" in pd_vis or "Invalid date" in pd_mod or "NaN" in pd_vis:
		raise E2EFailure(f"{mode_label} main_date: {probe}")
	if effective == "Jalali":
		if pd_mod[:10] != "2026-04-20":
			raise E2EFailure(f"{mode_label} main_date model must stay ISO: {probe}")
		if pd_vis and not re.match(r"^1[34]\d{2}-\d{2}-\d{2}$", pd_vis):
			raise E2EFailure(f"{mode_label} main_date visible expected Jalali: {probe}")
		await assert_jalali_picker_on_field(cdp_page, mode_label, "main_date", "posting_date")
	else:
		if pd_mod[:10] != "2026-04-20":
			raise E2EFailure(f"{mode_label} main_date model: {probe}")
		await assert_gregorian_main_datetime_picker(
			cdp_page, mode_label, "posting_date", iso + " 00:00:00"
		)


async def assert_main_time_pr(cdp_page: CDPClient, mode_label: str, effective: str) -> None:
	await cdp_page.evaluate("cur_frm.set_value('posting_time', '14:30:00');")
	await asyncio.sleep(0.6)
	probe = await cdp_page.evaluate(
		"""
		(function() {
			var inp = document.querySelector('.frappe-control[data-fieldname="posting_time"] input');
			return {
				visible: inp ? inp.value : null,
				model: cur_frm.doc.posting_time
			};
		})();
		"""
	)
	pt_vis = str(probe.get("visible") or "")
	pt_mod = str(probe.get("model") or "")
	if "Invalid date" in pt_vis or "Invalid date" in pt_mod or "NaN" in pt_vis:
		raise E2EFailure(f"{mode_label} main_time: {probe}")
	if pt_vis and not re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", pt_vis):
		raise E2EFailure(f"{mode_label} main_time not HH:mm:ss: {probe}")
	if effective == "Gregorian":
		await cdp_page.evaluate(
			"""
			(function() {
				var input = document.querySelector('.frappe-control[data-fieldname="posting_time"] input');
				if (input) { input.focus(); input.click(); }
			})();
			"""
		)
		await asyncio.sleep(0.4)


async def assert_grid_date_pr(cdp_page: CDPClient, mode_label: str, effective: str) -> None:
	result = await cdp_page.evaluate(
		"""
		(async function() {
			if (!cur_frm.doc.items || !cur_frm.doc.items.length) {
				return { ok: false, error: 'no items row' };
			}
			cur_frm.doc.items[0].schedule_date = '2026-04-20';
			cur_frm.refresh_field('items');
			await new Promise(function(r) { setTimeout(r, 800); });
			var grid = cur_frm.fields_dict.items.grid;
			var gr = grid.grid_rows[0];
			if (gr && typeof gr.toggle_editable_row === 'function') {
				gr.toggle_editable_row(true);
			}
			await new Promise(function(r) { setTimeout(r, 500); });
			var field = gr.on_grid_fields_dict && gr.on_grid_fields_dict.schedule_date;
			if (!field && gr && typeof gr.show_form === 'function') {
				gr.show_form();
				await new Promise(function(r) { setTimeout(r, 900); });
				field = cur_frm.cur_grid && cur_frm.cur_grid.grid_form && cur_frm.cur_grid.grid_form.fields_dict
					? cur_frm.cur_grid.grid_form.fields_dict.schedule_date
					: null;
			}
			var model = cur_frm.doc.items[0].schedule_date;
			var modelOk = model === '2026-04-20' || String(model || '').slice(0, 10) === '2026-04-20';
			if (!field || !field.$input || !field.$input.length) {
				return {
					ok: modelOk,
					skipPicker: true,
					model: model,
					effective: frappe.persian_calendar.runtime.getEffectiveCalendarModeSync()
				};
			}
			field.$input[0].focus();
			field.$input[0].click();
			await new Promise(function(r) { setTimeout(r, 700); });
			var jalali = !!field.jalaliDatepicker;
			var dp = field.datepicker;
			if (jalali) {
				return { ok: true, jalali: true, model: model, visible: field.$input.val() };
			}
			if (!dp || !dp.viewDate) {
				return { ok: false, error: 'no dp', model: model, visible: field.$input.val() };
			}
			var m = dp.viewDate.getMonth();
			var title = (dp.$datepicker && dp.$datepicker.find('.datepicker--nav-title').text()) || '';
			function titleOkApril(t) {
				t = (t || '').trim();
				if (/\\bMay\\b/i.test(t)) return false;
				if (/April/i.test(t)) return true;
				if (/2026/.test(t) && /(04|April|Apr)/i.test(t)) return true;
				return false;
			}
			return { ok: m === 3 && titleOkApril(title), month: m, title: title, model: model };
		})();
		"""
	)
	if not result.get("ok"):
		raise E2EFailure(f"{mode_label} grid_date schedule_date: {result}")
	if effective == "Jalali" and not result.get("skipPicker") and not result.get("jalali"):
		raise E2EFailure(f"{mode_label} grid_date expected Jalali picker: {result}")


async def assert_grid_time_via_datetime(
	cdp_page: CDPClient,
	mode_label: str,
	effective: str,
	job_card: str,
) -> None:
	"""Job Card grid has Datetime only; exercise time portion on to_time."""
	await cdp_page.evaluate(f"frappe.set_route('Form', 'Job Card', {json.dumps(job_card)});")
	await asyncio.sleep(3)
	await cdp_page.evaluate(
		"""
		(function() {
			var tab = document.querySelector('.form-tabs-list [data-fieldname="actual_time"], .nav-link[data-fieldname="actual_time"]');
			if (tab) tab.click();
		})();
		"""
	)
	await asyncio.sleep(0.8)
	probe = await cdp_page.evaluate(
		"""
		(function() {
			var row = cur_frm.doc.time_logs && cur_frm.doc.time_logs[0];
			if (!row) return { ok: false, error: 'no time_logs row' };
			row.to_time = '2026-04-20 15:45:00';
			cur_frm.refresh_field('time_logs');
			var grid = cur_frm.fields_dict.time_logs.grid;
			var gr = grid.grid_rows[0];
			if (gr && typeof gr.toggle_editable_row === 'function') gr.toggle_editable_row(true);
			var field = gr.on_grid_fields_dict.to_time;
			if (!field || !field.$input || !field.$input.length) return { ok: false, error: 'no to_time' };
			field.$input[0].focus();
			field.$input[0].click();
			return {
				ok: true,
				visible: field.$input.val(),
				model: row.to_time,
				jalali: !!field.jalaliDatepicker
			};
		})();
		"""
	)
	if not probe.get("ok"):
		raise E2EFailure(f"{mode_label} grid_time: {probe}")
	vis = str(probe.get("visible") or "")
	if "Invalid date" in vis or "NaN" in vis:
		raise E2EFailure(f"{mode_label} grid_time visible bad: {probe}")
	if effective == "Jalali" and not probe.get("jalali"):
		raise E2EFailure(f"{mode_label} grid_time expected Jalali on to_time: {probe}")


async def save_cur_frm_and_assert(
	cdp_page: CDPClient, mode_label: str, context: str
) -> None:
	await cdp_page.evaluate(E2E_SAVE_HOOKS_JS)
	await cdp_page.evaluate("window.__pcE2ESaveDone = null; window.__pcE2ELastSavedocs = null;")
	await cdp_page.evaluate(
		"""
		(function() {
			if (!cur_frm.is_dirty()) {
				cur_frm.dirty();
			}
			var done = function(ok, extra) {
				window.__pcE2ESaveDone = Object.assign({ ok: ok }, extra || {});
			};
			try {
				var p = cur_frm.save();
				if (p && typeof p.then === 'function') {
					p.then(function() { done(true); }).catch(function(e) {
						done(false, { error: String(e && e.message || e) });
					});
					return;
				}
			} catch (e) {}
			cur_frm.save(
				'Save',
				function(r) { done(!r.exc, { exc: r.exc }); },
				null,
				function() { done(false, { error: 'save_on_error' }); }
			);
		})();
		"""
	)
	save_meta = None
	for _ in range(120):
		await asyncio.sleep(0.5)
		save_meta = await cdp_page.evaluate(
			"""(() => ({ done: window.__pcE2ESaveDone, savedocs: window.__pcE2ELastSavedocs }))()"""
		)
		sd = save_meta.get("savedocs") or {}
		if sd.get("httpStatus") == 200:
			break
		if save_meta.get("done"):
			break
	else:
		diag = await cdp_page.evaluate(
			"""(() => ({
				validated: frappe.validated,
				dirty: cur_frm && cur_frm.is_dirty(),
				done: window.__pcE2ESaveDone,
				savedocs: window.__pcE2ELastSavedocs
			}))()"""
		)
		raise E2EFailure(f"{mode_label} {context}: save timeout {diag}")
	sd = save_meta.get("savedocs") or {}
	if sd.get("httpStatus") != 200:
		if not save_meta.get("done", {}).get("ok"):
			raise E2EFailure(f"{mode_label} {context}: save failed {save_meta}")
		raise E2EFailure(f"{mode_label} {context}: savedocs HTTP {sd.get('httpStatus')} {sd}")
	post = await cdp_page.evaluate(
		"""(() => ({
			is_dirty: cur_frm && cur_frm.is_dirty(),
			pills: Array.from(document.querySelectorAll('.indicator-pill')).map(function(el) {
				return (el.textContent || '').trim();
			})
		}))()"""
	)
	if post.get("is_dirty"):
		raise E2EFailure(f"{mode_label} {context}: dirty after save {post}")
	unsaved = await cdp_page.evaluate(
		"(() => (cur_frm && cur_frm.doc && cur_frm.doc.__unsaved) ? true : false)()"
	)
	if unsaved:
		raise E2EFailure(f"{mode_label} {context}: doc.__unsaved after save")


async def run_calendar_mode_acceptance(
	cdp_page: CDPClient,
	job_card: str,
	pr_name: str,
	csv_text: str,
	label: str,
	enabled: bool,
	user_pref: str,
	default_cal: str,
	default_employee: str,
) -> dict[str, str]:
	"""Full acceptance for one A–G mode; returns per-context status."""
	expected = expected_effective_mode(enabled, user_pref, default_cal)
	ctx: dict[str, str] = {}

	await isolate_calendar_mode_for_e2e(
		cdp_page, label, enabled, user_pref, default_cal
	)
	ctx["effective_mode"] = "PASS"

	await _run_job_card_csv_body(
		cdp_page,
		job_card,
		csv_text,
		label,
		user_pref,
		default_cal,
		default_employee,
		enabled,
	)
	ctx["csv_import"] = "PASS"
	ctx["grid_datetime"] = "PASS"
	ctx["jc_save"] = "PASS"

	await cdp_page.evaluate(
		"""
		(function() {
			var tab = document.querySelector('.form-tabs-list [data-fieldname="actual_time"], .nav-link[data-fieldname="actual_time"]');
			if (tab) tab.click();
		})();
		"""
	)
	await asyncio.sleep(0.5)
	await cdp_page.evaluate(
		"""
		(function() {
			var el = document.querySelector('.frappe-control[data-fieldname="actual_start_date"]');
			if (el) el.scrollIntoView({ block: 'center' });
		})();
		"""
	)
	await asyncio.sleep(0.3)
	field_order = (
		["expected_start_date", "actual_end_date", "actual_start_date"]
		if expected == "Gregorian"
		else ["actual_start_date", "expected_start_date", "actual_end_date"]
	)
	main_dt_field = await cdp_page.evaluate(
		f"""
		(function() {{
			var names = {json.dumps(field_order)};
			for (var i = 0; i < names.length; i++) {{
				var fn = names[i];
				var field = cur_frm.fields_dict[fn];
				if (field && field.refresh) field.refresh();
				var inp = document.querySelector('.frappe-control[data-fieldname="' + fn + '"] input');
				if (inp) return fn;
			}}
			return null;
		}})();
		"""
	)
	await asyncio.sleep(0.8)
	if not main_dt_field:
		probe = await cdp_page.evaluate(
			"""(() => ({
				actual_start_date: cur_frm.doc.actual_start_date,
				expected_start_date: cur_frm.doc.expected_start_date
			}))()"""
		)
		if str(probe.get("actual_start_date") or "").startswith("2026-"):
			ctx["main_datetime"] = "PASS (read-only; model ISO)"
		else:
			raise E2EFailure(f"{label}: no main Datetime input; doc={probe}")
	else:
		iso_val = "2026-04-20 12:00:00"
		if expected == "Jalali":
			await cdp_page.evaluate(f"cur_frm.set_value({json.dumps(main_dt_field)}, {json.dumps(iso_val)});")
			await asyncio.sleep(0.8)
			await assert_jalali_picker_on_field(cdp_page, label, "main_datetime", main_dt_field)
		else:
			await assert_gregorian_main_datetime_picker(cdp_page, label, main_dt_field, iso_val)
		ctx["main_datetime"] = "PASS"

	try:
		await cdp_page.evaluate(f"frappe.set_route('Form', 'Purchase Receipt', {json.dumps(pr_name)});")
		await asyncio.sleep(4)
		await assert_effective_mode_at_mode_start(
			cdp_page, f"{label} (PR)", expected, enabled, user_pref, default_cal
		)
		await assert_main_date_pr(cdp_page, label, expected)
		ctx["main_date_pr"] = "PASS"
		await assert_main_time_pr(cdp_page, label, expected)
		ctx["main_time_pr"] = "PASS"
		await cdp_page.evaluate(f"frappe.set_route('Form', 'Purchase Receipt', {json.dumps(pr_name)});")
		await asyncio.sleep(3)
		await assert_grid_date_pr(cdp_page, label, expected)
		ctx["grid_date_pr"] = "PASS"
		await cdp_page.evaluate(
			"""
			(function() {
				return frappe.call({
					method: 'frappe.desk.form.load.getdoc',
					args: { doctype: cur_frm.doctype, name: cur_frm.docname },
					async: false,
					callback: function(r) {
						frappe.model.sync(r.message);
						cur_frm.refresh();
					}
				});
			})();
			"""
		)
		await asyncio.sleep(2)
		await cdp_page.evaluate(
			"""
			(function() {
				var chk = document.querySelector(
					'.frappe-control[data-fieldname="edit_posting_date_and_time"] input[type="checkbox"]'
				);
				if (chk && !chk.checked) chk.click();
				var t = String(cur_frm.doc.posting_time || '12:00:00');
				var parts = t.split(':');
				var h = parseInt(parts[0], 10) || 0;
				var m = (parseInt(parts[1], 10) || 0);
				m = (m + 1) % 60;
				var s = String((parseInt(parts[2], 10) || 0) + 1).padStart(2, '0');
				cur_frm.set_value('posting_time', h + ':' + String(m).padStart(2, '0') + ':' + s);
				cur_frm.dirty();
			})();
			"""
		)
		await asyncio.sleep(0.5)
		await save_cur_frm_and_assert(cdp_page, label, "PR save")
		ctx["pr_save"] = "PASS"
		await assert_console_clean(cdp_page, f"{label} PR")
	except E2EFailure as e:
		e.acceptance_ctx = ctx  # type: ignore[attr-defined]
		raise

	await assert_grid_time_via_datetime(cdp_page, label, expected, job_card)
	ctx["grid_time"] = "PASS"

	return ctx


def print_acceptance_matrix_table(rows: list[tuple[str, dict[str, str]]]) -> None:
	contexts = [
		"effective_mode",
		"csv_import",
		"main_datetime",
		"main_date_pr",
		"main_time_pr",
		"grid_datetime",
		"grid_date_pr",
		"grid_time",
		"jc_save",
		"pr_save",
	]
	print("\n=== Calendar acceptance matrix (A–G) ===")
	header = "Mode | " + " | ".join(contexts) + " | OVERALL"
	print(header)
	print("-" * len(header))
	def _pass_cell(val: str | None) -> bool:
		return val == "PASS" or (isinstance(val, str) and str(val).startswith("PASS"))

	for label, ctx in rows:
		overall = "PASS" if all(_pass_cell(ctx.get(c)) for c in contexts) else "FAIL"
		cells = [ctx.get(c, "—") for c in contexts]
		print(f"{label} | " + " | ".join(cells) + f" | {overall}")
	print("=== end matrix ===\n")


async def _run_job_card_csv_body(
	cdp_page: CDPClient,
	job_card: str,
	csv_text: str,
	mode_label: str,
	user_pref: str,
	default_cal: str,
	default_employee: str,
	persian_calendar_enabled: bool = True,
) -> None:
	"""Job Card CSV import + picker + save (caller must run isolate_calendar_mode_for_e2e first)."""
	await cdp_page.evaluate(
		"""
		(function() {
			window.__pcMomentDeprecation = [];
			window.__pcRawCsvInFormatter = [];
			window.__persianCalendarInvalidDateLog = [];
		})();
		"""
	)
	await cdp_page.evaluate(
		f"frappe.set_route('Form', 'Job Card', {json.dumps(job_card)});"
	)
	await asyncio.sleep(4)
	await cdp_page.evaluate(
		"""
		(function() {
			var tab = document.querySelector('.form-tabs-list [data-fieldname="actual_time"], .nav-link[data-fieldname="actual_time"]');
			if (tab) tab.click();
		})();
		"""
	)
	await asyncio.sleep(1)
	csv_js = json.dumps(csv_text)
	import_result = await cdp_page.evaluate(
		f"""
		(function() {{
			var csvText = {csv_js};
			var data = frappe.utils.csv_to_array(csvText);
			var fieldnames = data[2];
			var me = cur_frm.fields_dict.time_logs.grid;
			cur_frm.clear_table('time_logs');
			var imported = [];
			$.each(data, function(i, row) {{
				if (i <= 6) return;
				var blank_row = true;
				$.each(row, function(ci, value) {{
					if (value) {{ blank_row = false; return false; }}
				}});
				if (!blank_row) {{
					var d = cur_frm.add_child('time_logs');
					$.each(row, function(ci, value) {{
						var fieldname = fieldnames[ci];
						var df = frappe.meta.get_docfield(me.df.options, fieldname);
						if (df) d[fieldname] = value;
					}});
					imported.push({{ from_time: d.from_time, to_time: d.to_time }});
				}}
			}});
			cur_frm.refresh_field('time_logs');
			return {{
				imported: imported,
				rowCount: cur_frm.doc.time_logs.length,
				models: (cur_frm.doc.time_logs || []).map(function(r) {{
					return {{ from_time: r.from_time, to_time: r.to_time, completed_qty: r.completed_qty }};
				}}),
				momentWarn: window.__pcMomentDeprecation || [],
				rawCsvWarn: window.__pcRawCsvInFormatter || [],
				effective: frappe.persian_calendar.runtime.getEffectiveCalendarModeSync()
			}};
		}})();
		"""
	)
	print(f"Calendar mode {mode_label}: import={import_result}")
	exp_eff = expected_effective_mode(persian_calendar_enabled, user_pref, default_cal)
	if import_result.get("effective") != exp_eff:
		await assert_effective_mode_at_mode_start(
			cdp_page,
			f"{mode_label} (import)",
			exp_eff,
			persian_calendar_enabled,
			user_pref,
			default_cal,
		)
	if import_result.get("momentWarn"):
		raise E2EFailure(f"{mode_label}: moment deprecation with raw CSV: {import_result.get('momentWarn')}")
	if import_result.get("rawCsvWarn"):
		raise E2EFailure(f"{mode_label}: raw CSV reached formatter: {import_result.get('rawCsvWarn')}")
	for row in import_result.get("models") or []:
		for key in ("from_time", "to_time"):
			val = str(row.get(key) or "")
			if "Invalid date" in val or "NaN" in val:
				raise E2EFailure(f"{mode_label}: bad model {key}={val}")
			if val and "/" in val:
				raise E2EFailure(f"{mode_label}: raw M/D still in model {key}={val}")
			if val and not val.startswith("2026-"):
				raise E2EFailure(f"{mode_label}: model not ISO {key}={val}")
	await assert_console_clean(cdp_page, f"{mode_label} after CSV import")
	exp_pick = expected_effective_mode(persian_calendar_enabled, user_pref, default_cal)
	await assert_grid_datetime_popup_on_user_click(
		cdp_page, mode_label, 0, "from_time", exp_pick == "Jalali", "2026-04-20 12:00:00"
	)
	await assert_grid_datetime_popup_on_user_click(
		cdp_page, mode_label, 0, "to_time", exp_pick == "Jalali", "2026-04-20 13:00:00"
	)
	row_count = int(import_result.get("rowCount") or 0)
	for row_idx in range(min(row_count, 3)):
		for field in ("from_time", "to_time"):
			await cdp_page.evaluate(
				f"""
				(function() {{
					var grid = cur_frm.fields_dict.time_logs.grid;
					var gr = grid.grid_rows[{row_idx}];
					var $w = gr.wrapper && gr.wrapper.jquery ? gr.wrapper : $(gr.wrapper);
					var input = $w.find('.frappe-control[data-fieldname="{field}"] input')[0];
					if (input) {{ input.focus(); input.click(); }}
				}})();
				"""
			)
			await asyncio.sleep(0.4)
	await cdp_page.evaluate(
		f"""
		(function() {{
			return frappe.call({{
				method: 'persian_calendar.jalali_support.e2e_fixtures.prepare_work_order_for_job_card_save',
				args: {{ job_card: {json.dumps(job_card)} }},
				async: false
			}});
		}})();
		"""
	)
	await cdp_page.evaluate("window.__pcE2ESaveDone = null; window.__pcE2ELastSavedocs = null;")
	await cdp_page.evaluate(
		f"""
		(function() {{
			var emp = {json.dumps(default_employee)};
			(cur_frm.doc.time_logs || []).forEach(function(r) {{
				if (!r.employee) r.employee = emp;
			}});
			if (cur_frm.doc.time_logs && cur_frm.doc.time_logs.length) {{
				cur_frm.dirty();
			}}
			cur_frm.save(
				'Save',
				function(r) {{
					window.__pcE2ESaveDone = {{ ok: !r.exc, exc: r.exc, validated: frappe.validated }};
				}},
				null,
				function() {{
					window.__pcE2ESaveDone = {{
						ok: false,
						error: 'save_on_error',
						validated: frappe.validated
					}};
				}}
			);
		}})();
		"""
	)
	for _ in range(120):
		await asyncio.sleep(0.5)
		if await cdp_page.evaluate("window.__pcE2ESaveDone"):
			break
	else:
		raise E2EFailure(f"{mode_label}: save timeout")
	save_meta = await cdp_page.evaluate(
		"""(() => ({ done: window.__pcE2ESaveDone, savedocs: window.__pcE2ELastSavedocs }))()"""
	)
	sd = save_meta.get("savedocs") or {}
	http_status = sd.get("httpStatus")
	body = str(sd.get("body") or "")
	print(f"Calendar mode {mode_label}: savedocs status={http_status} body_head={body[:800]!r} done={save_meta.get('done')}")
	if not save_meta.get("done", {}).get("ok"):
		raise E2EFailure(f"{mode_label}: save failed {save_meta}")
	if http_status is None:
		raise E2EFailure(f"{mode_label}: savedocs HTTP status not captured (form save reported ok). meta={save_meta}")
	if http_status >= 500:
		raise E2EFailure(f"{mode_label}: savedocs HTTP {http_status} body={body[:4000]}")
	if body.lstrip().lower().startswith("<!doctype") or body.lstrip().lower().startswith("<html"):
		raise E2EFailure(f"{mode_label}: savedocs HTML error body={body[:4000]}")
	if http_status != 200:
		raise E2EFailure(f"{mode_label}: savedocs HTTP {http_status} body={body[:4000]}")
	await asyncio.sleep(2)
	post = await cdp_page.evaluate(
		"""(() => ({ is_dirty: cur_frm && cur_frm.is_dirty(), effective: frappe.persian_calendar.runtime.getEffectiveCalendarModeSync() }))()"""
	)
	if post.get("is_dirty"):
		raise E2EFailure(f"{mode_label}: form dirty after save {post}")
	print(f"PASS calendar mode {mode_label}: effective={post.get('effective')} save HTTP 200 clean form")


async def run_job_card_csv_for_calendar_mode(
	cdp_page: CDPClient,
	job_card: str,
	csv_text: str,
	mode_label: str,
	user_pref: str,
	default_cal: str,
	default_employee: str,
	persian_calendar_enabled: bool = True,
) -> None:
	await isolate_calendar_mode_for_e2e(
		cdp_page, mode_label, persian_calendar_enabled, user_pref, default_cal
	)
	await _run_job_card_csv_body(
		cdp_page,
		job_card,
		csv_text,
		mode_label,
		user_pref,
		default_cal,
		default_employee,
		persian_calendar_enabled,
	)


async def run_scenarios(job_card: str, sid_value: str, csv_text: str) -> None:
	proc = subprocess.Popen(
		[
			CHROME,
			f"--remote-debugging-port={CDP_PORT}",
			"--no-sandbox",
			"--disable-gpu",
			"--disable-dev-shm-usage",
			"--window-size=1400,900",
			"about:blank",
		],
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL,
	)
	version_url = f"http://127.0.0.1:{CDP_PORT}/json/version"
	version = None
	for _ in range(40):
		await asyncio.sleep(0.25)
		try:
			with urllib.request.urlopen(version_url, timeout=2) as resp:
				version = json.loads(resp.read().decode())
				break
		except Exception:
			continue
	if not version:
		proc.terminate()
		raise E2EFailure(f"Chrome CDP not available on port {CDP_PORT}")
	try:
		ws_url = version["webSocketDebuggerUrl"]

		cdp = CDPClient(ws_url)
		await cdp.connect()
		await cdp.call("Target.createTarget", {"url": "about:blank"})
		targets = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list").read())
		page = next(t for t in targets if t.get("type") == "page")
		cdp_page = CDPClient(page["webSocketDebuggerUrl"])
		await cdp_page.connect()

		await cdp_page.call("Network.enable")
		await cdp_page.call("Page.enable")
		await cdp_page.call("Runtime.enable")
		await cdp_page.call(
			"Page.addScriptToEvaluateOnNewDocument", {"source": E2E_CONSOLE_HOOK_JS}
		)

		domain = BASE_URL.split("//", 1)[-1].split(":")[0]
		await cdp_page.call(
			"Network.setCookie",
			{
				"name": "sid",
				"value": sid_value,
				"domain": domain,
				"path": "/",
				"url": BASE_URL,
			},
		)

		if os.environ.get("E2E_PR_ONLY"):
			form_url = f"{BASE_URL}/app"
		else:
			form_url = f"{BASE_URL}/app/job-card/{urllib.parse.quote(job_card)}"
		await cdp_page.call("Page.navigate", {"url": form_url})
		for _ in range(40):
			await asyncio.sleep(0.5)
			ready = await cdp_page.evaluate("typeof frappe !== 'undefined' && !!frappe.boot")
			if ready:
				break
		else:
			raise E2EFailure(f"Desk did not load frappe.boot at {form_url}")
		await asyncio.sleep(3)
		bundle_url = jalali_bundle_url() + f"?_={int(time.time())}"
		await cdp_page.evaluate(
			f"""
			(function() {{
				var s = document.createElement('script');
				s.src = {json.dumps(bundle_url)};
				document.head.appendChild(s);
			}})();
			"""
		)
		await asyncio.sleep(5)
		await cdp_page.call("Page.reload", {"ignoreCache": True})
		await asyncio.sleep(10)
		await cdp_page.evaluate(E2E_CONSOLE_HOOK_JS)
		await cdp_page.evaluate(
			"""
			(function() {
				if (frappe.boot && frappe.boot.persian_calendar) {
					frappe.boot.persian_calendar.display_calendar = 'Gregorian';
					frappe.boot.persian_calendar.calendar_preference = 'Gregorian';
				}
				window.__persianCalendarInvalidDateLog = [];
				var desc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
				if (desc && desc.set && !window.__pcInvalidDateWatch) {
					window.__pcInvalidDateWatch = true;
					Object.defineProperty(HTMLInputElement.prototype, 'value', {
						configurable: true,
						get: desc.get,
						set: function(v) {
							if (String(v) === 'Invalid date') {
								console.trace('[E2E] Invalid date on input', this);
								window.__persianCalendarInvalidDateLog.push({ v: v, at: Date.now() });
							}
							return desc.set.call(this, v);
						}
					});
				}
			})();
			"""
		)
		boot_info = await cdp_page.evaluate(
			"""(() => ({
				user: frappe?.session?.user,
				hasRuntime: !!(frappe?.persian_calendar?.runtime),
				display: frappe?.boot?.persian_calendar?.display_calendar,
				watchLen: (window.__persianCalendarInvalidDateLog || []).length
			}))()"""
		)
		print(f"Page ready: {boot_info}")
		if boot_info.get("user") == "Guest":
			raise E2EFailure("Still Guest on form page")
		await assert_console_clean(cdp_page, "after desk load + bundle hard refresh")

		await cdp_page.evaluate(
			"""
			(function() {
				window.__pcE2ELastSavedocs = null;
				window.__pcE2ESaveDone = null;
				function recordSavedocs(ok, httpStatus, body) {
					window.__pcE2ELastSavedocs = {
						ok: ok,
						httpStatus: httpStatus,
						body: (body || '').slice(0, 4000)
					};
				}
				function __pcRecordSavedocsFromXhr(xhr, url) {
					if (String(url || '').indexOf('savedocs') < 0) return;
					window.__pcE2ELastSavedocs = {
						ok: xhr.status >= 200 && xhr.status < 300,
						httpStatus: xhr.status,
						body: (xhr.responseText || '').slice(0, 4000)
					};
				}
				if (!window.__pcJquerySavedocsHooked) {
					window.__pcJquerySavedocsHooked = true;
					$(document).on('ajaxComplete', function(ev, xhr, settings) {
						__pcRecordSavedocsFromXhr(xhr, settings && settings.url);
					});
				}
				if (!window.__pcXhrSavedocsHooked) {
					window.__pcXhrSavedocsHooked = true;
					var open = XMLHttpRequest.prototype.open;
					var send = XMLHttpRequest.prototype.send;
					XMLHttpRequest.prototype.open = function(method, url) {
						this.__pcUrl = url;
						return open.apply(this, arguments);
					};
					XMLHttpRequest.prototype.send = function() {
						var xhr = this;
						xhr.addEventListener('load', function() {
							__pcRecordSavedocsFromXhr(xhr, xhr.__pcUrl);
						});
						return send.apply(this, arguments);
					};
				}
				if (!window.__pcE2ESaveHooked) {
					window.__pcE2ESaveHooked = true;
					var origCall = frappe.call;
					frappe.call = function(opts) {
						var method = opts && (opts.method || '');
						if (String(method).indexOf('savedocs') >= 0) {
							var origErr = opts.error;
							opts.error = function(r) {
								var xhr = r && r.xhr;
								recordSavedocs(
									false,
									(xhr && xhr.status) || (r && r.status) || 500,
									(xhr && xhr.responseText) || (r && r.message) || ''
								);
								if (origErr) return origErr(r);
							};
							var origCb = opts.callback;
							opts.callback = function(r) {
								recordSavedocs(true, 200, JSON.stringify(r || {}));
								if (origCb) return origCb(r);
							};
						}
						return origCall.apply(this, arguments);
					};
				}
			})();
			"""
		)

		if (
			not os.environ.get("E2E_JC_CSV_ONLY")
			and not os.environ.get("E2E_CALENDAR_MATRIX")
			and not os.environ.get("E2E_GRID_PICKER_MATRIX")
		):
			pr_name = bench_get_draft_purchase_receipt()
			for scenario_id, default_cal in (("E", "Jalali"), ("F", "Gregorian")):
				bench_set_calendar_test_context(default_cal)
				await cdp_page.evaluate(
					f"""
					(function() {{
						var rt = frappe.persian_calendar.runtime;
						frappe.boot.persian_calendar.enabled = true;
						frappe.boot.persian_calendar.calendar_preference = 'System Default';
						frappe.boot.persian_calendar.default_calendar = {json.dumps(default_cal)};
						rt.configureSystemDefaultCalendarSync({json.dumps(default_cal)});
						rt.invalidateCalendarSettingsCache();
						return rt.getCalendarPreferenceDebugSync();
					}})();
					"""
				)
				await asyncio.sleep(0.3)
				debug_boot = await cdp_page.evaluate(
					"""(() => frappe.persian_calendar.runtime.getCalendarPreferenceDebugSync())()"""
				)
				effective = debug_boot.get("effective_calendar_mode")
				print(f"Scenario {scenario_id}: effective_calendar_mode={effective} debug={debug_boot}")
				if effective != default_cal:
					raise E2EFailure(
						f"Scenario {scenario_id}: expected effective {default_cal}, got {effective}"
					)
				route_doc = pr_name or "new-purchase-receipt-1"
				await cdp_page.evaluate(
				f"frappe.set_route('Form', 'Purchase Receipt', {json.dumps(route_doc)});"
			)
			await asyncio.sleep(4)
			await cdp_page.evaluate(
				"""
				(function() {
					var chk = document.querySelector(
						'.frappe-control[data-fieldname="edit_posting_date_and_time"] input[type="checkbox"]'
					);
					if (chk && !chk.checked) chk.click();
				})();
				"""
			)
			await asyncio.sleep(0.8)
			probe = await cdp_page.evaluate(
				"""
				(function() {
					var rt = frappe.persian_calendar.runtime;
					var dbg = rt.getCalendarPreferenceDebugSync();
					var pdInput = document.querySelector(
						'.frappe-control[data-fieldname="posting_date"] input'
					);
					var ptInput = document.querySelector(
						'.frappe-control[data-fieldname="posting_time"] input'
					);
					var doc = cur_frm && cur_frm.doc ? cur_frm.doc : {};
					return {
						debug: dbg,
						posting_date_visible: pdInput ? pdInput.value : null,
						posting_date_model: doc.posting_date,
						posting_time_visible: ptInput ? ptInput.value : null,
						posting_time_model: doc.posting_time,
						shouldUseJalali: rt.shouldUseJalaliCalendarSync(),
						invalidLog: window.__persianCalendarInvalidDateLog || []
					};
				})();
				"""
			)
			print(f"Scenario {scenario_id}: posting probe: {probe}")
			pt_vis = str(probe.get("posting_time_visible") or "")
			pt_mod = str(probe.get("posting_time_model") or "")
			if "Invalid date" in pt_vis or "Invalid date" in pt_mod or "NaN" in pt_vis:
				raise E2EFailure(f"Scenario {scenario_id}: bad posting_time: {probe}")
			if pt_vis and not re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", pt_vis):
				raise E2EFailure(f"Scenario {scenario_id}: posting_time not HH:mm:ss: {pt_vis}")
			pd_vis = str(probe.get("posting_date_visible") or "")
			pd_mod = str(probe.get("posting_date_model") or "")
			if effective == "Jalali":
				pd_mod_date = str(pd_mod or "")[:10]
				if pd_mod_date and not re.match(r"^20\d{2}-\d{2}-\d{2}$", pd_mod_date):
					raise E2EFailure(
						f"Scenario {scenario_id}: posting_date model must be Gregorian ISO, got {pd_mod}"
					)
				if pd_vis and not re.match(r"^1[34]\d{2}-\d{2}-\d{2}$", pd_vis):
					raise E2EFailure(
						f"Scenario {scenario_id}: posting_date visible expected Jalali yyyy-mm-dd, got {pd_vis}"
					)
			if probe.get("invalidLog"):
				raise E2EFailure(f"Scenario {scenario_id}: Invalid date watch: {probe.get('invalidLog')}")
			pre_save_dump = await cdp_page.evaluate(
				"""
				(function() {
					function collectDateTimeFields(frm) {
						var out = {};
						if (!frm || !frm.meta || !frm.meta.fields) return out;
						frm.meta.fields.forEach(function(df) {
							if (df.fieldtype === 'Date' || df.fieldtype === 'Datetime' || df.fieldtype === 'Time') {
								out[df.fieldname] = frm.doc[df.fieldname];
							}
							if (df.fieldtype === 'Table' && frm.doc[df.fieldname]) {
								frm.doc[df.fieldname].forEach(function(row, i) {
									var childMeta = frappe.get_meta(df.options);
									if (!childMeta) return;
									childMeta.fields.forEach(function(cdf) {
										if (cdf.fieldtype === 'Date' || cdf.fieldtype === 'Datetime' || cdf.fieldtype === 'Time') {
											out[df.fieldname + '[' + i + '].' + cdf.fieldname] = row[cdf.fieldname];
										}
									});
								});
							}
						});
						return out;
					}
					var frm = cur_frm;
					var rt = frappe.persian_calendar && frappe.persian_calendar.runtime;
					return {
						doctype: frm && frm.doc ? frm.doc.doctype : null,
						name: frm && frm.doc ? frm.doc.name : null,
						effective_calendar_mode: rt && rt.getEffectiveCalendarModeSync ? rt.getEffectiveCalendarModeSync() : null,
						posting_date: frm && frm.doc ? frm.doc.posting_date : null,
						posting_time: frm && frm.doc ? frm.doc.posting_time : null,
						set_posting_time: frm && frm.doc ? frm.doc.set_posting_time : null,
						date_time_fields: collectDateTimeFields(frm),
						items_len: frm && frm.doc && frm.doc.items ? frm.doc.items.length : 0,
						is_dirty: frm ? frm.is_dirty() : null
					};
				})();
				"""
			)
			print(f"Scenario {scenario_id}: pre-save dump: {pre_save_dump}")
			await cdp_page.evaluate("window.__pcE2ESaveDone = null; window.__pcE2ELastSavedocs = null;")
			await cdp_page.evaluate(
				"""
				(function() {
					cur_frm.save().then(function() {
						window.__pcE2ESaveDone = { ok: true };
					}).catch(function(e) {
						window.__pcE2ESaveDone = {
							ok: false,
							error: String(e.message || e)
						};
					});
				})();
				"""
			)
			for _ in range(60):
				await asyncio.sleep(0.5)
				done = await cdp_page.evaluate("window.__pcE2ESaveDone")
				if done:
					break
			else:
				raise E2EFailure(f"Scenario {scenario_id}: save timeout")
			save_meta = await cdp_page.evaluate(
				"""(() => ({
					done: window.__pcE2ESaveDone,
					savedocs: window.__pcE2ELastSavedocs
				}))()"""
			)
			sd = save_meta.get("savedocs") or {}
			http_status = sd.get("httpStatus")
			body = str(sd.get("body") or "")
			print(f"Scenario {scenario_id}: savedocs status={http_status} body_head={body[:1200]!r}")
			if http_status is None:
				raise E2EFailure(f"Scenario {scenario_id}: no savedocs HTTP status captured: {save_meta}")
			if http_status >= 500:
				raise E2EFailure(
					f"Scenario {scenario_id}: savedocs HTTP {http_status} (server error). body={body[:4000]}"
				)
			if body.lstrip().lower().startswith("<!doctype") or body.lstrip().lower().startswith("<html"):
				raise E2EFailure(
					f"Scenario {scenario_id}: savedocs returned HTML error page (HTTP {http_status}). body={body[:4000]}"
				)
			if not save_meta.get("done", {}).get("ok") or http_status != 200:
				raise E2EFailure(f"Scenario {scenario_id}: save failed: {save_meta}")
			print(f"Scenario {scenario_id}: save OK (HTTP {http_status})")
			await asyncio.sleep(2)
			await cdp_page.evaluate(
				"""
				(function() {
					try {
						localStorage.setItem('persian_calendar_dirty_trace', '1');
						if (frappe.persian_calendar.runtime.enableDirtyStateTrace) {
							frappe.persian_calendar.runtime.enableDirtyStateTrace();
						}
					} catch (e) {}
				})();
				"""
			)
			post_save = await cdp_page.evaluate(
				"""
				(function() {
					var frm = cur_frm;
					var dirty = frm ? !!frm.is_dirty() : true;
					var pills = Array.from(document.querySelectorAll('.indicator-pill')).map(function(el) {
						return (el.textContent || '').trim();
					});
					var notSavedBadge = pills.some(function(t) {
						return /not\\s*saved/i.test(t);
					});
					var pdInput = document.querySelector(
						'.frappe-control[data-fieldname="posting_date"] input'
					);
					var rt = frappe.persian_calendar && frappe.persian_calendar.runtime;
					return {
						is_dirty: dirty,
						__unsaved: frm && frm.doc ? frm.doc.__unsaved : null,
						indicator_pills: pills,
						not_saved_badge: notSavedBadge,
						posting_date_model: frm && frm.doc ? frm.doc.posting_date : null,
						posting_date_visible: pdInput ? pdInput.value : null,
						effective_calendar_mode: rt && rt.getEffectiveCalendarModeSync
							? rt.getEffectiveCalendarModeSync()
							: null,
						dirty_trace_after_save: (window.__persianCalendarDirtyTraceLog || []).filter(function(e) {
							return e.savePhase === 'after_save' || e.savePhase === 'post_after_save';
						})
					};
				})();
				"""
			)
			print(f"Scenario {scenario_id}: post-save clean state: {post_save}")
			if scenario_id == "E":
				if post_save.get("is_dirty"):
					raise E2EFailure(f"Scenario E: form still dirty after save: {post_save}")
				if post_save.get("not_saved_badge"):
					raise E2EFailure(f"Scenario E: Not Saved badge still shown: {post_save}")
				if post_save.get("dirty_trace_after_save"):
					raise E2EFailure(
						f"Scenario E: model mutations after save: {post_save.get('dirty_trace_after_save')}"
					)
			await assert_console_clean(cdp_page, f"after Scenario {scenario_id} Purchase Receipt save")

		if os.environ.get("E2E_PR_ONLY"):
			await assert_console_clean(cdp_page, "final (PR-only E/F)")
			print("PASS: PR-only scenarios E/F completed")
			await cdp_page.close()
			await cdp.close()
			return

		# --- A) Job Card Time Logs ---
		await cdp_page.evaluate(
			f"frappe.set_route('Form', 'Job Card', {json.dumps(job_card)});"
		)
		await asyncio.sleep(4)
		await assert_console_clean(cdp_page, "after Job Card route (form refresh)")
		await cdp_page.evaluate(
			"""
			(function() {
				var tab = document.querySelector('.form-tabs-list [data-fieldname="actual_time"], .nav-link[data-fieldname="actual_time"]');
				if (tab) tab.click();
			})();
			"""
		)
		await asyncio.sleep(1)

		await cdp_page.evaluate(
			"""
			(function() {
				if (!window.__pcE2ESaveHooked) {
					window.__pcE2ESaveHooked = true;
					window.__pcE2ELastSavedocs = null;
					window.__pcE2ESaveDone = null;
					function recordSavedocs(ok, httpStatus, body) {
						window.__pcE2ELastSavedocs = { ok: ok, httpStatus: httpStatus, body: (body || '').slice(0, 4000) };
					}
					var origCall = frappe.call;
					frappe.call = function(opts) {
						var method = opts && (opts.method || '');
						if (String(method).indexOf('savedocs') >= 0) {
							var origErr = opts.error;
							opts.error = function(r) {
								var xhr = r && r.xhr;
								recordSavedocs(false, (xhr && xhr.status) || (r && r.status) || 500, (xhr && xhr.responseText) || '');
								if (origErr) return origErr(r);
							};
							var origCb = opts.callback;
							opts.callback = function(r) {
								recordSavedocs(true, 200, JSON.stringify(r || {}));
								if (origCb) return origCb(r);
							};
						}
						return origCall.apply(this, arguments);
					};
				}
			})();
			"""
		)
		default_employee = bench_get_default_employee()
		print(f"E2E default employee: {default_employee}")
		if os.environ.get("E2E_GRID_PICKER_MATRIX"):
			print("Running grid picker click matrix (4 modes, user click → visible popup)...")
			for label, enabled, user_pref, default_cal in GRID_PICKER_MODE_MATRIX:
				await run_job_card_csv_for_calendar_mode(
					cdp_page,
					job_card,
					csv_text,
					label,
					user_pref,
					default_cal,
					default_employee,
					enabled,
				)
			await assert_console_clean(cdp_page, "final (grid picker matrix)")
			await cdp_page.close()
			await cdp.close()
			return

		matrix = CALENDAR_MODE_MATRIX if os.environ.get("E2E_CALENDAR_MATRIX") else None
		if matrix:
			pr_name = os.environ.get("E2E_PURCHASE_RECEIPT") or bench_get_draft_purchase_receipt()
			if not pr_name:
				raise E2EFailure("E2E_PURCHASE_RECEIPT / draft PR required for full matrix")
			print(
				f"Running full calendar acceptance matrix A–G "
				f"(Job Card {job_card}, PR {pr_name})..."
			)
			matrix_rows: list[tuple[str, dict[str, str]]] = []
			only = os.environ.get("E2E_MATRIX_ONLY", "")
			if only.strip():
				labels = {x.strip() for x in only.split(",") if x.strip()}
				matrix = [m for m in matrix if m[0] in labels]
			for label, enabled, user_pref, default_cal in matrix:
				try:
					ctx = await run_calendar_mode_acceptance(
						cdp_page,
						job_card,
						pr_name,
						csv_text,
						label,
						enabled,
						user_pref,
						default_cal,
						default_employee,
					)
					matrix_rows.append((label, ctx))
				except E2EFailure as e:
					partial = getattr(e, "acceptance_ctx", None) or {}
					partial["OVERALL"] = f"FAIL: {e}"
					matrix_rows.append((label, partial))
					print_acceptance_matrix_table(matrix_rows)
					raise
			print_acceptance_matrix_table(matrix_rows)
			await assert_console_clean(cdp_page, "final (full A–G acceptance matrix)")
			await cdp_page.close()
			await cdp.close()
			return
		else:
			for mode_label, user_pref, default_cal in (
				("Gregorian", "Gregorian", "Jalali"),
				("Jalali", "Jalali", "Jalali"),
				("SystemDefaultGregorian", "System Default", "Gregorian"),
				("SystemDefault", "System Default", "Jalali"),
			):
				await run_job_card_csv_for_calendar_mode(
					cdp_page, job_card, csv_text, mode_label, user_pref, default_cal, default_employee
				)
		print("PASS: Job Card CSV matrix")

		if os.environ.get("E2E_JC_CSV_ONLY") and not os.environ.get("E2E_CALENDAR_MATRIX"):
			await assert_console_clean(cdp_page, "final (JC CSV matrix only)")
			print("PASS: Job Card CSV E2E only (Gregorian, Jalali, System Default)")
			await cdp_page.close()
			await cdp.close()
			return

		await cdp_page.evaluate(
			f"""
			(function() {{
				return frappe.call({{
					method: 'persian_calendar.jalali_support.e2e_fixtures.prepare_work_order_for_job_card_save',
					args: {{ job_card: {json.dumps(job_card)} }},
					async: false
				}});
			}})();
			"""
		)
		await cdp_page.evaluate(
			"""
			(function() {
				window.__pcE2ELastSavedocs = null;
				window.__pcE2ESaveDone = null;
				function recordSavedocs(ok, httpStatus, body) {
					window.__pcE2ELastSavedocs = {
						ok: ok,
						httpStatus: httpStatus,
						body: (body || '').slice(0, 4000)
					};
				}
				function __pcRecordSavedocsFromXhr(xhr, url) {
					if (String(url || '').indexOf('savedocs') < 0) return;
					window.__pcE2ELastSavedocs = {
						ok: xhr.status >= 200 && xhr.status < 300,
						httpStatus: xhr.status,
						body: (xhr.responseText || '').slice(0, 4000)
					};
				}
				if (!window.__pcJquerySavedocsHooked) {
					window.__pcJquerySavedocsHooked = true;
					$(document).on('ajaxComplete', function(ev, xhr, settings) {
						__pcRecordSavedocsFromXhr(xhr, settings && settings.url);
					});
				}
				if (!window.__pcXhrSavedocsHooked) {
					window.__pcXhrSavedocsHooked = true;
					var open = XMLHttpRequest.prototype.open;
					var send = XMLHttpRequest.prototype.send;
					XMLHttpRequest.prototype.open = function(method, url) {
						this.__pcUrl = url;
						return open.apply(this, arguments);
					};
					XMLHttpRequest.prototype.send = function() {
						var xhr = this;
						xhr.addEventListener('load', function() {
							__pcRecordSavedocsFromXhr(xhr, xhr.__pcUrl);
						});
						return send.apply(this, arguments);
					};
				}
				if (!window.__pcE2ESaveHooked) {
					window.__pcE2ESaveHooked = true;
					var origCall = frappe.call;
					frappe.call = function(opts) {
						var method = opts && (opts.method || '');
						if (String(method).indexOf('savedocs') >= 0) {
							var origErr = opts.error;
							opts.error = function(r) {
								var xhr = r && r.xhr;
								recordSavedocs(
									false,
									(xhr && xhr.status) || (r && r.status) || 500,
									(xhr && xhr.responseText) || (r && r.message) || ''
								);
								if (origErr) return origErr(r);
							};
							var origCb = opts.callback;
							opts.callback = function(r) {
								recordSavedocs(true, 200, JSON.stringify(r || {}));
								if (origCb) return origCb(r);
							};
						}
						return origCall.apply(this, arguments);
					};
					window.__pcE2EOrigCall = origCall;
				}
			})();
			"""
		)
		pre_save = await cdp_page.evaluate(
			"""
			(function() {
				return (cur_frm.doc.time_logs || []).map(function(r) {
					return {
						from_time: r.from_time,
						to_time: r.to_time,
						time_in_mins: r.time_in_mins,
						completed_qty: r.completed_qty,
						employee: r.employee,
						operation: r.operation
					};
				});
			})();
			"""
		)
		print(f"Scenario D: time_logs before save: {pre_save}")
		await cdp_page.evaluate(
			"""
			(function() {
				cur_frm.save().then(function() {
					window.__pcE2ESaveDone = { ok: true };
				}).catch(function(e) {
					window.__pcE2ESaveDone = {
						ok: false,
						error: String(e.message || e),
						exc: e.exc
					};
				});
			})();
			"""
		)
		for _ in range(60):
			await asyncio.sleep(0.5)
			done = await cdp_page.evaluate("window.__pcE2ESaveDone")
			if done:
				break
		else:
			raise E2EFailure("cur_frm.save() did not complete within 30s")
		save_result = await cdp_page.evaluate(
			"""
			(function() {
				var dump = (cur_frm.doc.time_logs || []).map(function(r) {
					return {
						from_time: r.from_time,
						to_time: r.to_time,
						time_in_mins: r.time_in_mins,
						completed_qty: r.completed_qty,
						employee: r.employee,
						operation: r.operation
					};
				});
				var sd = window.__pcE2ELastSavedocs;
				var done = window.__pcE2ESaveDone || {};
				var httpStatus = (sd && sd.httpStatus) || (done.ok ? 200 : 500);
				var body = (sd && sd.body) || '';
				var saveOk = !!(done.ok && httpStatus >= 200 && httpStatus < 300 && (!sd || sd.ok !== false));
				return {
					ok: saveOk,
					httpStatus: httpStatus,
					savedocs: sd,
					saveDone: done,
					time_logs: dump,
					dirty: cur_frm.is_dirty(),
					htmlError: body.trim().slice(0, 80).toLowerCase().indexOf('<!doctype') >= 0,
					error: done.error || null,
					exc: done.exc || null
				};
			})();
			"""
		)
		print(f"Scenario D: time_logs before save: {save_result.get('time_logs')}")
		print(f"Scenario D: savedocs result: {save_result}")
		http_status = int(save_result.get("httpStatus") or 0)
		if http_status >= 500 or save_result.get("htmlError"):
			body = (save_result.get("savedocs") or {}).get("body") or save_result.get("error") or ""
			raise E2EFailure(
				f"savedocs returned HTTP {http_status} (HTML error page). "
				f"Body snippet: {str(body)[:800]}"
			)
		if not save_result.get("ok"):
			raise E2EFailure(f"Job Card save failed after CSV import: {save_result}")
		for row in save_result.get("time_logs") or []:
			for key in ("from_time", "to_time"):
				val = str(row.get(key, ""))
				if "Invalid date" in val or "NaN" in val:
					raise E2EFailure(f"time_logs sent to server still bad {key}={val}")
				if val and not val.startswith("2026-"):
					raise E2EFailure(f"time_logs {key} not ISO on save payload: {row}")
		print(f"Scenario D: CSV import + grid click + save OK (HTTP {http_status})")
		await assert_console_clean(cdp_page, "after CSV grid click + save")

		# --- B) Purchase Receipt posting_time ---
		await cdp_page.evaluate(
			"frappe.set_route('Form', 'Purchase Receipt', 'new-purchase-receipt-1');"
		)
		await asyncio.sleep(3)
		await cdp_page.evaluate(
			"""
			(function() {
				var chk = document.querySelector('.frappe-control[data-fieldname="edit_posting_date_and_time"] input[type="checkbox"]');
				if (chk && !chk.checked) chk.click();
			})();
			"""
		)
		await asyncio.sleep(0.5)
		await cdp_page.evaluate(
			"""
			(function() {
				var input = document.querySelector('.frappe-control[data-fieldname="posting_time"] input');
				if (!input) throw new Error('posting_time input missing');
				input.focus();
				input.click();
			})();
			"""
		)
		await asyncio.sleep(0.7)
		result_b = await cdp_page.evaluate(
			"""
			(function() {
				var input = document.querySelector('.frappe-control[data-fieldname="posting_time"] input');
				var val = input ? (input.value || '') : '';
				var model = cur_frm && cur_frm.doc ? cur_frm.doc.posting_time : null;
				var log = window.__persianCalendarInvalidDateLog || [];
				return { val: val, model: model, logLen: log.length, log: log };
			})();
			"""
		)
		if "Invalid date" in str(result_b.get("val", "")) or "Invalid date" in str(result_b.get("model", "")):
			raise E2EFailure(f"Stock Entry posting_time Invalid date: {result_b}")
		if result_b.get("logLen", 0) > 0:
			raise E2EFailure(f"Watch log posting_time: {result_b.get('log')}")
		await assert_console_clean(cdp_page, "after Purchase Receipt posting_time focus")

		# --- C) Jalali -> Gregorian without reload (boot-only switch for E2E stability) ---
		await cdp_page.evaluate(
			"""
			(function() {
				window.__persianCalendarInvalidDateLog = [];
				if (frappe.boot && frappe.boot.persian_calendar) {
					frappe.boot.persian_calendar.calendar_preference = 'Jalali';
					frappe.boot.persian_calendar.display_calendar = 'Jalali';
				}
			})();
			"""
		)
		await asyncio.sleep(0.3)
		await cdp_page.evaluate(
			"""
			(function() {
				if (frappe.boot && frappe.boot.persian_calendar) {
					frappe.boot.persian_calendar.calendar_preference = 'Gregorian';
					frappe.boot.persian_calendar.display_calendar = 'Gregorian';
				}
				var rt = frappe.persian_calendar && frappe.persian_calendar.runtime;
				if (rt && rt.invalidateCalendarSettingsCache) rt.invalidateCalendarSettingsCache();
				if (rt && rt.updateBootFromUserCalendarPreference) rt.updateBootFromUserCalendarPreference('Gregorian');
			})();
			"""
		)
		await cdp_page.evaluate(
			f"frappe.set_route('Form', 'Job Card', {json.dumps(job_card)});"
		)
		await asyncio.sleep(3)
		await cdp_page.evaluate(
			"""
			(function() {
				var grid = cur_frm && cur_frm.fields_dict && cur_frm.fields_dict.time_logs && cur_frm.fields_dict.time_logs.grid;
				if (grid && grid.grid_rows && grid.grid_rows.length) {
					grid.grid_rows[0].toggle_editable_row(true);
				}
			})();
			"""
		)
		await asyncio.sleep(1)
		for field in ("from_time", "to_time"):
			await cdp_page.evaluate(
				f"""
				(function() {{
					var input = document.querySelector('.frappe-control[data-fieldname="{field}"] input');
					if (input) {{ input.focus(); input.click(); }}
				}})();
				"""
			)
			await asyncio.sleep(0.5)
			result_c = await cdp_page.evaluate(
				f"""
				(function() {{
					var input = document.querySelector('.frappe-control[data-fieldname="{field}"] input');
					if (!input) return {{ skip: true }};
					return {{
						val: input.value,
						model: cur_frm && cur_frm.doc && cur_frm.doc.time_logs && cur_frm.doc.time_logs[0] ? cur_frm.doc.time_logs[0]['{field}'] : null,
						logLen: (window.__persianCalendarInvalidDateLog || []).length
					}};
				}})();
				"""
			)
			if result_c.get("skip"):
				continue
			if "Invalid date" in str(result_c.get("val", "")) or "Invalid date" in str(result_c.get("model", "")):
				raise E2EFailure(f"After switch {field}: {result_c}")
			if result_c.get("logLen", 0) > 0:
				raise E2EFailure(f"After switch watch log {field}")

		await assert_console_clean(cdp_page, "final (all scenarios)")
		print("Console assertion: PASS (no uncaught errors)")

		await cdp_page.close()
		await cdp.close()
	finally:
		proc.terminate()
		try:
			proc.wait(timeout=5)
		except subprocess.TimeoutExpired:
			proc.kill()


def main() -> int:
	os.environ.setdefault("BENCH_PATH", "/workspace/development/frappe-bench")
	os.environ.setdefault("E2E_SKIP_FIXTURE_CREATE", "1")
	os.environ.setdefault("E2E_JOB_CARD", "PO-JOB01046")
	os.environ.setdefault("E2E_PURCHASE_RECEIPT", "MAT-PRE-2026-00075")
	print(f"E2E base URL: {BASE_URL}")
	print("API login...")
	sid = frappe_login_sid()
	job_card = os.environ.get("E2E_JOB_CARD") or ""
	if not os.environ.get("E2E_PR_ONLY"):
		print("Resolving Job Card...")
		if not job_card:
			fixture = bench_create_fixture()
			job_card = fixture.get("job_card") or ""
		if not job_card:
			raise E2EFailure("No job_card (set E2E_JOB_CARD or create fixture)")
		print(f"Job Card: {job_card}")
	else:
		job_card = job_card or "PO-JOB01041"
		print(f"PR-only E2E; Purchase Receipt: {os.environ.get('E2E_PURCHASE_RECEIPT', 'MAT-PRE-2026-00075')}")
	csv_text = load_time_logs_csv_text() if not os.environ.get("E2E_PR_ONLY") else ""
	if not os.environ.get("E2E_PR_ONLY"):
		print(f"CSV fixture: {CSV_FIXTURE} ({len(csv_text)} bytes)")
	if os.environ.get("E2E_GRID_PICKER_MATRIX"):
		print(f"Running grid picker user-click matrix (4 modes) on Job Card {job_card}...")
	elif os.environ.get("E2E_CALENDAR_MATRIX"):
		print(
			f"Running full E2E calendar acceptance A–G "
			f"(JC {job_card}, PR {os.environ.get('E2E_PURCHASE_RECEIPT', 'MAT-PRE-2026-00075')})..."
		)
	elif os.environ.get("E2E_JC_CSV_ONLY"):
		print(f"Running Job Card CSV matrix only (PO-JOB01046): {job_card}")
	elif os.environ.get("E2E_PR_ONLY"):
		print("Running PR-only CDP scenarios E/F (Purchase Receipt)...")
	else:
		print("Running headless CDP scenarios E/F + Job Card CSV matrix + legacy checks...")
	asyncio.run(run_scenarios(job_card, sid, csv_text))
	if os.environ.get("E2E_PR_ONLY"):
		print("PASS: PR E2E (MAT-PRE save HTTP 200, clean form, no HTML 500)")
	else:
		print(
			"PASS: all E2E scenarios completed "
			"(CSV import, no Invalid date/NaN, save OK, no uncaught console errors)"
		)
	return 0


if __name__ == "__main__":
	try:
		sys.exit(main())
	except E2EFailure as e:
		print(f"FAIL: {e}", file=sys.stderr)
		sys.exit(1)
