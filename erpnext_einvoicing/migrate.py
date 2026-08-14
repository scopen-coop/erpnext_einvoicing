# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe


def after_migrate():
	_create_uom_mappings()
	_insert_refusal_reasons()
	_create_custom_fields()


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


REFUSAL_REASONS = [
	{"reason_code": "TX_TVA_ERR", "reason_label": "Taux de TVA erroné"},
	{"reason_code": "MONTANTTOTAL_ERR", "reason_label": "Montant total erroné"},
	{"reason_code": "CALCUL_ERR", "reason_label": "Erreur de calcul"},
	{"reason_code": "NON_CONFORME", "reason_label": "Non conforme"},
	{"reason_code": "DOUBLON", "reason_label": "Doublon"},
	{"reason_code": "DEST_ERR", "reason_label": "Destinataire erroné"},
	{"reason_code": "TRANSAC_INC", "reason_label": "Transaction incomplète"},
	{"reason_code": "EMMET_INC", "reason_label": "Émetteur incorrect"},
	{"reason_code": "CONTRAT_TERM", "reason_label": "Contrat terminé"},
	{"reason_code": "DOUBLE_FACT", "reason_label": "Double facturation"},
	{"reason_code": "CMD_ERR", "reason_label": "Commande erronée"},
	{"reason_code": "ADR_ERR", "reason_label": "Adresse erronée"},
	{"reason_code": "REF_CT_ABSENT", "reason_label": "Référence contrat absente"},
]


def _insert_refusal_reasons():
	for r in REFUSAL_REASONS:
		if not frappe.db.exists("eInvoicing Refusal Reason", r["reason_code"]):
			doc = frappe.new_doc("eInvoicing Refusal Reason")
			doc.reason_code = r["reason_code"]
			doc.reason_label = r["reason_label"]
			doc.insert(ignore_permissions=True)
	frappe.db.commit()


def _create_custom_fields():
	if not frappe.db.exists("Custom Field", "Purchase Invoice Item-po_match_status"):
		frappe.get_doc(
			{
				"doctype": "Custom Field",
				"dt": "Purchase Invoice Item",
				"fieldname": "po_match_status",
				"label": "PO Match Status",
				"fieldtype": "Select",
				"options": "\nmatched\npartial\nambiguous",
				"read_only": 1,
				"in_list_view": 1,
				"insert_after": "amount",
			}
		).insert(ignore_permissions=True)
	frappe.db.commit()
