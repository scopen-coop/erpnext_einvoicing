# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe


def build_purchase_invoice(epurchase_invoice):
	"""
	Builds a Purchase Invoice draft from a matched ePurchase Invoice.
	Called by ePurchaseInvoice.convert_to_purchase_invoice().
	"""
	pi = frappe.new_doc("Purchase Invoice")
	pi.einvoice_source = epurchase_invoice.name
	pi.bill_no = epurchase_invoice.invoice_number
	pi.bill_date = epurchase_invoice.invoice_date
	pi.due_date = epurchase_invoice.due_date
	pi.currency = epurchase_invoice.currency or "EUR"
	pi.buying_price_list = (
		frappe.db.get_single_value("Buying Settings", "buying_price_list") or "Standard Buying"
	)

	### Supplier resolution
	if epurchase_invoice.matched_supplier:
		pi.supplier = epurchase_invoice.matched_supplier
	elif epurchase_invoice.ethirdparty:
		pi.supplier = _create_supplier_from_ethirdparty(epurchase_invoice.ethirdparty)
	else:
		frappe.throw(
			frappe._("No supplier or eThirdParty linked to this ePurchase Invoice."),
			title=frappe._("Missing Supplier"),
		)

	if epurchase_invoice.purchase_order:
		pi.purchase_order = epurchase_invoice.purchase_order

	if epurchase_invoice.purchase_receipt:
		pi.purchase_receipt = epurchase_invoice.purchase_receipt

	for item in epurchase_invoice.items:
		pi.append(
			"items",
			{
				"item_code": item.matched_item,
				"item_name": item.item_description_raw,
				"qty": item.qty,
				"uom": _resolve_uom(item.uom),
				"rate": item.unit_price,
				"amount": item.amount,
			},
		)

	tax_rates = [item.tax_rate for item in epurchase_invoice.items]
	taxes_template = _resolve_taxes(tax_rates)
	if taxes_template:
		pi.taxes_and_charges = taxes_template

	pi.insert(ignore_permissions=True)
	epurchase_invoice.db_set("purchase_invoice", pi.name)
	frappe.db.commit()

	return pi


### Helpers


def _resolve_uom(uom_code):
	"""Resolve a UN/CEFACT UOM code to an ERPNext UOM via eInvoicing UOM Mapping."""
	if not uom_code:
		return frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"

	mapped = frappe.db.get_value("eInvoicing UOM Mapping", uom_code, "erpnext_uom")
	if mapped and frappe.db.exists("UOM", mapped):
		return mapped

	fallback = frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"
	return fallback


def _resolve_taxes(tax_rates):
	"""Resolve unique tax rates from items to a Purchase Taxes Template."""
	if not tax_rates:
		return None
	# Use the most common non-zero rate
	rates = [r for r in tax_rates if r and float(r) > 0]
	if not rates:
		return None
	key = f"{max(set(rates), key=rates.count):.1f}"
	return frappe.db.get_value("eInvoicing Tax Mapping", key, "purchase_taxes_template")


def _create_supplier_from_ethirdparty(ethirdparty_name):
	"""Creates a Supplier from an eThirdParty and returns the supplier name."""
	ethirdparty = frappe.get_doc("eThirdParty", ethirdparty_name)

	supplier = frappe.new_doc("Supplier")
	supplier.supplier_name = ethirdparty.party_name
	supplier.supplier_group = frappe.db.get_single_value(
		"Buying Settings", "supplier_group"
	) or frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	supplier.tax_id = ethirdparty.siret
	supplier.categorie_comptable_tiers = ethirdparty.categorie_comptable_tiers or "France"

	if ethirdparty.zip:
		supplier.zip = ethirdparty.zip
	if ethirdparty.city:
		supplier.city = ethirdparty.city

	existing = frappe.db.get_value("Supplier", {"tax_id": ethirdparty.siret}, "name") or frappe.db.get_value(
		"Supplier", {"supplier_name": ethirdparty.party_name}, "name"
	)
	if existing:
		ethirdparty.db_set("matched_party_type", "Supplier")
		ethirdparty.db_set("matched_party", existing)
		ethirdparty.db_set("status", "converted")
		return existing

	supplier.insert(ignore_permissions=True)
	frappe.db.commit()

	ethirdparty.db_set("matched_party_type", "Supplier")
	ethirdparty.db_set("matched_party", supplier.name)
	ethirdparty.db_set("status", "converted")

	return supplier.name
