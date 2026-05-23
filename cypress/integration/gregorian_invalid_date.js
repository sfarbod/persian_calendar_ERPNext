/**
 * E2E: no input or model value may become "Invalid date" in Gregorian preference.
 *
 * Run:
 *   cd apps/frappe && npx cypress run --config-file ../persian_calendar/cypress.config.js \
 *     --spec ../persian_calendar/cypress/integration/gregorian_invalid_date.js
 */

function assertNotInvalidDate(value, label) {
	expect(value, label).to.not.match(/Invalid\s*date/i);
	expect(String(value || "")).to.not.match(/NaN/i);
}

context("Gregorian mode never assigns Invalid date", () => {
	let jobFixture = null;

	before(() => {
		cy.login();
		cy.visit("/desk");
		cy.ensureJalaliAppEnabled();
		cy.createJobCardFixture().then((r) => {
			jobFixture = r?.message || r;
		});
	});

	after(() => {
		if (jobFixture) {
			cy.deleteJobCardFixture(jobFixture);
		}
	});

	beforeEach(() => {
		cy.setCalendarPreference("Gregorian");
		cy.enableInvalidDateWatch();
	});

	it("Job Card Time Logs from_time / to_time focus stays valid", () => {
		cy.window().then((win) => {
			win.frappe.set_route("Form", "Job Card", jobFixture.job_card);
		});
		cy.wait(2000);

		cy.get("body").then(($body) => {
			const $tab = $body.find(
				'.form-tabs-list [data-fieldname="actual_time"], .nav-link:contains("Actual Time")'
			);
			if ($tab.length) {
				cy.wrap($tab.first()).click({ force: true });
				cy.wait(400);
			}
		});

		["from_time", "to_time"].forEach((fieldname) => {
			cy.get(
				`.form-grid .frappe-control[data-fieldname="${fieldname}"] input, .form-in-grid .frappe-control[data-fieldname="${fieldname}"] input`
			)
				.filter(":visible")
				.first()
				.scrollIntoView()
				.click({ force: true })
				.focus({ force: true });
			cy.wait(400);

			cy.inspectGridDatetimeInput(fieldname).then((info) => {
				assertNotInvalidDate(info.value, `${fieldname} input`);
				expect(info.hasInvalid, `${fieldname} hasInvalid`).to.eq(false);
			});

			cy.window().then((win) => {
				const frm = win.cur_frm;
				const row = frm?.doc?.time_logs?.[0];
				if (row) {
					assertNotInvalidDate(row[fieldname], `${fieldname} model`);
				}
			});
		});

		cy.assertInvalidDateLogEmpty();
	});

	it("Stock Entry posting_time focus stays valid", () => {
		cy.window().then((win) => {
			win.frappe.set_route("Form", "Stock Entry", "new-stock-entry-1");
		});
		cy.wait(2500);

		cy.get('.frappe-control[data-fieldname="posting_time"] input')
			.filter(":visible")
			.first()
			.scrollIntoView()
			.click({ force: true })
			.focus({ force: true });
		cy.wait(500);

		cy.get('.frappe-control[data-fieldname="posting_time"] input')
			.filter(":visible")
			.first()
			.invoke("val")
			.then((val) => {
				assertNotInvalidDate(val, "posting_time input");
			});

		cy.window().then((win) => {
			const pt = win.cur_frm?.doc?.posting_time;
			assertNotInvalidDate(pt, "posting_time model");
		});

		cy.assertInvalidDateLogEmpty();
	});
});
