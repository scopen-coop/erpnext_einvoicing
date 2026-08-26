# Copyright (c) 2026, Scopen and contributors
import frappe


def on_submit(doc, method):
	"""Called on Purchase Invoice submit - placeholder for outgoing flow."""
	einvoice_name = frappe.db.get_value("ePurchase Invoice", {"purchase_invoice": doc.name}, "name")
	if not einvoice_name:
		return
	already_sent = frappe.db.exists(
		"eInvoicing Lifecycle Log",
		{"parent": einvoice_name, "status_code": "205", "ack_status": "ok"},
	)
	if already_sent:
		return
	try:
		from erpnext_einvoicing.providers.sync import _get_provider

		einvoice = frappe.get_doc("ePurchase Invoice", einvoice_name)
		provider = _get_provider(einvoice.company)
		provider.send_lifecycle("205", einvoice)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"eInvoicing lifecycle 205 - PI {doc.name}")


def on_cancel(doc, method):
	"""Remet l'ePurchase Invoice en ready quand la PI est annulée."""
	einvoice = frappe.db.get_value("ePurchase Invoice", {"purchase_invoice": doc.name}, "name")
	if einvoice:
		frappe.db.set_value("ePurchase Invoice", einvoice, "conversion_status", "ready")
		frappe.db.commit()
		frappe.msgprint(
			frappe._("ePurchase Invoice {0} has been reset to ready.").format(einvoice),
			alert=True,
		)


def on_trash(doc, method):
	"""Remet l'ePurchase Invoice en ready quand la PI est supprimée."""
	einvoice = frappe.db.get_value("ePurchase Invoice", {"purchase_invoice": doc.name}, "name")
	if einvoice:
		frappe.db.set_value(
			"ePurchase Invoice",
			einvoice,
			{
				"purchase_invoice": None,
				"conversion_status": "ready",
			},
		)
		frappe.db.commit()
		frappe.msgprint(
			frappe._("ePurchase Invoice {0} has been reset to ready.").format(einvoice),
			alert=True,
		)
