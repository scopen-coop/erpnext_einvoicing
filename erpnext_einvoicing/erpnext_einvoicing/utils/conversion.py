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
