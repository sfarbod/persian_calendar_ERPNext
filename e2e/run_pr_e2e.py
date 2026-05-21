#!/usr/bin/env python3
"""Focused E2E: Purchase Receipt MAT-PRE-2026-00075, System Default → Jalali, cur_frm.save()."""

from __future__ import annotations

import os
import sys

# Reuse full runner; only PR scenario E (+ minimal boot).
os.environ.setdefault("E2E_PURCHASE_RECEIPT", "MAT-PRE-2026-00075")
os.environ.setdefault("E2E_PR_ONLY", "1")
os.environ.setdefault("CYPRESS_ADMIN_PASSWORD", "admin")

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, E2E_DIR)

from run_cdp_e2e import main  # noqa: E402

if __name__ == "__main__":
	sys.exit(main())
