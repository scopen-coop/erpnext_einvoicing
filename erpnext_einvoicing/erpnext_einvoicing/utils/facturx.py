# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import json
from datetime import datetime
from typing import Literal

import frappe
from lxml import etree

### Constants

_CII_NAMESPACE = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"

_UBL_NAMESPACES = {
	"urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
	"urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2",
	"urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2",
}

_CII_NS = {
	"rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
	"ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
	"udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}

XmlFormat = Literal["facturx", "ubl"]


### Public entry point


def create_e_purchase_invoice(pdf_content: bytes, flow_data: dict):
	"""
	Main entry point called by EsalinkProvider._process_flow.
	Extracts XML from PDF, parses it, creates and returns an ePurchase Invoice.
	"""
	xml_bytes = _extract_xml_from_pdf(pdf_content)
	xml_format = _detect_xml_format(xml_bytes)

	if xml_format == "ubl":
		frappe.throw(
			frappe._("UBL format is not yet supported for incoming invoices."),
			title=frappe._("Unsupported Format"),
		)

	data = _parse_cii(xml_bytes)
	return _create_doc(data, xml_bytes, flow_data)


### XML extraction


def _extract_xml_from_pdf(pdf_content: bytes):
	from facturx import get_xml_from_pdf

	try:
		_filename, xml_bytes = get_xml_from_pdf(pdf_content, check_xsd=False)
	except Exception as e:
		frappe.throw(
			frappe._("Failed to extract XML from PDF: {0}").format(str(e)),
			title=frappe._("Extraction Error"),
		)
	if not xml_bytes:
		frappe.throw(
			frappe._("No XML data found in PDF."),
			title=frappe._("Extraction Error"),
		)
	return xml_bytes


### Format detection


def _detect_xml_format(xml_bytes: bytes):
	try:
		root = etree.fromstring(xml_bytes)
	except etree.XMLSyntaxError as e:
		frappe.throw(
			frappe._("Invalid XML data: {0}").format(str(e)),
			title=frappe._("Invalid XML"),
		)
	ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
	if ns == _CII_NAMESPACE or root.tag.endswith("}CrossIndustryInvoice"):
		return "facturx"
	if ns in _UBL_NAMESPACES:
		return "ubl"
	frappe.throw(
		frappe._("Unsupported XML format. Only Factur-X/CII and UBL 2.x are accepted."),
		title=frappe._("Unsupported Format"),
	)


### CII Parser


def _parse_cii(xml_bytes: bytes):
	root = etree.fromstring(xml_bytes)
	ns = _CII_NS

	def get(xpath, default=""):
		result = root.xpath(xpath, namespaces=ns)
		if not result:
			return default
		val = result[0]
		return (
			val.text.strip()
			if hasattr(val, "text") and val.text
			else (val.strip() if isinstance(val, str) else default)
		)

	def get_all(xpath):
		return root.xpath(xpath, namespaces=ns)

	### Header
	invoice_number = get("//rsm:ExchangedDocument/ram:ID/text()")
	invoice_date = _parse_cii_date(get("//rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString/text()"))

	### Seller
	seller_base = "//rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty"
	supplier_name = get(f"{seller_base}/ram:Name/text()")
	supplier_siret = get(f"{seller_base}/ram:SpecifiedLegalOrganization/ram:ID/text()") or get(
		f"{seller_base}/ram:SpecifiedTaxRegistration[ram:ID/@schemeID='0002']/ram:ID/text()"
	)
	supplier_vat = get(f"{seller_base}/ram:SpecifiedTaxRegistration[ram:ID/@schemeID='VA']/ram:ID/text()")

	address_parts = [
		get(f"{seller_base}/ram:PostalTradeAddress/ram:LineOne/text()"),
		get(f"{seller_base}/ram:PostalTradeAddress/ram:PostcodeCode/text()"),
		get(f"{seller_base}/ram:PostalTradeAddress/ram:CityName/text()"),
		get(f"{seller_base}/ram:PostalTradeAddress/ram:CountryID/text()"),
	]
	supplier_address = "\n".join(p for p in address_parts if p)

	### Buyer
	buyer_base = "//rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:BuyerTradeParty"
	buyer_siret = get(f"{buyer_base}/ram:SpecifiedLegalOrganization/ram:ID/text()") or get(
		f"{buyer_base}/ram:SpecifiedTaxRegistration[ram:ID/@schemeID='0002']/ram:ID/text()"
	)

	### Settlement
	settlement_base = "//rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement"
	currency = get(f"{settlement_base}/ram:InvoiceCurrencyCode/text()") or "EUR"

	summary_base = f"{settlement_base}/ram:SpecifiedTradeSettlementHeaderMonetarySummation"
	total_ht = _to_float(get(f"{summary_base}/ram:TaxBasisTotalAmount/text()"))
	total_vat = _to_float(get(f"{summary_base}/ram:TaxTotalAmount/text()"))
	total_ttc = _to_float(get(f"{summary_base}/ram:GrandTotalAmount/text()"))

	### Due date
	due_date = _parse_cii_date(
		get(f"{settlement_base}/ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime/udt:DateTimeString/text()")
	)

	### Items
	items = []
	line_base = "//rsm:SupplyChainTradeTransaction/ram:IncludedSupplyChainTradeLineItem"
	for line in get_all(line_base):

		def line_get(xpath):
			result = line.xpath(xpath, namespaces=ns)
			if not result:
				return ""
			val = result[0]
			return (
				val.text.strip()
				if hasattr(val, "text") and val.text
				else (val.strip() if isinstance(val, str) else "")
			)

		description = line_get("ram:SpecifiedTradeProduct/ram:Name/text()")
		ref = line_get("ram:SpecifiedTradeProduct/ram:SellerAssignedID/text()")
		qty = _to_float(line_get("ram:SpecifiedLineTradeDelivery/ram:BilledQuantity/text()"))
		uom = line_get("ram:SpecifiedLineTradeDelivery/ram:BilledQuantity/@unitCode")
		unit_price = _to_float(
			line_get("ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount/text()")
		)
		amount = _to_float(
			line_get(
				"ram:SpecifiedLineTradeSettlement/ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount/text()"
			)
		)
		tax_rate = _to_float(
			line_get(
				"ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax/ram:RateApplicablePercent/text()"
			)
		)

		items.append(
			{
				"item_description_raw": description,
				"item_ref_raw": ref,
				"qty": qty or 1,
				"uom": uom,
				"unit_price": unit_price,
				"amount": amount,
				"tax_rate": tax_rate,
				"match_status": "unmatched",
			}
		)

	return {
		"invoice_number": invoice_number,
		"invoice_date": invoice_date,
		"due_date": due_date,
		"currency": currency,
		"supplier_name_raw": supplier_name,
		"supplier_siret": supplier_siret,
		"supplier_vat": supplier_vat,
		"supplier_address_raw": supplier_address,
		"buyer_siret": buyer_siret,
		"total_ht": total_ht,
		"total_vat": total_vat,
		"total_ttc": total_ttc,
		"items": items,
	}


### Document creation


def _create_doc(data: dict, xml_bytes: bytes, flow_data: dict):
	settings = frappe.get_single("eInvoicing Settings")

	doc = frappe.new_doc("ePurchase Invoice")
	doc.approved_platform = settings.approved_platform
	doc.invoice_profile = settings.invoice_profile or "EN16931"
	doc.conversion_status = "pending"
	doc.supplier_match_status = "unmatched"
	doc.flow_id = flow_data.get("flowId", "")

	doc.invoice_number = data.get("invoice_number")
	doc.invoice_date = data.get("invoice_date")
	doc.due_date = data.get("due_date")
	doc.currency = data.get("currency") or "EUR"
	doc.supplier_name_raw = data.get("supplier_name_raw")
	doc.supplier_siret = data.get("supplier_siret")
	doc.supplier_vat = data.get("supplier_vat")
	doc.supplier_address_raw = data.get("supplier_address_raw")
	doc.total_ht = data.get("total_ht", 0)
	doc.total_vat = data.get("total_vat", 0)
	doc.total_ttc = data.get("total_ttc", 0)

	buyer_siret = data.get("buyer_siret", "")
	doc.buyer_siret = buyer_siret
	if buyer_siret:
		company = frappe.db.get_value("Company", {"tax_id": buyer_siret}, "name")
		if company:
			doc.company = company

	for item in data.get("items", []):
		doc.append("items", item)

	doc.xml_content = xml_bytes.decode("utf-8", errors="replace")
	doc.raw_flow_data = json.dumps(flow_data, ensure_ascii=False, indent=2)

	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	_auto_match_supplier(doc, data)
	_auto_match_items(doc)

	return doc


### Supplier auto-matching


def _auto_match_supplier(doc, data: dict):
	"""
	Priority:
	1. Existing Supplier by SIRET (tax_id)
	2. Existing Supplier by name
	3. Existing eThirdParty by SIRET
	4. Create eThirdParty in pending
	"""
	siret = data.get("supplier_siret", "").replace(" ", "")
	name_raw = data.get("supplier_name_raw", "")

	### 1. Existing Supplier by SIRET
	if siret:
		supplier = frappe.db.get_value("Supplier", {"tax_id": siret}, "name")
		if supplier:
			doc.db_set("matched_supplier", supplier)
			doc.db_set("supplier_match_status", "matched")
			return

	### 2. Existing Supplier by name
	if name_raw:
		supplier = frappe.db.get_value(
			"Supplier",
			{"supplier_name": ["like", f"%{name_raw}%"]},
			"name",
		)
		if supplier:
			doc.db_set("matched_supplier", supplier)
			doc.db_set("supplier_match_status", "matched")


### Items auto-matching


def _auto_match_items(doc):
	"""
	Priority:
	1. Item Supplier.supplier_part_no (with matched supplier)
	2. Item.item_code exact match on item_ref_raw
	3. Item.item_name match on item_description_raw
	"""
	matched_supplier = doc.matched_supplier
	updated = False

	for item in doc.items:
		if item.match_status != "unmatched":
			continue

		### 1. supplier_part_no
		if item.item_ref_raw and matched_supplier:
			matched = frappe.db.get_value(
				"Item Supplier",
				{"supplier": matched_supplier, "supplier_part_no": item.item_ref_raw},
				"parent",
			)
			if matched:
				item.matched_item = matched
				item.match_status = "matched"
				updated = True
				continue

		### 2. item_code exact
		if item.item_ref_raw and frappe.db.exists("Item", item.item_ref_raw):
			item.matched_item = item.item_ref_raw
			item.match_status = "matched"
			updated = True
			continue

		### 3. item_name
		if item.item_description_raw:
			matched = frappe.db.get_value(
				"Item",
				{"item_name": item.item_description_raw, "is_purchase_item": 1},
				"name",
			)
			if matched:
				item.matched_item = matched
				item.match_status = "matched"
				updated = True

	if updated:
		doc.save(ignore_permissions=True)
		frappe.db.commit()


### Helpers


def _parse_cii_date(date_str: str):
	if not date_str:
		return None
	try:
		return datetime.strptime(date_str.strip(), "%Y%m%d").date()
	except ValueError:
		return None


def _to_float(value):
	try:
		return float(value)
	except (ValueError, TypeError):
		return 0.0
