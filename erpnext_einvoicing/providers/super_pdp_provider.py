# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe
import requests

from erpnext_einvoicing.providers.base_provider import BaseProvider


class SuperPdpProvider(BaseProvider):
	"""SUPER PDP implementation of BaseProvider."""

	### Authentication

	def get_access_token(self):
		token_url = (
			self.platform.prod_token_url
			if self.company_doc.einvoicing_live_mode
			else self.platform.test_token_url
		)
		if not token_url:
			frappe.throw(
				frappe._("Token URL not configured on platform '{0}'.").format(self.platform.name),
				title=frappe._("Missing Configuration"),
			)

		client_id = self.company_doc.einvoicing_client_id or ""
		client_secret = self.company_doc.get_password("einvoicing_client_secret") or ""

		headers = {"Content-Type": "application/x-www-form-urlencoded"}
		data = {
			"grant_type": "client_credentials",
			"client_id": client_id,
			"client_secret": client_secret,
		}
		try:
			response = requests.post(token_url, data=data, headers=headers, timeout=30)
			response.raise_for_status()
		except requests.exceptions.ConnectionError:
			frappe.throw(
				frappe._("Cannot reach '{0}'. Check the URL and network connectivity.").format(token_url),
				title=frappe._("Connection Error"),
			)
		except requests.exceptions.Timeout:
			frappe.throw(
				frappe._("Connection to '{0}' timed out.").format(token_url),
				title=frappe._("Timeout"),
			)
		except requests.exceptions.HTTPError as e:
			frappe.throw(
				frappe._("Authentication failed on '{0}': HTTP {1}.").format(
					token_url, e.response.status_code
				),
				title=frappe._("Authentication Error"),
			)

		token_data = response.json()
		token = token_data.get("access_token")
		if not token:
			frappe.throw(
				frappe._("No access_token in response from '{0}'.").format(self.platform.name),
				title=frappe._("Authentication Error"),
			)

		self.save_token(token, expires_in=token_data.get("expires_in"))
		return token

	def refresh_token(self):
		return self.get_access_token()

	def delete_access_token(self):
		token = (
			self.company_doc.get_password("einvoicing_access_token")
			if self.company_doc.einvoicing_access_token
			else None
		)
		if token:
			token_url = (
				self.platform.prod_token_url
				if self.company_doc.einvoicing_live_mode
				else self.platform.test_token_url
			) or ""
			revoke_url = token_url.rsplit("/token", 1)[0] + "/revoke" if token_url else ""
			if revoke_url:
				try:
					requests.post(revoke_url, data={"token": token}, timeout=10)
				except Exception:
					pass
		self.company_doc.db_set("einvoicing_access_token", None)
		self.company_doc.db_set("einvoicing_token_expires_at", None)
		self.company_doc.einvoicing_access_token = None
		return True

	### Health

	def check_health(self):
		try:
			result = self.call_api("healthcheck", "GET")
		except frappe.ValidationError as e:
			return {"status": "error", "message": str(e)}

		if result["status_code"] == 200:
			return {
				"status": "ok",
				"message": frappe._("Platform '{0}' is reachable.").format(self.platform.name),
			}
		return {
			"status": "error",
			"message": frappe._("Platform '{0}' returned HTTP {1}.").format(
				self.platform.name, result["status_code"]
			),
		}

	### Process Flow

	def _process_flow(self, flow_id, flow_data, sync_type):
		result = self.call_api(
			f"flows/{flow_id}",
			"GET",
			params={"docType": "Converted"},
			extra_headers={"Accept": "application/octet-stream"},
		)
		if result["status_code"] not in (200, 202):
			frappe.throw(
				frappe._("Failed to download flow {0} (HTTP {1}).").format(flow_id, result["status_code"])
			)
		xml_content = result["response"]
		if not xml_content:
			frappe.throw(frappe._("Empty response for flow {0}.").format(flow_id))

		from erpnext_einvoicing.erpnext_einvoicing.utils.facturx import create_e_purchase_invoice_from_xml

		einvoice = create_e_purchase_invoice_from_xml(xml_content, flow_data)
		self._save_flow_doc(flow_id, flow_data, sync_type, "ePurchase Invoice", einvoice.name)

	### Extra headers

	def _get_extra_headers(self):
		return {}
