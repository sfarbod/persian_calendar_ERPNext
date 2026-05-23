Cypress.Commands.add("login", (email, password) => {
	if (!email) {
		email = Cypress.config("testUser") || "Administrator";
	}
	if (!password) {
		password = Cypress.env("adminPassword") || Cypress.config("adminPassword");
	}
	return cy.session([email, password], () => {
		return cy.request({
			url: "/api/method/login",
			method: "POST",
			body: { usr: email, pwd: password },
			failOnStatusCode: true,
		});
	});
});

Cypress.Commands.add("deskVisit", (route) => {
	cy.visit("/desk");
	cy.window().its("frappe.session.user").should("not.eq", "Guest");
	if (route) {
		cy.window().then((win) => {
			win.frappe.set_route(route);
		});
		cy.wait(1500);
	}
});

Cypress.Commands.add("setCalendarPreference", (preference) => {
	cy.window().then((win) => {
		const frappe = win.frappe;
		const user = frappe.session.user;
		return frappe
			.call("frappe.client.set_value", {
				doctype: "User",
				name: user,
				fieldname: "calendar_preference",
				value: preference,
			})
			.then(() => {
				const rt = frappe.persian_calendar?.runtime;
				if (rt) {
					rt.invalidateCalendarSettingsCache();
					rt.updateBootFromUserCalendarPreference(preference);
					return rt.fetchCalendarSettings();
				}
			});
	});
});

Cypress.Commands.add("ensureJalaliAppEnabled", () => {
	cy.window().then((win) => {
		const frappe = win.frappe;
		return frappe.db
			.get_doc("Jalali Settings", "Jalali Settings")
			.then((doc) => {
				if (!doc.enabled) {
					return frappe.db.set_value("Jalali Settings", doc.name, "enabled", 1);
				}
			})
			.catch(() => {
				// single doc name may differ; ignore if missing in minimal sites
			});
	});
});

Cypress.Commands.add("inspectGridDatetimeInput", (fieldname) => {
	return cy
		.get(
			`.form-grid .frappe-control[data-fieldname="${fieldname}"] input, .form-in-grid .frappe-control[data-fieldname="${fieldname}"] input`
		)
		.first()
		.then(($input) => {
			return cy.window().then((win) => {
				return win.frappe.persian_calendar.runtime.inspectDatetimeInput($input[0]);
			});
		});
});

Cypress.Commands.add("createJobCardFixture", () => {
	return cy.window().then((win) => {
		return win.frappe.call(
			"persian_calendar.jalali_support.e2e_fixtures.create_job_card_time_log_fixture"
		);
	});
});

Cypress.Commands.add("deleteJobCardFixture", (payload) => {
	if (!payload) return;
	return cy.window().then((win) => {
		return win.frappe.call(
			"persian_calendar.jalali_support.e2e_fixtures.delete_job_card_time_log_fixture",
			{ payload: JSON.stringify(payload) }
		);
	});
});

Cypress.Commands.add("resetPersianCalendarCounters", () => {
	return cy.window().then((win) => {
		win.frappe.persian_calendar.runtime.resetDestroyLog();
		win.frappe.persian_calendar.runtime.resetCallCounts();
	});
});

Cypress.Commands.add("enableInvalidDateWatch", () => {
	cy.window().then((win) => {
		win.frappe.persian_calendar.runtime.enableInvalidDateWatch();
		win.frappe.persian_calendar.runtime.resetInvalidDateLog();
	});
});

Cypress.Commands.add("assertInvalidDateLogEmpty", () => {
	cy.window().then((win) => {
		const log = win.frappe.persian_calendar.runtime.getInvalidDateLog();
		expect(log, "Invalid date watch log").to.have.length(0);
	});
});
