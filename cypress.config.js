const { defineConfig } = require("cypress");

module.exports = defineConfig({
	adminPassword: process.env.CYPRESS_ADMIN_PASSWORD || "admin",
	testUser: process.env.CYPRESS_TEST_USER || "Administrator",
	defaultCommandTimeout: 30000,
	pageLoadTimeout: 60000,
	viewportHeight: 900,
	viewportWidth: 1400,
	video: true,
	e2e: {
		baseUrl: process.env.CYPRESS_BASE_URL || "http://development.localhost:8000",
		specPattern: "cypress/integration/**/*.js",
		supportFile: "cypress/support/e2e.js",
		testIsolation: false,
	},
});
