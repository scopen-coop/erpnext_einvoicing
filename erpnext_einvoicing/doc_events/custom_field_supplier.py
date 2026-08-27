# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe

ORIGIN_DOCTYPE = "Supplier"
TARGET_DOCTYPE = "eThirdParty"


def on_create(doc, method=None):
	if doc.dt != ORIGIN_DOCTYPE:
		return
	if doc.reqd != 1:
		return
	cf = frappe.new_doc("Custom Field")
	cf.dt = TARGET_DOCTYPE
	cf.fieldname = doc.fieldname
	cf.label = doc.label
	cf.fieldtype = doc.fieldtype
	cf.options = doc.options
	cf.insert_after = "matched_party"
	cf.reqd = 0
	cf.default = doc.default
	cf.description = doc.description
	cf.hidden = doc.hidden
	cf.read_only = doc.read_only
	try:
		cf.insert(ignore_permissions=True)
		frappe.db.commit()
		print(f"[einvoicing] Custom Field {doc.fieldname} mirrored to {TARGET_DOCTYPE}")
	except frappe.exceptions.ValidationError:
		pass


def on_update(doc, method=None):
	if doc.dt != ORIGIN_DOCTYPE:
		return
	mirror_name = frappe.db.get_value("Custom Field", {"dt": TARGET_DOCTYPE, "fieldname": doc.fieldname})
	if not mirror_name:
		if doc.reqd == 1:
			on_create(doc, method)
		return
	if doc.reqd != 1:
		on_delete(doc, method)
		return
	cf = frappe.get_doc("Custom Field", mirror_name)
	cf.label = doc.label
	cf.fieldtype = doc.fieldtype
	cf.options = doc.options
	cf.default = doc.default
	cf.description = doc.description
	cf.hidden = doc.hidden
	cf.read_only = doc.read_only
	cf.save(ignore_permissions=True)
	frappe.db.commit()
	print(f"[einvoicing] Custom Field {doc.fieldname} updated on {TARGET_DOCTYPE}")


def on_delete(doc, method=None):
	if doc.dt != ORIGIN_DOCTYPE:
		return
	mirror_name = frappe.db.get_value("Custom Field", {"dt": TARGET_DOCTYPE, "fieldname": doc.fieldname})
	if not mirror_name:
		return
	frappe.delete_doc("Custom Field", mirror_name, ignore_permissions=True)
	frappe.db.commit()
