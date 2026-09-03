# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe
import requests

from erpnext_einvoicing.providers.base_provider import BaseProvider


class EsalinkProvider(BaseProvider):
	"""Esalink/Hubtimize implementation of BaseProvider."""

	### Authentication

	def get_access_token(self):
		import base64
		from urllib.parse import quote

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
		encoded = base64.b64encode(
			f"{quote(client_id, safe='')}:{quote(client_secret, safe='')}".encode()
		).decode()

		headers = {
			"Authorization": f"Basic {encoded}",
			"Content-Type": "application/x-www-form-urlencoded",
			**self._get_extra_headers(),
		}
		try:
			response = requests.post(
				token_url,
				data="grant_type=client_credentials",
				headers=headers,
				timeout=30,
			)
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

		data = response.json()
		token = data.get("access_token")
		if not token:
			frappe.throw(
				frappe._("No access_token in response from '{0}'.").format(self.platform.name),
				title=frappe._("Authentication Error"),
			)

		self.save_token(token, expires_in=data.get("expires_in"))
		return token

	def refresh_token(self):
		return self.get_access_token()

	def delete_access_token(self):
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

	def _build_cdar_data_dict(self, status_code, doc, refusal_reasons=None):
		cdar_dict = super()._build_cdar_data_dict(status_code, doc, refusal_reasons)
		if doc.get("raw_flow_data"):
			import json

			try:
				flow_data = json.loads(doc.raw_flow_data)
				tracking_id = flow_data.get("trackingId")
				if tracking_id:
					cdar_dict["MDT-87"] = str(tracking_id)
			except Exception:
				pass
		return cdar_dict

	### Extra headers

	def _get_extra_headers(self):
		if not self.platform.api_key_header:
			return {}
		api_key = (
			self.company_doc.get_password("einvoicing_api_key")
			if self.company_doc.einvoicing_api_key
			else None
		)
		if not api_key:
			return {}
		return {self.platform.api_key_header: api_key}
