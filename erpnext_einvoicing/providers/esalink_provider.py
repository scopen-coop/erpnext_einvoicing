# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import json

import frappe
import requests
from frappe.utils import get_datetime, now_datetime

from erpnext_einvoicing.providers.base_provider import BaseProvider

FLOW_TYPE_MAP = {
	"Purchase Invoice": "SupplierInvoice",
	"Customer Invoice": "CustomerInvoice",
}

PASSWORD_FIELDS = ("client_secret", "api_key", "access_token")


class EsalinkProvider(BaseProvider):
	"""Esalink/Hubtimize implementation of BaseProvider."""

	### Authentication

	def get_access_token(self) -> str:
		payload = self._build_auth_payload()
		token_url = self.platform.prod_token_url if self.settings.live_mode else self.platform.test_token_url
		if not token_url:
			frappe.throw(
				frappe._("Token URL not configured on platform '{0}'.").format(self.platform.name),
				title=frappe._("Missing Configuration"),
			)
		headers = {
			"Content-Type": "application/x-www-form-urlencoded",
			**self._build_api_key_header(),
		}
		try:
			response = requests.post(token_url, data=payload, headers=headers, timeout=30)
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

	def refresh_token(self) -> str:
		return self.get_access_token()

	def delete_access_token(self) -> bool:
		self.settings.db_set("access_token", None)
		self.settings.db_set("token_expires_at", None)
		self.settings.access_token = None
		return True

	### Health

	def check_health(self) -> dict:
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

	### Sample invoice

	def send_sample_invoice(self) -> dict:
		frappe.throw(
			frappe._("send_sample_invoice is not yet implemented for platform '{0}'.").format(
				self.platform.provider_name
			),
			title=frappe._("Not Implemented"),
		)

	### Generic API call

	def call_api(
		self,
		resource: str,
		method: str,
		params: dict | None = None,
		extra_headers: dict | None = None,
	) -> dict:
		if self.is_token_expired():
			self.get_access_token()

		base_url = self.get_base_url()
		url = f"{base_url}{resource}"

		headers = {
			"Authorization": f"Bearer {self.settings.get_password('access_token')}",
			"Content-Type": "application/json",
			**self._build_api_key_header(),
		}
		if extra_headers:
			headers.update(extra_headers)

		try:
			response = requests.request(
				method=method.upper(),
				url=url,
				headers=headers,
				json=params if method.upper() in ("POST", "PUT", "PATCH") else None,
				params=params if method.upper() == "GET" else None,
				timeout=30,
			)
		except requests.exceptions.ConnectionError:
			return {"status_code": 0, "response": "Connection error"}
		except requests.exceptions.Timeout:
			return {"status_code": 0, "response": "Timeout"}

		content_type = response.headers.get("Content-Type", "")
		if "application/pdf" in content_type or "application/octet-stream" in content_type:
			return {"status_code": response.status_code, "response": response.content}

		try:
			return {"status_code": response.status_code, "response": response.json()}
		except Exception:
			return {"status_code": response.status_code, "response": response.text}

	### Flows

	def check_pending_flows(self, sync_type: str) -> dict:
		payload = self._build_search_payload(sync_type, limit=1)
		result = self.call_api("flows/search", "POST", params=payload)
		if result["status_code"] not in (200, 202):
			return {"has_pending": False, "total": 0}
		total = result["response"].get("total", 0)
		return {"has_pending": total > 0, "total": total}

	def sync_flows(self, sync_type: str) -> dict:
		payload = self._build_search_payload(sync_type, limit=1)
		result = self.call_api("flows/search", "POST", params=payload)
		if result["status_code"] not in (200, 202):
			return {
				"status": "error",
				"message": frappe._("Failed to reach platform (HTTP {0}).").format(result["status_code"]),
			}

		total = result["response"].get("total", 0)
		if total == 0:
			return {
				"status": "ok",
				"message": frappe._("No flows to synchronize."),
				"total": 0,
				"synced": 0,
				"skipped": 0,
				"errors": 0,
			}

		payload["limit"] = total
		result = self.call_api("flows/search", "POST", params=payload)
		if result["status_code"] not in (200, 202):
			return {
				"status": "error",
				"message": frappe._("Failed to retrieve flows (HTTP {0}).").format(result["status_code"]),
			}

		flows = sorted(
			result["response"].get("results", []),
			key=lambda f: f.get("updatedAt", ""),
		)

		existing_flow_ids = set(
			frappe.db.get_all(
				"eInvoicing Flow",
				filters={"approved_platform": self.platform.name},
				pluck="flow_id",
			)
		)

		synced = skipped = errors = 0
		sync_date = now_datetime()

		for flow in flows:
			flow_id = flow.get("flowId")
			if not flow_id:
				errors += 1
				continue
			if flow_id in existing_flow_ids:
				skipped += 1
				continue
			try:
				self._process_flow(flow_id, flow, sync_type)
				synced += 1
			except Exception:
				frappe.log_error(frappe.get_traceback(), f"eInvoicing sync error — flowId {flow_id}")
				errors += 1

		status = "ok" if errors == 0 else ("partial" if synced > 0 else "error")
		self._save_sync_log(sync_type, sync_date, status, total, synced, skipped, errors)

		return {
			"status": status,
			"message": frappe._("{0} synced, {1} skipped, {2} errors out of {3} flows.").format(
				synced, skipped, errors, total
			),
			"total": total,
			"synced": synced,
			"skipped": skipped,
			"errors": errors,
		}

	### Private helpers

	def _process_flow(self, flow_id: str, flow_data: dict, sync_type: str) -> None:
		result = self.call_api(f"flows/{flow_id}", "GET", params={"docType": "Original"})
		if result["status_code"] not in (200, 202):
			frappe.throw(
				frappe._("Failed to download flow {0} (HTTP {1}).").format(flow_id, result["status_code"])
			)

		pdf_content = result["response"]
		if not isinstance(pdf_content, bytes):
			frappe.throw(frappe._("Expected binary PDF content for flow {0}.").format(flow_id))

		from erpnext_einvoicing.erpnext_einvoicing.utils.facturx import create_e_purchase_invoice

		einvoice = create_e_purchase_invoice(pdf_content, flow_data)

		self._save_flow_doc(flow_id, flow_data, sync_type, "ePurchase Invoice", einvoice.name)

	def _save_flow_doc(
		self,
		flow_id: str,
		flow_data: dict,
		sync_type: str,
		document_type: str | None,
		document_name: str | None,
	) -> None:
		doc = frappe.new_doc("eInvoicing Flow")
		doc.flow_id = flow_id
		doc.approved_platform = self.platform.name
		doc.flow_type = sync_type
		doc.flow_direction = flow_data.get("flowDirection", "")
		doc.ack_status = flow_data.get("acknowledgement", {}).get("status", "")
		doc.tracking_id = flow_data.get("trackingId", "")
		doc.document_type = document_type or ""
		doc.document_name = document_name or ""

		submitted_at = flow_data.get("submittedAt")
		updated_at = flow_data.get("updatedAt")
		if submitted_at:
			doc.submitted_at = get_datetime(submitted_at).replace(tzinfo=None)
		if updated_at:
			doc.updated_at = get_datetime(updated_at).replace(tzinfo=None)

		doc.insert(ignore_permissions=True)

	def _save_sync_log(
		self,
		sync_type: str,
		sync_date,
		status: str,
		total: int,
		synced: int,
		skipped: int,
		errors: int,
	) -> None:
		doc = frappe.new_doc("eInvoicing Sync Log")
		doc.sync_type = sync_type
		doc.approved_platform = self.platform.name
		doc.last_sync_date = sync_date
		doc.last_sync_status = status
		doc.flows_total = total
		doc.flows_synced = synced
		doc.flows_skipped = skipped
		doc.flows_error = errors
		doc.insert(ignore_permissions=True)

	def _build_search_payload(self, sync_type: str, limit: int = 100) -> dict:
		last_sync_date = frappe.db.get_value(
			"eInvoicing Sync Log",
			filters={
				"sync_type": sync_type,
				"approved_platform": self.platform.name,
				"last_sync_status": "ok",
			},
			fieldname="last_sync_date",
			order_by="last_sync_date desc",
		)
		updated_after = (
			get_datetime(last_sync_date).strftime("%Y-%m-%dT%H:%M:%S.000Z")
			if last_sync_date
			else "1970-01-01T00:00:00.000Z"
		)
		return {
			"where": {
				"updatedAfter": updated_after,
				"flowType": [FLOW_TYPE_MAP.get(sync_type, "SupplierInvoice")],
				"flowDirection": ["In"],
			},
			"limit": limit,
		}

	def _build_auth_payload(self) -> dict:
		try:
			mapping = json.loads(self.platform.auth_payload_map or "{}")
		except json.JSONDecodeError as e:
			frappe.throw(
				frappe._("Invalid JSON in auth_payload_map: {0}").format(str(e)),
				title=frappe._("Configuration Error"),
			)
		payload = {}
		for api_field, settings_field in mapping.items():
			if hasattr(self.settings, settings_field):
				if settings_field in PASSWORD_FIELDS:
					payload[api_field] = self.settings.get_password(settings_field) or ""
				else:
					payload[api_field] = getattr(self.settings, settings_field) or ""
			else:
				payload[api_field] = settings_field
		return payload

	def _build_api_key_header(self) -> dict:
		if not self.platform.api_key_header:
			return {}
		api_key = self.settings.get_password("api_key") if self.settings.api_key else None
		if not api_key:
			return {}
		return {self.platform.api_key_header: api_key}
