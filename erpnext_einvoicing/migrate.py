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
	content = ""
	if frappe.conf.get("einvoicing_force_sandbox"):
		live_companies = frappe.db.get_all(
			"Company",
			filters={"einvoicing_live_mode": 1},
			pluck="name",
		)
		if live_companies:
			names = ", ".join(live_companies)
			content = f'<div style="background:#e74c3c;color:#fff; width:100%; text-align:center;padding:10px;font-weight:bold;"><i class="fa fa-exclamation-triangle"></i> eInvoicing: live mode enabled on a non-production site - all PA communications will be redirected to test environments ({names})</div>'
	frappe.db.set_single_value("Navbar Settings", "announcement_widget", content)
