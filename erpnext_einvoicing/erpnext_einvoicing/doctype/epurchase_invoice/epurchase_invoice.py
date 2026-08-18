# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ePurchaseInvoice(Document):
	def before_save(self):
		self._update_conversion_status()

	### Status

	def _update_conversion_status(self):
		if self.conversion_status in ("converted", "refused"):
			return
		self.conversion_status = "ready" if self._is_ready_for_conversion() else "pending"

	def _is_ready_for_conversion(self):
		if not self._supplier_ready():
			return False
		for item in self.items:
			if item.match_status not in ("matched", "created"):
				return False
			if not item.matched_item:
				return False
		company_doc = frappe.get_doc("Company", self.company)
		if company_doc.einvoicing_po_required:
			has_po = bool(self.purchase_order) or any(
				item.purchase_order for item in self.items if item.match_status == "matched"
			)
			if not has_po:
				return False
		if company_doc.einvoicing_pr_required:
			has_pr = bool(self.purchase_receipt) or any(
				item.purchase_receipt for item in self.items if item.match_status == "matched"
			)
			if not has_pr:
				return False
		return True

	def _supplier_ready(self):
		if self.supplier_match_status == "matched" and self.matched_supplier:
			return True
		if self.ethirdparty:
			status = frappe.db.get_value("eThirdParty", self.ethirdparty, "status")
			return status == "ready"
		return False

	### Conversion

	@frappe.whitelist()
	def convert_to_purchase_invoice(self):
		"""Creates a Purchase Invoice draft from this ePurchase Invoice."""
		if self.conversion_status == "converted":
			frappe.throw(
				frappe._("This ePurchase Invoice has already been converted."),
				title=frappe._("Already Converted"),
			)
		if not self._is_ready_for_conversion():
			frappe.throw(
				frappe._("Supplier and all items must be matched before conversion."),
				title=frappe._("Not Ready"),
			)

		from erpnext_einvoicing.erpnext_einvoicing.utils.conversion import build_purchase_invoice

		pi = build_purchase_invoice(self)
		self.db_set("conversion_status", "converted")

		already_sent = frappe.db.exists(
			"eInvoicing Lifecycle Log",
			{"parent": self.name, "status_code": "204", "ack_status": "ok"},
		)
		if not already_sent:
			try:
				from erpnext_einvoicing.erpnext_einvoicing.doctype.einvoicing_settings.einvoicing_settings import (
					get_provider,
				)

				settings = frappe.get_single("eInvoicing Settings")
				if settings.approved_platform:
					platform = frappe.get_doc("Approved Platforms", settings.approved_platform)
					provider = get_provider(settings, platform)
					provider.send_lifecycle("204", self)
			except Exception:
				frappe.log_error(frappe.get_traceback(), f"eInvoicing lifecycle 204 — {self.name}")

		return pi.name
