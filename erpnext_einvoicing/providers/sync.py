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


### Whitelisted methods


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


### Scheduled task


def sync_incoming_flows():
	"""Called by scheduler every 30 min (see hooks.py)."""
	try:
		result = _get_provider().sync_flows("Purchase Invoice")
		if result.get("status") == "error":
			frappe.log_error(result.get("message"), "eInvoicing scheduled sync error")
	except Exception:
		frappe.log_error(frappe.get_traceback(), "eInvoicing scheduled sync exception")
