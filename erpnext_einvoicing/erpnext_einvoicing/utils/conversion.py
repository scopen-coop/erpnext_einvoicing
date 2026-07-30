# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe


def build_purchase_invoice(epurchase_invoice):
	"""
	Builds a Purchase Invoice draft from a matched ePurchase Invoice.
	Called by ePurchaseInvoice.convert_to_purchase_invoice().
	"""
	pi = frappe.new_doc("Purchase Invoice")
	pi.supplier = epurchase_invoice.matched_supplier
	pi.bill_no = epurchase_invoice.invoice_number
	pi.bill_date = epurchase_invoice.invoice_date
	pi.due_date = epurchase_invoice.due_date
	pi.currency = epurchase_invoice.currency or "EUR"
	pi.buying_price_list = "Standard Buying"
	pi.einvoice_source = epurchase_invoice.name

	### Résolution du supplier
	if not epurchase_invoice.matched_supplier and epurchase_invoice.ethirdparty:
		ethirdparty = frappe.get_doc("eThirdParty", epurchase_invoice.ethirdparty)
		settings = frappe.get_single("eInvoicing Settings")

		supplier = frappe.new_doc("Supplier")
		supplier.supplier_name = ethirdparty.party_name
		supplier.supplier_group = (
			settings.default_supplier_group
			or frappe.db.get_single_value("Buying Settings", "supplier_group")
			or frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
		)
		supplier.tax_id = ethirdparty.siret
		supplier.categorie_comptable_tiers = ethirdparty.categorie_comptable_tiers or "France"
		if ethirdparty.zip:
			supplier.zip = ethirdparty.zip
		if ethirdparty.city:
			supplier.city = ethirdparty.city
		supplier.insert(ignore_permissions=True)
		frappe.db.commit()

		ethirdparty.db_set("matched_party_type", "Supplier")
		ethirdparty.db_set("matched_party", supplier.name)
		ethirdparty.db_set("status", "converted")

		pi.supplier = supplier.name
	else:
		pi.supplier = epurchase_invoice.matched_supplier

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
				"uom": item.uom or "Nos",
				"rate": item.unit_price,
				"amount": item.amount,
			},
		)

	pi.insert(ignore_permissions=True)
	frappe.db.commit()

	return pi
