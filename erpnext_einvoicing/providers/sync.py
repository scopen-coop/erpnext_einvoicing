# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe

from erpnext_einvoicing.erpnext_einvoicing.doctype.einvoicing_settings.einvoicing_settings import (
	get_provider,
)

### Helpers


def _get_provider():
	settings = frappe.get_single("eInvoicing Settings")

	if not settings.approved_platform:
		frappe.throw(frappe._("No Approved Platform configured in eInvoicing Settings."))

	platform = frappe.get_doc("Approved Platforms", settings.approved_platform)

	if not platform.is_enabled:
		frappe.throw(frappe._("Platform '{0}' is disabled.").format(platform.name))

	return get_provider(settings, platform)


### Provider whitelisted methods


@frappe.whitelist()
def healthcheck():
	frappe.only_for("System Manager")
	return _get_provider().check_health()


@frappe.whitelist()
def recreate_access_token():
	frappe.only_for("System Manager")
	provider = _get_provider()
	try:
		provider.get_access_token()
		return {"status": "ok", "message": frappe._("Access token successfully generated.")}
	except frappe.ValidationError as e:
		return {"status": "error", "message": str(e)}
	except Exception as e:
		return {"status": "error", "message": frappe._("Unexpected error: {0}").format(str(e))}


@frappe.whitelist()
def delete_access_token():
	frappe.only_for("System Manager")
	provider = _get_provider()
	try:
		provider.delete_access_token()
		return {"status": "ok", "message": frappe._("Access token deleted.")}
	except Exception as e:
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def check_pending_flows(sync_type="Purchase Invoice"):
	frappe.only_for("System Manager")
	return _get_provider().check_pending_flows(sync_type)


@frappe.whitelist()
def sync_flows(sync_type="Purchase Invoice"):
	frappe.only_for("System Manager")
	return _get_provider().sync_flows(sync_type)


@frappe.whitelist()
def send_sample_invoice():
	frappe.only_for("System Manager")
	return _get_provider().send_sample_invoice()


### Inbox whitelisted methods


@frappe.whitelist()
def get_buying_settings():
	settings = frappe.get_single("eInvoicing Settings")
	return {
		"po_required": bool(settings.po_required),
		"pr_required": bool(settings.pr_required),
	}


@frappe.whitelist()
def link_purchase_order(name, purchase_order):
	frappe.db.set_value("ePurchase Invoice", name, "purchase_order", purchase_order)
	frappe.db.commit()
	return {"status": "ok"}


@frappe.whitelist()
def link_purchase_receipt(name, purchase_receipt):
	frappe.db.set_value("ePurchase Invoice", name, "purchase_receipt", purchase_receipt)
	frappe.db.commit()
	return {"status": "ok"}


@frappe.whitelist()
def get_einvoicing_inbox():
	invoices = frappe.get_all(
		"ePurchase Invoice",
		filters={"conversion_status": ["in", ["pending", "ready", "converted"]]},
		fields=[
			"name",
			"conversion_status",
			"invoice_number",
			"invoice_date",
			"currency",
			"total_ht",
			"total_vat",
			"total_ttc",
			"supplier_name_raw",
			"supplier_siret",
			"supplier_vat",
			"supplier_match_status",
			"matched_supplier",
			"purchase_order",
			"purchase_receipt",
			"approved_platform",
		],
		order_by="creation desc",
	)

	for inv in invoices:
		inv["items"] = frappe.get_all(
			"ePurchase Invoice Item",
			filters={"parent": inv["name"]},
			fields=[
				"idx",
				"item_description_raw",
				"item_ref_raw",
				"qty",
				"uom",
				"unit_price",
				"amount",
				"tax_rate",
				"match_status",
				"matched_item",
			],
			order_by="idx asc",
		)

	return invoices


@frappe.whitelist()
def match_supplier(name, matched_supplier):
	doc = frappe.get_doc("ePurchase Invoice", name)
	doc.matched_supplier = matched_supplier
	doc.supplier_match_status = "matched"
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok"}


@frappe.whitelist()
def unlink_matched_supplier(name):
	doc = frappe.get_doc("ePurchase Invoice", name)
	doc.matched_supplier = None
	doc.supplier_match_status = "unmatched"
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok"}


@frappe.whitelist()
def create_supplier_from_siret(name):
	import requests

	doc = frappe.get_doc("ePurchase Invoice", name)
	if not doc.supplier_siret:
		return {"status": "error", "error": frappe._("No SIRET on this invoice.")}

	siret = doc.supplier_siret.replace(" ", "")

	try:
		response = requests.get(
			"https://recherche-entreprises.api.gouv.fr/search",
			params={"q": siret, "per_page": 1},
			timeout=10,
		)
		response.raise_for_status()
		data = response.json()
	except Exception as e:
		return {"status": "error", "error": frappe._("SIRENE API error: {0}").format(str(e))}

	results = data.get("results", [])
	if not results:
		return {"status": "error", "error": frappe._("No company found for SIRET {0}.").format(siret)}

	company = results[0]
	supplier_name = company.get("nom_complet") or doc.supplier_name_raw

	if frappe.db.exists("Supplier", {"supplier_name": supplier_name}):
		existing = frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
		doc.matched_supplier = existing
		doc.supplier_match_status = "matched"
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		return {"status": "ok", "supplier": existing}

	supplier = frappe.new_doc("Supplier")
	supplier.supplier_name = supplier_name
	supplier.supplier_group = (
		frappe.db.get_single_value("Buying Settings", "supplier_group")
		or frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
		or frappe.db.get_value("Supplier Group", {}, "name")
	)
	supplier.tax_id = siret

	siege = company.get("siege", {})
	if siege.get("code_postal"):
		supplier.zip = siege["code_postal"]
	if siege.get("libelle_commune"):
		supplier.city = siege["libelle_commune"]

	supplier.insert(ignore_permissions=True)
	frappe.db.commit()

	doc.matched_supplier = supplier.name
	doc.supplier_match_status = "created"
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {"status": "ok", "supplier": supplier.name}


@frappe.whitelist()
def match_item(name, item_idx, matched_item):
	item_idx = int(item_idx)
	doc = frappe.get_doc("ePurchase Invoice", name)
	for item in doc.items:
		if item.idx == item_idx:
			item.matched_item = matched_item
			item.match_status = "matched"
			break
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok"}


@frappe.whitelist()
def unlink_matched_item(name, item_idx):
	item_idx = int(item_idx)
	doc = frappe.get_doc("ePurchase Invoice", name)
	for item in doc.items:
		if item.idx == item_idx:
			item.matched_item = None
			item.match_status = "unmatched"
			break
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok"}


@frappe.whitelist()
def create_item(name, item_idx, item_name, item_group):
	item_idx = int(item_idx)
	doc = frappe.get_doc("ePurchase Invoice", name)

	new_item = frappe.new_doc("Item")
	new_item.item_name = item_name
	new_item.item_group = item_group
	new_item.item_code = item_name
	new_item.is_purchase_item = 1
	new_item.insert(ignore_permissions=True)
	frappe.db.commit()

	for item in doc.items:
		if item.idx == item_idx:
			item.matched_item = new_item.name
			item.match_status = "created"
			break
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {"status": "ok", "item": new_item.name}


### Scheduled task


def sync_incoming_flows():
	"""Called by scheduler every 30 min (see hooks.py)."""
	try:
		result = _get_provider().sync_flows("Purchase Invoice")
		if result.get("status") == "error":
			frappe.log_error(result.get("message"), "eInvoicing scheduled sync error")
	except Exception:
		frappe.log_error(frappe.get_traceback(), "eInvoicing scheduled sync exception")
