# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe


def after_migrate():
	_create_uom_mappings()
	_insert_refusal_reasons()
	_sync_supplier_custom_fields_to_ethirdparty()


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


def _sync_supplier_custom_fields_to_ethirdparty():
	supplier_fields = frappe.get_all(
		"Custom Field",
		filters={"dt": "Supplier", "reqd": 1},
		fields=[
			"fieldname",
			"label",
			"fieldtype",
			"options",
			"insert_after",
			"reqd",
			"default",
			"description",
			"hidden",
			"read_only",
		],
	)

	count = 0
	skipped = 0
	for row in supplier_fields:
		cf = frappe.new_doc("Custom Field")
		cf.dt = "eThirdParty"
		cf.fieldname = row.fieldname
		cf.label = row.label
		cf.fieldtype = row.fieldtype
		cf.options = row.options
		cf.insert_after = row.insert_after
		cf.reqd = 0
		cf.default = row.default
		cf.description = row.description
		cf.hidden = row.hidden
		cf.read_only = row.read_only

		try:
			cf.insert(ignore_permissions=True)
			count += 1
		except frappe.exceptions.ValidationError:
			skipped += 1

	if count or skipped:
		frappe.db.commit()
		print(f"[einvoicing] Custom Fields Supplier -> eThirdParty : {count} créé(s), {skipped} ignoré(s)")
