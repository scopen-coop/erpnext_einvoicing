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
	try:
		return _get_provider().check_pending_flows(sync_type)
	except Exception as e:
		return {"has_pending": False, "total": 0, "error": str(e)}


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
def get_einvoicing_inbox(date_from=None, date_to=None):
	filters = {"conversion_status": ["in", ["pending", "ready", "converted", "refused"]]}
	if date_from and date_to:
		filters["invoice_date"] = ["between", [date_from, date_to]]
	elif date_from:
		filters["invoice_date"] = [">=", date_from]
	elif date_to:
		filters["invoice_date"] = ["<=", date_to]
	invoices = frappe.get_all(
		"ePurchase Invoice",
		filters=filters,
		fields=[
			"name",
			"conversion_status",
			"purchase_invoice",
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
			"sirene_status",
			"matched_supplier",
			"ethirdparty",
			"purchase_order",
			"purchase_receipt",
			"approved_platform",
			"purchase_invoice",
			"company",
			"buyer_siret",
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

		attachment = frappe.db.get_value(
			"File",
			{
				"attached_to_doctype": "ePurchase Invoice",
				"attached_to_name": inv["name"],
			},
			"file_url",
		)
		inv["pdf_url"] = attachment or None

		last_log_list = frappe.get_all(
			"eInvoicing Lifecycle Log",
			filters={"parent": inv["name"]},
			fields=["name", "status_code", "status_label", "ack_status", "ack_message", "error_type"],
			order_by="sent_at desc",
			limit=1,
		)
		inv["last_lifecycle_log"] = last_log_list[0] if last_log_list else None

		company = inv.get("company")
		for item in inv["items"]:
			if item.get("tax_rate") and company:
				item["tax_account_name"] = frappe.db.get_value(
					"Account",
					{
						"company": company,
						"account_type": "Tax",
						"tax_rate": item["tax_rate"],
						"root_type": "Asset",
					},
					"account_name",
				)
			else:
				item["tax_account_name"] = None

		if inv.get("ethirdparty"):
			inv["ethirdparty_doc"] = frappe.db.get_value(
				"eThirdParty",
				inv["ethirdparty"],
				[
					"name",
					"status",
					"party_name",
					"siret",
					"zip",
					"city",
					"country_code",
					"categorie_comptable_tiers",
				],
				as_dict=True,
			)

	return invoices


@frappe.whitelist()
def match_supplier(name, matched_supplier, apply_to_all=0):
	apply_to_all = frappe.utils.cint(apply_to_all)

	### Vérification cohérence SIRET
	siret = frappe.db.get_value("ePurchase Invoice", name, "supplier_siret")
	if siret:
		existing_siret = frappe.db.get_value("Supplier", matched_supplier, "siret")
		existing_siren = frappe.db.get_value("Supplier", matched_supplier, "siren")
		existing_tax_id = frappe.db.get_value("Supplier", matched_supplier, "tax_id")

		supplier_identifiers = {v for v in [existing_siret, existing_siren, existing_tax_id] if v}

		if supplier_identifiers:
			siret_match = any(
				siret.startswith(id) or id.startswith(siret) or siret == id for id in supplier_identifiers
			)
			if not siret_match:
				return {
					"status": "warning",
					"message": frappe._(
						"Supplier '{0}' identifiers ({1}) don't match invoice SIRET {2}."
					).format(
						matched_supplier,
						", ".join(supplier_identifiers),
						siret,
					),
				}

	frappe.db.set_value(
		"ePurchase Invoice",
		name,
		{
			"matched_supplier": matched_supplier,
			"supplier_match_status": "matched",
		},
	)

	from erpnext_einvoicing.erpnext_einvoicing.utils.facturx import _auto_match_items

	doc = frappe.get_doc("ePurchase Invoice", name)
	_auto_match_items(doc)
	doc._update_conversion_status()
	doc.db_set("conversion_status", doc.conversion_status)

	if apply_to_all and siret:
		others = frappe.get_all(
			"ePurchase Invoice",
			filters={
				"supplier_siret": siret,
				"name": ["!=", name],
				"supplier_match_status": "unmatched",
				"conversion_status": ["!=", "converted"],
			},
			pluck="name",
		)
		for other in others:
			frappe.db.set_value(
				"ePurchase Invoice",
				other,
				{
					"matched_supplier": matched_supplier,
					"supplier_match_status": "matched",
				},
			)
			inv = frappe.get_doc("ePurchase Invoice", other)
			inv._update_conversion_status()
			inv.db_set("conversion_status", inv.conversion_status)

	frappe.db.commit()

	doc.reload()
	matched_count = sum(1 for item in doc.items if item.match_status == "matched")
	return {
		"status": "ok",
		"supplier": matched_supplier,
		"matched_items": matched_count,
		"total_items": len(doc.items),
		"conversion_status": doc.conversion_status,
	}


@frappe.whitelist()
def count_similar_unmatched(name, match_type):
	doc = frappe.get_doc("ePurchase Invoice", name)

	if match_type == "supplier":
		if not doc.supplier_siret:
			return {"count": 0}
		count = frappe.db.count(
			"ePurchase Invoice",
			{
				"supplier_siret": doc.supplier_siret,
				"name": ["!=", name],
				"supplier_match_status": "unmatched",
				"conversion_status": ["!=", "converted"],
			},
		)
		return {"count": count}

	if match_type == "item":
		item_idx = frappe.form_dict.get("item_idx")
		if not item_idx:
			return {"count": 0}
		doc = frappe.get_doc("ePurchase Invoice", name)
		ref_raw = next((i.item_ref_raw for i in doc.items if i.idx == int(item_idx)), None)
		if not ref_raw:
			return {"count": 0}
		count = frappe.db.count(
			"ePurchase Invoice Item",
			{
				"item_ref_raw": ref_raw,
				"match_status": "unmatched",
				"parent": ["!=", name],
			},
		)
		return {"count": count}

	if match_type == "supplier_matched":
		siret = frappe.db.get_value("ePurchase Invoice", name, "supplier_siret")
		if not siret:
			return {"count": 0}
		count = frappe.db.count(
			"ePurchase Invoice",
			{
				"supplier_siret": siret,
				"name": ["!=", name],
				"supplier_match_status": "matched",
				"conversion_status": ["!=", "converted"],
			},
		)
		return {"count": count}

	if match_type == "item_matched":
		item_idx = frappe.form_dict.get("item_idx")
		if not item_idx:
			return {"count": 0}
		doc = frappe.get_doc("ePurchase Invoice", name)
		ref_raw = next((i.item_ref_raw for i in doc.items if i.idx == int(item_idx)), None)
		if not ref_raw:
			return {"count": 0}
		count = frappe.db.count(
			"ePurchase Invoice Item",
			{
				"item_ref_raw": ref_raw,
				"match_status": "matched",
				"parent": ["!=", name],
			},
		)
		return {"count": count}

	return {"count": 0}


@frappe.whitelist()
def rematch_supplier(name):
	doc = frappe.get_doc("ePurchase Invoice", name)
	siret = (doc.supplier_siret or "").replace(" ", "")
	name_raw = doc.supplier_name_raw or ""

	if siret:
		supplier = frappe.db.get_value("Supplier", {"tax_id": siret}, "name")
		if supplier:
			doc.db_set("matched_supplier", supplier)
			doc.db_set("supplier_match_status", "matched")
			frappe.db.commit()
			return {"status": "ok", "supplier": supplier}

	if name_raw:
		supplier = frappe.db.get_value(
			"Supplier",
			{"supplier_name": ["like", f"%{name_raw}%"]},
			"name",
		)
		if supplier:
			doc.db_set("matched_supplier", supplier)
			doc.db_set("supplier_match_status", "matched")
			frappe.db.commit()
			return {"status": "ok", "supplier": supplier}

	return {"status": "not_found"}


def _rematch_all_pending():
	invoices = frappe.get_all(
		"ePurchase Invoice",
		filters={"conversion_status": ["in", ["pending", "ready"]]},
		pluck="name",
	)
	for name in invoices:
		doc = frappe.get_doc("ePurchase Invoice", name)
		if doc.supplier_match_status == "unmatched":
			from erpnext_einvoicing.erpnext_einvoicing.utils.facturx import _auto_match_supplier

			_auto_match_supplier(
				doc,
				{
					"supplier_siret": doc.supplier_siret,
					"supplier_name_raw": doc.supplier_name_raw,
				},
			)
		from erpnext_einvoicing.erpnext_einvoicing.utils.facturx import _auto_match_items

		_auto_match_items(doc)


@frappe.whitelist()
def unlink_matched_supplier(name, apply_to_all=0):
	apply_to_all = frappe.utils.cint(apply_to_all)
	doc = frappe.get_doc("ePurchase Invoice", name)
	siret = doc.supplier_siret
	ethirdparty_name = doc.ethirdparty

	frappe.db.set_value(
		"ePurchase Invoice",
		name,
		{
			"matched_supplier": None,
			"supplier_match_status": "unmatched",
			"ethirdparty": None,
			"sirene_status": None,
			"conversion_status": "pending",
		},
	)

	doc.reload()
	for item in doc.items:
		item.matched_item = None
		item.match_status = "unmatched"
	doc.save(ignore_permissions=True)

	if apply_to_all and siret:
		others = frappe.get_all(
			"ePurchase Invoice",
			filters={
				"supplier_siret": siret,
				"name": ["!=", name],
				"conversion_status": ["!=", "converted"],
			},
			pluck="name",
		)
		for other_name in others:
			frappe.db.set_value(
				"ePurchase Invoice",
				other_name,
				{
					"matched_supplier": None,
					"supplier_match_status": "unmatched",
					"ethirdparty": None,
					"sirene_status": None,
					"conversion_status": "pending",
				},
			)
			other_doc = frappe.get_doc("ePurchase Invoice", other_name)
			for item in other_doc.items:
				item.matched_item = None
				item.match_status = "unmatched"
			other_doc.save(ignore_permissions=True)

	if ethirdparty_name:
		others = frappe.db.count("ePurchase Invoice", {"ethirdparty": ethirdparty_name})
		if not others:
			frappe.delete_doc("eThirdParty", ethirdparty_name, ignore_permissions=True)

	frappe.db.commit()
	return {"status": "ok"}


@frappe.whitelist()
def enrich_from_siret(name):
	import requests as req

	doc = frappe.get_doc("ePurchase Invoice", name)

	siret = (doc.supplier_siret or "").replace(" ", "")
	if not siret:
		return {"status": "error", "error": frappe._("No SIRET on this invoice.")}

	ethirdparty_name = doc.ethirdparty or frappe.db.get_value("eThirdParty", {"siret": siret}, "name")

	if ethirdparty_name:
		ethirdparty = frappe.get_doc("eThirdParty", ethirdparty_name)
	else:
		ethirdparty = frappe.new_doc("eThirdParty")
		ethirdparty.party_type = "Supplier"
		ethirdparty.siret = siret
		ethirdparty.vat_number = doc.supplier_vat or ""
		ethirdparty.party_name = doc.supplier_name_raw or ""
		ethirdparty.status = "pending"
		ethirdparty.insert(ignore_permissions=True)
		doc.db_set("ethirdparty", ethirdparty.name)
		frappe.db.commit()

	try:
		response = req.get(
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
		frappe.db.set_value("ePurchase Invoice", name, "sirene_status", "not_found")
		frappe.db.commit()
		return {"status": "not_found"}

	company = results[0]
	siege = company.get("siege", {})

	ethirdparty.party_name = company.get("nom_complet") or ethirdparty.party_name
	ethirdparty.address_line1 = siege.get("adresse", "")
	ethirdparty.zip = siege.get("code_postal", "")
	ethirdparty.city = siege.get("libelle_commune", "")
	ethirdparty.country_code = "FR"
	ethirdparty.sirene_raw = frappe.as_json(company)

	### Dry-run validation
	import json as _json

	test_supplier = frappe.new_doc("Supplier")
	test_supplier.supplier_name = ethirdparty.party_name
	test_supplier.supplier_group = frappe.db.get_single_value(
		"Buying Settings", "supplier_group"
	) or frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	test_supplier.tax_id = siret
	test_supplier.categorie_comptable_tiers = "France"

	missing_fields = [
		field.label
		for field in frappe.get_meta("Supplier").fields
		if field.reqd and not test_supplier.get(field.fieldname)
	]

	try:
		test_supplier.run_method("validate")
	except Exception as e:
		missing_fields.append(str(e))

	if missing_fields:
		ethirdparty.status = "warning"
		ethirdparty.save(ignore_permissions=True)
		frappe.db.commit()
		return {
			"status": "warning",
			"ethirdparty": ethirdparty.as_dict(),
			"missing_fields": missing_fields,
		}

	status = "warning" if missing_fields else "ok"
	return {
		"status": status,
		"data": {
			"siret": siret,
			"party_name": ethirdparty.party_name,
			"address_line1": ethirdparty.address_line1,
			"zip": ethirdparty.zip,
			"city": ethirdparty.city,
			"country_code": ethirdparty.country_code,
			"categorie_comptable_tiers": ethirdparty.categorie_comptable_tiers,
		},
		"missing_fields": missing_fields,
	}


@frappe.whitelist()
def save_ethirdparty(invoice_name, data, supplier_group, apply_to_all=0):
	apply_to_all = frappe.utils.cint(apply_to_all)
	if isinstance(data, str):
		import json

		data = json.loads(data)

	doc = frappe.get_doc("ePurchase Invoice", invoice_name)
	siret = data.get("siret", "")

	ethirdparty_name = doc.ethirdparty or frappe.db.get_value("eThirdParty", {"siret": siret}, "name")

	if ethirdparty_name:
		ethirdparty = frappe.get_doc("eThirdParty", ethirdparty_name)
	else:
		ethirdparty = frappe.new_doc("eThirdParty")
		ethirdparty.party_type = "Supplier"
		ethirdparty.siret = siret

	ethirdparty.party_name = data.get("party_name", "")
	ethirdparty.address_line1 = data.get("address_line1", "")
	ethirdparty.zip = data.get("zip", "")
	ethirdparty.city = data.get("city", "")
	ethirdparty.country_code = data.get("country_code", "")
	ethirdparty.categorie_comptable_tiers = data.get("categorie_comptable_tiers", "")
	ethirdparty.status = "ready"
	ethirdparty.save(ignore_permissions=True)
	frappe.db.commit()

	doc.db_set("ethirdparty", ethirdparty.name)
	frappe.db.set_value("ePurchase Invoice", invoice_name, "sirene_status", "ok")

	from erpnext_einvoicing.erpnext_einvoicing.utils.facturx import _auto_match_items

	_auto_match_items(doc)

	if apply_to_all and siret:
		others = frappe.get_all(
			"ePurchase Invoice",
			filters={
				"supplier_siret": siret,
				"name": ["!=", invoice_name],
				"conversion_status": ["!=", "converted"],
			},
			pluck="name",
		)
		for other in others:
			frappe.db.set_value(
				"ePurchase Invoice",
				other,
				{
					"ethirdparty": ethirdparty.name,
					"sirene_status": "ok",
				},
			)

	frappe.db.commit()
	doc.reload()
	matched_count = sum(1 for item in doc.items if item.match_status == "matched")
	return {
		"status": "ok",
		"supplier": ethirdparty.party_name,
		"matched_items": matched_count,
		"total_items": len(doc.items),
		"conversion_status": doc.conversion_status,
		"ethirdparty": ethirdparty.name,
	}


@frappe.whitelist()
def unlink_ethirdparty(name, apply_to_all=0):
	apply_to_all = frappe.utils.cint(apply_to_all)
	doc = frappe.get_doc("ePurchase Invoice", name)
	ethirdparty_name = doc.ethirdparty
	siret = doc.supplier_siret

	if ethirdparty_name:
		frappe.db.set_value(
			"ePurchase Invoice",
			{"ethirdparty": ethirdparty_name},
			{"ethirdparty": None, "supplier_match_status": "unmatched", "sirene_status": None},
		)
		frappe.delete_doc("eThirdParty", ethirdparty_name, ignore_permissions=True)

	if apply_to_all and siret:
		frappe.db.set_value(
			"ePurchase Invoice",
			{"supplier_siret": siret, "conversion_status": ["!=", "converted"]},
			{"ethirdparty": None, "supplier_match_status": "unmatched", "sirene_status": None},
		)

	frappe.db.commit()
	return {"status": "ok"}


@frappe.whitelist()
def update_ethirdparty(name, data):
	if isinstance(data, str):
		import json

		data = json.loads(data)
	doc = frappe.get_doc("eThirdParty", name)
	for field, value in data.items():
		doc.set(field, value)
	doc.status = "ready"
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok"}


@frappe.whitelist()
def update_item_tax_rate(name, item_idx, tax_rate):
	item_idx = int(item_idx)
	doc = frappe.get_doc("ePurchase Invoice", name)
	for item in doc.items:
		if item.idx == item_idx:
			item.tax_rate = float(tax_rate) if tax_rate else 0
			break
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok"}


@frappe.whitelist()
def match_item(name, item_idx, matched_item, apply_to_all=0):
	apply_to_all = frappe.utils.cint(apply_to_all)
	item_idx = int(item_idx)
	doc = frappe.get_doc("ePurchase Invoice", name)

	ref_raw = None
	for item in doc.items:
		if item.idx == item_idx:
			item.matched_item = matched_item
			item.match_status = "matched"
			ref_raw = item.item_ref_raw
			break

	if apply_to_all and ref_raw:
		for item in doc.items:
			if item.item_ref_raw == ref_raw and item.match_status == "unmatched":
				item.matched_item = matched_item
				item.match_status = "matched"

	doc.save(ignore_permissions=True)
	doc.reload()
	doc._update_conversion_status()
	doc.db_set("conversion_status", doc.conversion_status)

	if apply_to_all and ref_raw:
		_apply_item_match_to_all(name, ref_raw, matched_item)

	frappe.db.commit()
	return {"status": "ok"}


def _apply_item_match_to_all(exclude_name, item_ref_raw, matched_item):
	"""Applique le match item à toutes les lignes avec la même référence fournisseur."""
	invoices = frappe.get_all(
		"ePurchase Invoice",
		filters={"name": ["!=", exclude_name], "conversion_status": ["!=", "converted"]},
		pluck="name",
	)
	for inv_name in invoices:
		inv = frappe.get_doc("ePurchase Invoice", inv_name)
		updated = False
		for item in inv.items:
			if item.item_ref_raw == item_ref_raw and item.match_status == "unmatched":
				item.matched_item = matched_item
				item.match_status = "matched"
				updated = True
		if updated:
			inv.save(ignore_permissions=True)


@frappe.whitelist()
def rematch_items(name):
	from erpnext_einvoicing.erpnext_einvoicing.utils.facturx import _auto_match_items

	doc = frappe.get_doc("ePurchase Invoice", name)
	_auto_match_items(doc)
	return {"status": "ok"}


@frappe.whitelist()
def unlink_matched_item(name, item_idx, apply_to_all=0):
	apply_to_all = frappe.utils.cint(apply_to_all)
	item_idx = int(item_idx)
	doc = frappe.get_doc("ePurchase Invoice", name)

	ref_raw = None
	for item in doc.items:
		if item.idx == item_idx:
			ref_raw = item.item_ref_raw
			item.matched_item = None
			item.match_status = "unmatched"
			break

	if apply_to_all and ref_raw:
		for item in doc.items:
			if item.item_ref_raw == ref_raw and item.match_status == "matched":
				item.matched_item = None
				item.match_status = "unmatched"

	doc.save(ignore_permissions=True)
	doc.reload()
	doc._update_conversion_status()
	doc.db_set("conversion_status", doc.conversion_status)

	if apply_to_all and ref_raw:
		invoices = frappe.get_all(
			"ePurchase Invoice",
			filters={"name": ["!=", name], "conversion_status": ["!=", "converted"]},
			pluck="name",
		)
		for inv_name in invoices:
			inv = frappe.get_doc("ePurchase Invoice", inv_name)
			updated = False
			for item in inv.items:
				if item.item_ref_raw == ref_raw and item.match_status == "matched":
					item.matched_item = None
					item.match_status = "unmatched"
					updated = True
			if updated:
				inv.save(ignore_permissions=True)
				inv.reload()
				inv._update_conversion_status()
				inv.db_set("conversion_status", inv.conversion_status)

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
	new_item.einvoice_source = name
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


@frappe.whitelist()
def convert_to_purchase_invoice(name):
	doc = frappe.get_doc("ePurchase Invoice", name)
	return doc.convert_to_purchase_invoice()


@frappe.whitelist()
def cancel_conversion(name):
	doc = frappe.get_doc("ePurchase Invoice", name)
	if not doc.purchase_invoice:
		return {"status": "error", "error": frappe._("No Purchase Invoice linked.")}

	pi = frappe.get_doc("Purchase Invoice", doc.purchase_invoice)
	if pi.docstatus != 0:
		return {
			"status": "error",
			"error": frappe._("Purchase Invoice is already submitted. Cancel it manually first."),
		}

	pi_name = doc.purchase_invoice

	# Délier d'abord l'ePurchase Invoice
	frappe.db.set_value(
		"ePurchase Invoice",
		name,
		{
			"purchase_invoice": None,
			"conversion_status": "ready",
		},
	)
	frappe.db.set_value("Purchase Invoice", pi_name, "einvoice_source", None)
	frappe.db.commit()

	frappe.delete_doc("Purchase Invoice", pi_name, ignore_permissions=True)
	frappe.db.commit()

	return {"status": "ok"}


@frappe.whitelist()
def get_refusal_reasons():
	return frappe.get_all(
		"eInvoicing Refusal Reason",
		fields=["reason_code", "reason_label"],
		order_by="reason_code asc",
	)


@frappe.whitelist()
def refuse_invoice(name, reason_code, reason_comment=None):
	doc = frappe.get_doc("ePurchase Invoice", name)
	if doc.conversion_status in ("converted", "refused"):
		frappe.throw(frappe._("Cannot refuse this invoice."))

	refusal_reasons = [{"MDT-113": reason_code}]
	if reason_comment:
		refusal_reasons[0]["MDT-126"] = reason_comment

	try:
		_get_provider().send_lifecycle("210", doc, refusal_reasons)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"eInvoicing lifecycle 210 — {name}")
		frappe.throw(frappe._("Failed to send refusal to platform."))

	frappe.db.set_value("ePurchase Invoice", name, "conversion_status", "refused")
	frappe.db.commit()
	return {"status": "ok"}


### Scheduled task


def sync_incoming_flows():
	"""Called by scheduler every 30 min (see hooks.py)."""
	try:
		result = _get_provider().sync_flows("Purchase Invoice")
		if result.get("status") == "error":
			frappe.log_error(result.get("message"), "eInvoicing scheduled sync error")
	except Exception:
		frappe.log_error(frappe.get_traceback(), "eInvoicing scheduled sync exception")


def poll_lifecycle_acknowledgements():
	"""Called by scheduler"""
	try:
		provider = _get_provider()
		pending_logs = frappe.get_all(
			"eInvoicing Lifecycle Log",
			filters={"ack_status": "pending"},
			fields=["name", "cdar_flow_id", "parent"],
		)
		for log in pending_logs:
			_poll_one_lifecycle_log(provider, log)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "eInvoicing lifecycle poll exception")


def _poll_one_lifecycle_log(provider, log):
	try:
		result = provider.call_api(
			f"flows/{log.cdar_flow_id}",
			"GET",
			params={"docType": "Metadata"},
			extra_headers={"Accept": "application/octet-stream"},
		)
		if result["status_code"] not in (200, 202):
			frappe.db.set_value(
				"eInvoicing Lifecycle Log",
				log.name,
				{
					"ack_status": "error",
					"error_type": "platform",
					"ack_message": frappe._("HTTP {0}").format(result["status_code"]),
				},
			)
			frappe.db.commit()
			return

		ack = result["response"].get("acknowledgement", {})
		ack_status = ack.get("status", "")

		if ack_status == "Ok":
			frappe.db.set_value(
				"eInvoicing Lifecycle Log",
				log.name,
				{"ack_status": "ok", "error_type": None, "ack_message": None},
			)
		elif ack_status == "Error":
			details = ack.get("details", [])
			msg = details[0].get("reasonMessage", "") if details else ""
			frappe.db.set_value(
				"eInvoicing Lifecycle Log",
				log.name,
				{"ack_status": "error", "error_type": "data", "ack_message": msg},
			)
		frappe.db.commit()
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"eInvoicing lifecycle poll — {log.name}")


@frappe.whitelist()
def poll_single_lifecycle_log(log_name):
	provider = _get_provider()
	log = frappe.get_all(
		"eInvoicing Lifecycle Log",
		filters={"name": log_name},
		fields=["name", "cdar_flow_id", "parent"],
		limit=1,
	)
	if not log:
		return {"status": "error"}
	_poll_one_lifecycle_log(provider, log[0])
	return {"status": "ok"}


@frappe.whitelist()
def send_lifecycle_status(name, status_code, refusal_reasons=None):
	if isinstance(refusal_reasons, str):
		import json as _json

		refusal_reasons = _json.loads(refusal_reasons) if refusal_reasons else None
	doc = frappe.get_doc("ePurchase Invoice", name)
	return _get_provider().send_lifecycle(status_code, doc, refusal_reasons)
