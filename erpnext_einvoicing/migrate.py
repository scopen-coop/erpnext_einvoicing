# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt
import frappe


def after_migrate():
	_create_uom_mappings()
	_set_sandbox_system_message()


### Private


MAPPINGS = [
	("C62", "Unit", "Unité"),
	("PCE", "Piece", "Unité"),
	("KGM", "Kilogram", "Kg"),
	("GRM", "Gram", "Gram"),
	("TNE", "Tonne", "Tonne"),
	("LTR", "Litre", "Litre"),
	("MLT", "Millilitre", "Centilitre"),
	("MTR", "Metre", "Mètre"),
	("CMT", "Centimetre", "Centimeter"),
	("MTQ", "Cubic metre", "Cubic Meter"),
	("BX", "Box", "Box"),
]


def _create_uom_mappings():
	for unece_code, description, erpnext_uom in MAPPINGS:
		if not frappe.db.exists("UOM", erpnext_uom):
			continue
		try:
			doc = frappe.get_doc("eInvoicing UOM Mapping", unece_code)
		except frappe.DoesNotExistError:
			doc = frappe.new_doc("eInvoicing UOM Mapping")
			doc.unece_code = unece_code
		doc.unece_description = description
		doc.erpnext_uom = erpnext_uom
		doc.save(ignore_permissions=True)
	frappe.db.commit()


def _set_sandbox_system_message():
	if not frappe.conf.get("einvoicing_force_sandbox"):
		return
	msg = frappe._("eInvoicing sandbox mode active - CDARs are sent to PA test environments")
	frappe.db.set_single_value(
		"System Settings",
		"system_message",
		f'<i class="fa fa-exclamation-triangle"></i> {msg}',
	)
