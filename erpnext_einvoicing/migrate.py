# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe


def after_migrate():
	_create_uom_mappings()


### Private


def _create_uom_mappings():
	frappe.db.sql("DELETE FROM `tabeInvoicing UOM Mapping`")

	mappings = [
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

	for unece_code, description, erpnext_uom in mappings:
		if not frappe.db.exists("UOM", erpnext_uom):
			continue
		doc = frappe.new_doc("eInvoicing UOM Mapping")
		doc.unece_code = unece_code
		doc.unece_description = description
		doc.erpnext_uom = erpnext_uom
		doc.insert(ignore_permissions=True)

	frappe.db.commit()
