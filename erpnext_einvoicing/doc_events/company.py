# Copyright (c) 2026, Scopen and contributors
import frappe


def on_update(doc, method):
	update_sandbox_banner()


@frappe.whitelist()
def get_sandbox_banner():
	current = frappe.db.get_single_value("Navbar Settings", "announcement_widget") or ""
	return current if "einvoicing-sandbox-banner" in current else ""


def update_sandbox_banner():
	content = ""
	if frappe.conf.get("einvoicing_force_sandbox"):
		live_companies = frappe.db.get_all(
			"Company",
			filters={"einvoicing_live_mode": 1},
			pluck="name",
		)
		if live_companies:
			names = ", ".join(live_companies)
			message = frappe._(
				"eInvoicing: live mode enabled on a non-production site - REAL communications are sent to the PA ({0}). Will be reset to sandbox on next migrate."
			).format(names)
			content = (
				'<div class="einvoicing-sandbox-banner" style="background:#e74c3c;color:#fff;width:100%;'
				'text-align:center;padding:10px;font-weight:bold;">'
				f'<i class="fa fa-exclamation-triangle"></i> {message}</div>'
			)

	# Ne touche qu'à notre propre bandeau, pas aux annonces du client
	current = frappe.db.get_single_value("Navbar Settings", "announcement_widget") or ""
	is_ours = "einvoicing-sandbox-banner" in current or "eInvoicing: live mode enabled" in current
	if not current or is_ours:
		frappe.db.set_single_value("Navbar Settings", "announcement_widget", content)
