# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ePurchaseInvoice(Document):
	def before_save(self):
		self._update_conversion_status()

	### Status

	def _update_conversion_status(self):
		if self.conversion_status == "converted":
			return
		self.conversion_status = "ready" if self._is_ready_for_conversion() else "pending"

	def _is_ready_for_conversion(self) -> bool:
		if self.supplier_match_status not in ("matched", "created"):
			return False
		if not self.matched_supplier:
			return False
		for item in self.items:
			if item.match_status not in ("matched", "created"):
				return False
			if not item.matched_item:
				return False
		return True

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
		return pi.name


### Hook


def on_purchase_invoice_submit(doc, method):
	"""Called on Purchase Invoice submit — placeholder for outgoing flow."""
	pass
