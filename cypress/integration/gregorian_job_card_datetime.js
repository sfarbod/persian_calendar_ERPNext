/**
 * Regression: Gregorian Display Calendar + Job Card Datetime controls.
 *
 * Frappe ≥16.29 ControlDatetime.set_formatted_input calls this.sync_datepicker_state.
 * Without a JalaliControlDatetime delegate, opening Job Card blanks the page.
 *
 * Run (from apps/frappe):
 *   CYPRESS_BASE_URL=http://development.localhost:8000 CYPRESS_ADMIN_PASSWORD=admin \
 *   npx cypress run --config-file ../persian_calendar/cypress.config.js \
 *     --spec ../persian_calendar/cypress/integration/gregorian_job_card_datetime.js
 */

const JOB_CARD_ROUTE = "Form/Job Card";

function openJobCard(win, name) {
	win.frappe.set_route(JOB_CARD_ROUTE, name);
}

context("Gregorian Display Calendar — Job Card Datetime control", () => {
	let fixture = null;
	let consoleErrors = [];

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

	beforeEach(() => {
		consoleErrors = [];
		cy.on("window:before:load", (win) => {
			win.addEventListener("unhandledrejection", (ev) => {
				consoleErrors.push(String(ev.reason));
			});
		});
	});

	it("JalaliControlDatetime exposes sync_datepicker_state", () => {
		cy.window().then((win) => {
			const Proto = win.frappe.ui.form.ControlDatetime.prototype;
			expect(Proto.sync_datepicker_state, "sync_datepicker_state on ControlDatetime").to.be.a(
				"function"
			);
		});
	});

	it("opens existing Job Card with Display Calendar = Gregorian without blank page", () => {
		cy.setCalendarPreference("Gregorian");
		cy.window().then((win) => {
			expect(win.frappe.persian_calendar.runtime.shouldUseJalaliCalendarSync()).to.eq(false);
		});

		cy.window().then((win) => openJobCard(win, fixture.job_card));
		cy.wait(2500);

		cy.get(".form-layout, .form-page", { timeout: 15000 }).should("be.visible");
		cy.get("body").should("not.have.class", "ajax-state");
		cy.window().then((win) => {
			const cur = win.frappe.get_route?.() || win.frappe.router?.current || [];
			const joined = Array.isArray(cur) ? cur.join("/") : String(cur);
			expect(joined).to.match(/Job Card/i);
			const bad = consoleErrors.filter((m) => /sync_datepicker_state is not a function/i.test(m));
			expect(bad, `unhandled sync_datepicker_state errors: ${consoleErrors.join(" | ")}`).to.have
				.length(0);
		});

		// Time Logs Datetime inputs should exist / be interactable when present
		cy.get("body").then(($body) => {
			const $tab = $body.find(
				'.form-tabs-list [data-fieldname="actual_time"], .nav-link:contains("Actual Time")'
			);
			if ($tab.length) {
				cy.wrap($tab.first()).click({ force: true });
				cy.wait(400);
			}
		});
		cy.get(
			'.form-grid .frappe-control[data-fieldname="from_time"] input, .frappe-control[data-fieldname="from_time"] input'
		).then(($inputs) => {
			if ($inputs.length) {
				cy.wrap($inputs.first()).should("be.visible");
			}
		});
	});

	it("opens Job Card with Display Calendar = Jalali without blank page", () => {
		cy.setCalendarPreference("Jalali");
		cy.window().then((win) => {
			expect(win.frappe.persian_calendar.runtime.shouldUseJalaliCalendarSync()).to.eq(true);
		});
		cy.window().then((win) => openJobCard(win, fixture.job_card));
		cy.wait(2500);
		cy.get(".form-layout, .form-page", { timeout: 15000 }).should("be.visible");
		cy.window().then(() => {
			const bad = consoleErrors.filter((m) => /sync_datepicker_state is not a function/i.test(m));
			expect(bad).to.have.length(0);
		});
	});
});
