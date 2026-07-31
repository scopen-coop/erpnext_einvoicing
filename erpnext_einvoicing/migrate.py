# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe


def after_migrate():
	_create_uom_mappings()
	_create_tax_mappings()


### Private


def _create_uom_mappings():
	mappings = [
		("C62", "Unit", "Nos"),
		("KGM", "Kilogram", "Kg"),
		("GRM", "Gram", "Gram"),
		("TNE", "Tonne", "Tonne"),
		("LTR", "Litre", "Litre"),
		("MLT", "Millilitre", "mL"),
		("MTR", "Metre", "Metre"),
		("CMT", "Centimetre", "Cm"),
		("MMT", "Millimetre", "mm"),
		("MTK", "Square metre", "Sq Meter"),
		("MTQ", "Cubic metre", "Cubic Meter"),
		("HUR", "Hour", "Hour"),
		("DAY", "Day", "Day"),
		("MON", "Month", "Month"),
		("ANN", "Year", "Year"),
		("PCE", "Piece", "Nos"),
		("SET", "Set", "Set"),
		("PAK", "Pack", "Nos"),
		("BX", "Box", "Box"),
		("RL", "Roll", "Roll"),
	]

	for unece_code, description, erpnext_uom in mappings:
		if frappe.db.exists("eInvoicing UOM Mapping", unece_code):
			continue
		if not frappe.db.exists("UOM", erpnext_uom):
			continue
		doc = frappe.new_doc("eInvoicing UOM Mapping")
		doc.unece_code = unece_code
		doc.unece_description = description
		doc.erpnext_uom = erpnext_uom
		doc.insert(ignore_permissions=True)

	frappe.db.commit()


def _create_tax_mappings():
	mappings = [
		("20.0", "TVA 20%"),
		("10.0", "TVA 10%"),
		("5.5", "TVA 5.5%"),
		("2.1", "TVA 2.1%"),
		("0.0", "Exonéré / Hors TVA"),
	]
	for tax_rate, description in mappings:
		if frappe.db.exists("eInvoicing Tax Mapping", tax_rate):
			continue
		doc = frappe.new_doc("eInvoicing Tax Mapping")
		doc.tax_rate = tax_rate
		doc.description = description
		doc.insert(ignore_permissions=True)
	frappe.db.commit()
