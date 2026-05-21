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
	default_calendar: str, user_calendar_preference: str = "System Default"
) -> None:
	"""Set Administrator calendar preference and Jalali Settings default_calendar."""
	bench = _bench_cmd()
	bench_path = os.environ.get("BENCH_PATH", "/workspace/development/frappe-bench")
	exe = subprocess.run(
		[
			bench,
			"--site",
			SITE,
			"execute",
			"frappe.get_attr('persian_calendar.jalali_support.e2e_fixtures.set_calendar_e2e_context')"
			f"({json.dumps(default_calendar)}, {json.dumps(user_calendar_preference)})",
		],
		capture_output=True,
		text=True,
		cwd=bench_path,
		timeout=120,
	)
	if exe.returncode != 0:
		raise E2EFailure(f"bench calendar context failed:\n{exe.stdout}\n{exe.stderr}")


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


async def run_job_card_csv_for_calendar_mode(
	cdp_page: CDPClient,
	job_card: str,
	csv_text: str,
	mode_label: str,
	user_pref: str,
	default_cal: str,
	default_employee: str,
) -> None:
	"""CSV import + click + save for one calendar preference (clears localStorage each run)."""
	bench_set_calendar_test_context(default_cal, user_pref)
	await cdp_page.evaluate(
		f"""
		(function() {{
			try {{
				localStorage.clear();
				sessionStorage.clear();
			}} catch (e) {{}}
			frappe.boot.persian_calendar = frappe.boot.persian_calendar || {{}};
			frappe.boot.persian_calendar.enabled = true;
			frappe.boot.persian_calendar.calendar_preference = {json.dumps(user_pref)};
			frappe.boot.persian_calendar.default_calendar = {json.dumps(default_cal)};
			var rt = frappe.persian_calendar.runtime;
			var __pcUserPref = {json.dumps(user_pref)};
			if (__pcUserPref === 'System Default' && rt.configureSystemDefaultCalendarSync) {{
				rt.configureSystemDefaultCalendarSync({json.dumps(default_cal)});
			}} else if (rt.updateBootFromUserCalendarPreference) {{
				rt.updateBootFromUserCalendarPreference(__pcUserPref);
			}}
			if (rt.invalidateCalendarSettingsCache) rt.invalidateCalendarSettingsCache();
			window.__pcMomentDeprecation = [];
			window.__pcRawCsvInFormatter = [];
			window.__persianCalendarInvalidDateLog = [];
			return rt.getCalendarPreferenceDebugSync ? rt.getCalendarPreferenceDebugSync() : null;
		}})();
		"""
	)
	await cdp_page.call("Page.reload", {"ignoreCache": True})
	for _ in range(80):
		await asyncio.sleep(0.5)
		ready = await cdp_page.evaluate("typeof frappe !== 'undefined' && !!frappe.boot")
		if ready:
			break
	else:
		raise E2EFailure(f"{mode_label}: desk did not reload (frappe.boot missing)")
	await asyncio.sleep(3)
	await cdp_page.evaluate(E2E_CONSOLE_HOOK_JS)
	await cdp_page.evaluate(E2E_SAVE_HOOKS_JS)
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

		if not os.environ.get("E2E_JC_CSV_ONLY"):
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
		for mode_label, user_pref, default_cal in (
			("Gregorian", "Gregorian", "Jalali"),
			("Jalali", "Jalali", "Jalali"),
			("SystemDefault", "System Default", "Jalali"),
		):
			await run_job_card_csv_for_calendar_mode(
				cdp_page, job_card, csv_text, mode_label, user_pref, default_cal, default_employee
			)
		print("PASS: Job Card CSV matrix (Gregorian, Jalali, System Default)")

		if os.environ.get("E2E_JC_CSV_ONLY"):
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
	if os.environ.get("E2E_JC_CSV_ONLY"):
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
