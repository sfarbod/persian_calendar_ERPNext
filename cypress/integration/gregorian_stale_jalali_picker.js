/**
 * Regression: stale JalaliDatepicker on grid inputs after switching User preference to Gregorian
 * without full browser reload.
 *
 * Requires: frappe + erpnext + persian_calendar on site, Jalali Settings enabled.
 *
 * Run (from bench):
 *   cd apps/frappe && npx cypress run --config-file ../persian_calendar/cypress.config.js \
 *     --spec ../persian_calendar/cypress/integration/gregorian_stale_jalali_picker.js
 *
 * Env:
 *   CYPRESS_BASE_URL=http://development.localhost:8000
 *   CYPRESS_ADMIN_PASSWORD=admin
 */

const JOB_CARD_ROUTE = "Form/Job Card";

function openJobCard(win, name) {
	win.frappe.set_route(JOB_CARD_ROUTE, name);
}

function focusTimeLogDatetime(fieldname) {
	cy.get(
		`.form-grid .frappe-control[data-fieldname="${fieldname}"] input, .form-in-grid .frappe-control[data-fieldname="${fieldname}"] input`
	)
		.filter(":visible")
		.first()
		.scrollIntoView()
		.click({ force: true })
		.focus({ force: true });
	cy.wait(400);
}

