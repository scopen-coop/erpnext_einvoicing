# Copyright (c) 2026, Scopen and contributors
import frappe


def on_submit(doc, method):
	for ref in doc.references:
		if ref.reference_doctype != "Purchase Invoice":
			continue
		pi = frappe.get_doc("Purchase Invoice", ref.reference_name)
		if pi.outstanding_amount != 0:
			continue
		einvoice_name = frappe.db.get_value("ePurchase Invoice", {"purchase_invoice": pi.name}, "name")
		if not einvoice_name:
			continue

		already_sent = frappe.db.exists(
			"eInvoicing Lifecycle Log",
			{"parent": einvoice_name, "status_code": "211", "ack_status": "ok"},
		)
		if already_sent:
			continue

		try:
			from erpnext_einvoicing.providers.sync import _get_provider

			einvoice = frappe.get_doc("ePurchase Invoice", einvoice_name)
			_get_provider(einvoice.company).send_lifecycle("211", einvoice)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"eInvoicing lifecycle 211 — PI {pi.name}",
			)
