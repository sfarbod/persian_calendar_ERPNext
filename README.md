### Persian Calendar

Jalali desk support and **Company Business Calendar** for ERPNext (Frappe v16).

**Current version:** **1.9.0** — see [`CHANGELOG.md`](CHANGELOG.md) and [`docs/RELEASE_NOTES_1.9.0.md`](docs/RELEASE_NOTES_1.9.0.md).

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app persian_calendar
```

After install/upgrade:

```bash
bench migrate
bench build --app persian_calendar
bench --site <site> clear-cache
bench --site <site> execute persian_calendar.calendar.diagnostics.release_check
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/persian_calendar
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