context("Gregorian mode removes stale Jalali grid datetime picker", () => {
	let fixture = null;
	before(() => {
		cy.login();
		cy.visit("/desk");
		cy.window().then((win) => {
			expect(win.frappe.persian_calendar?.runtime, "persian_calendar runtime").to.exist;
		});

		cy.ensureJalaliAppEnabled();
		cy.createJobCardFixture().then((r) => {
			fixture = r?.message || r;
			expect(fixture?.job_card, "fixture.job_card").to.exist;
		});
	});

	after(() => {
		if (!fixture) return;
		cy.deleteJobCardFixture(fixture);
	});

	it("Jalali attach then Gregorian switch without reload does not corrupt Time Logs datetime", () => {
		// --- Phase A: Jalali preference, attach picker on grid ---
		cy.setCalendarPreference("Jalali");
		cy.window().then((win) => {
			expect(win.frappe.persian_calendar.runtime.shouldUseJalaliCalendarSync()).to.eq(true);
		});
		cy.resetPersianCalendarCounters();

		cy.window().then((win) => openJobCard(win, fixture.job_card));
		cy.wait(2000);

		// Actual Time tab if present
		cy.get("body").then(($body) => {
			const $tab = $body.find('.form-tabs-list [data-fieldname="actual_time"], .nav-link:contains("Actual Time")');
			if ($tab.length) {
				cy.wrap($tab.first()).click({ force: true });
				cy.wait(500);
			}
		});

		focusTimeLogDatetime("from_time");

		cy.window().then((win) => {
			const rt = win.frappe.persian_calendar.runtime;
			expect(rt.shouldUseJalaliCalendarSync()).to.eq(true);
			const counts = rt.getCallCounts();
			expect(counts.valueToJalaliDisplay || 0).to.be.greaterThan(0);
		});

		// Optional: visible jalali popup in DOM after focus (may be body-mounted)
		cy.get("body").then(($body) => {
			const hasJalaliUi =
				$body.find(".jalali-datepicker:visible").length > 0 ||
				$body.find('input[data-has-jalali-datepicker="true"]').length > 0;
			expect(hasJalaliUi, "Jalali picker or attr after Jalali focus").to.eq(true);
		});

		cy.inspectGridDatetimeInput("from_time").then((info) => {
			cy.wrap(info).as("jalaliPhaseInspect");
			expect(info.hasNaN).to.eq(false);
			expect(info.hasInvalid).to.eq(false);
		});

		// --- Phase B: switch to Gregorian WITHOUT location.reload ---
		cy.setCalendarPreference("Gregorian");
		cy.window().then((win) => {
			const rt = win.frappe.persian_calendar.runtime;
			expect(rt.shouldUseJalaliCalendarSync()).to.eq(false);
			expect(win.frappe.boot.persian_calendar.display_calendar).to.eq("Gregorian");
			rt.resetCallCounts();
		});

		// Form-only refresh (same as User after_save handler)
		cy.window().then((win) => {
			if (win.cur_frm) {
				// simulate stale rendered value left behind by prior mode / formatter
				const inp = win.document.querySelector(
					'.form-grid .frappe-control[data-fieldname="from_time"] input, .form-in-grid .frappe-control[data-fieldname="from_time"] input'
				);
				if (inp) {
					inp.value = "20-04-2026 12:00:00";
				}
				win.cur_frm.refresh_fields();
			}
		});
		cy.wait(800);

		cy.window().then((win) => {
			const rt = win.frappe.persian_calendar.runtime;
			const destroyLog = rt.getDestroyLog();
			expect(destroyLog.length).to.be.greaterThan(0);
		});

		cy.enableInvalidDateWatch();

		focusTimeLogDatetime("from_time");
		focusTimeLogDatetime("to_time");

		// Stale dd-mm display must be replaced from model (user format), never Invalid date or raw ISO in input
		cy.inspectGridDatetimeInput("from_time").then((info) => {
			expect(info.hasInvalid).to.eq(false);
			expect(info.value).to.not.match(/Invalid\s*date/i);
			expect(info.value).to.not.eq("20-04-2026 12:00:00");
		});

		cy.assertInvalidDateLogEmpty();

		cy.window().then((win) => {
			const counts = win.frappe.persian_calendar.runtime.getCallCounts();
			expect(counts.valueToJalaliDisplay || 0).to.eq(0);
			expect(counts.parseJalaliDateTime || 0).to.eq(0);
			expect(counts.syncInputFromModel || 0).to.eq(0);
		});

		cy.inspectGridDatetimeInput("from_time").then((info) => {
			cy.wrap(info).as("gregorianPhaseInspect");
			expect(info.gregorianMode).to.eq(true);
			expect(info.hasNaN, `value=${info.value}`).to.eq(false);
			expect(info.hasInvalid, `value=${info.value}`).to.eq(false);
			expect(info.hasJalaliAttr, "stale data-has-jalali-datepicker").to.eq(false);
			expect(info.hasJalaliInstance, "stale jalaliDatepickerInstance").to.eq(false);
		});

		cy.inspectGridDatetimeInput("to_time").then((info) => {
			expect(info.hasNaN, `value=${info.value}`).to.eq(false);
			expect(info.hasInvalid, `value=${info.value}`).to.eq(false);
			expect(info.hasJalaliAttr).to.eq(false);
			expect(info.hasJalaliInstance).to.eq(false);
		});

		cy.get(".jalali-datepicker:visible").should("not.exist");

		// Save must not fail with bad datetime
		cy.window().then((win) => {
			if (!win.cur_frm) {
				return;
			}
			const row = win.cur_frm.doc.time_logs?.[0];
			if (row && !row.from_time) {
				row.from_time = win.frappe.datetime.now_datetime();
			}
		});
		cy.get('.btn-primary[data-label="Save"], .primary-action').filter(':visible').first().click({ force: true });
		cy.wait(2000);
		cy.get("body").should("not.contain", "Incorrect datetime value");
		cy.get("body").should("not.contain", "NaN-NaN");
	});

	it("Gregorian → Jalali → Gregorian does not accumulate handlers", () => {
		cy.setCalendarPreference("Gregorian");
		cy.window().then((win) => {
			win.frappe.persian_calendar.runtime.resetDestroyLog();
		});
		cy.window().then((win) => openJobCard(win, fixture.job_card));
		cy.wait(1500);

		cy.setCalendarPreference("Jalali");
		cy.window().then((win) => {
			win.cur_frm?.refresh_fields();
			win.frappe.persian_calendar.runtime.resetCallCounts();
		});
		cy.wait(800);
		focusTimeLogDatetime("from_time");

		cy.setCalendarPreference("Gregorian");
		cy.window().then((win) => {
			win.cur_frm?.refresh_fields();
			win.frappe.persian_calendar.runtime.resetCallCounts();
		});
		cy.wait(800);
		focusTimeLogDatetime("from_time");

		cy.window().then((win) => {
			const rt = win.frappe.persian_calendar.runtime;
			const counts = rt.getCallCounts();
			expect(counts.valueToJalaliDisplay || 0).to.eq(0);
			expect(counts.parseJalaliDateTime || 0).to.eq(0);
			expect(counts.syncInputFromModel || 0).to.eq(0);

			const destroyLog = rt.getDestroyLog();
			expect(destroyLog.length).to.be.greaterThan(0);
		});
		cy.inspectGridDatetimeInput("from_time").then((info) => {
			expect(info.gregorianMode).to.eq(true);
			expect(info.hasJalaliAttr).to.eq(false);
			expect(info.hasJalaliInstance).to.eq(false);
			expect(info.hasNaN).to.eq(false);
			expect(info.hasInvalid).to.eq(false);
		});
	});
});
