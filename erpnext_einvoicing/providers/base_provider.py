# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import datetime
from abc import ABC, abstractmethod
from datetime import timedelta

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

LIFECYCLE_STATUS_MAP = {
	"204": "Acknowledged",
	"205": "Approved",
	"210": "Rejected",
	"211": "PaymentTransmitted",
}

LIFECYCLE_STATUS_CODE_MAP = {
	"204": "45",  # in process
	"205": "1",  # accepted
	"210": "45",  # fallback (in process)
	"211": "47",  # paid
}


class BaseProvider(ABC):
	"""
	Abstract base class for all e-invoicing platform providers.
	Credentials are stored in eTransactions Settings.
	Protocol/URL configuration is stored in Approved Platforms.
	"""

	def __init__(self, settings, platform):
		self.settings = settings
		self.platform = platform

	### Abstract methods

	@abstractmethod
	def get_access_token(self) -> str:
		"""Obtain a new access token and persist it. Returns the token string."""
		pass

	@abstractmethod
	def refresh_token(self) -> str:
		"""Refresh the current access token. Returns the new token string."""
		pass

	@abstractmethod
	def delete_access_token(self) -> bool:
		"""Delete the stored access token. Returns True on success."""
		pass

	@abstractmethod
	def check_health(self) -> dict:
		"""
		Check connectivity with the platform.
		Returns {"status": "ok"|"warning"|"error", "message": str}
		"""
		pass

	@abstractmethod
	def call_api(
		self,
		resource: str,
		method: str,
		params: dict | None = None,
		extra_headers: dict | None = None,
	) -> dict:
		"""
		Generic authenticated API call.
		Returns {"status_code": int, "response": dict | bytes}
		"""
		pass

	@abstractmethod
	def check_pending_flows(self, sync_type: str) -> dict:
		"""
		Check whether there are unprocessed incoming flows.
		Returns {"has_pending": bool, "total": int}
		"""
		pass

	@abstractmethod
	def sync_flows(self, sync_type: str) -> dict:
		"""
		Retrieve and process all pending incoming flows.
		Returns {"status": str, "message": str, "total": int, "synced": int, "skipped": int, "errors": int}
		"""
		pass

	@abstractmethod
	def _send_cdar(self, xml_bytes, filename, flow_info):
		"""Send CDAR XML to the PA. Returns the raw API result dict."""
		pass

	@abstractmethod
	def send_sample_invoice(self) -> dict:
		"""
		Send a sample invoice to validate the platform connection end-to-end.
		Returns {"status": "ok"|"error", "message": str}
		"""
		pass

	### Common methods

	def get_base_url(self) -> str:
		"""Returns the API base URL based on live_mode in eTransactions Settings."""
		url = self.platform.prod_api_url if self.settings.live_mode else self.platform.test_api_url
		if not url:
			frappe.throw(
				frappe._("API URL not configured on platform '{0}'.").format(self.platform.name),
				title=frappe._("Missing Configuration"),
			)
		return url if url.endswith("/") else url + "/"

	def is_token_expired(self) -> bool:
		"""Returns True if the stored access token is missing or within 60 s of expiry."""
		if not self.settings.access_token:
			return True
		if not self.settings.token_expires_at:
			return True
		expires_at = get_datetime(self.settings.token_expires_at)
		now = get_datetime(now_datetime())
		return now >= (expires_at - timedelta(seconds=60))

	def save_token(self, token: str, expires_in: int | None = None) -> None:
		"""Persist the access token (and optional expiry) in eTransactions Settings."""
		self.settings.db_set("access_token", token)
		if expires_in:
			expires_at = add_to_date(now_datetime(), seconds=int(expires_in))
			self.settings.db_set("token_expires_at", expires_at.strftime("%Y-%m-%d %H:%M:%S"))
		self.settings.access_token = token

	# Lifecycle (AFNOR XP Z12-013)

	def send_lifecycle(self, status_code, doc, refusal_reasons=None):
		"""Generate and send a CDAR lifecycle status. Pure AFNOR XP Z12-013."""
		from pyfrctc import generate_cdar

		if status_code not in LIFECYCLE_STATUS_MAP:
			frappe.throw(
				frappe._("Unknown lifecycle status code: {0}").format(status_code),
				title=frappe._("Lifecycle Error"),
			)

		cdar_dict = self._build_cdar_data_dict(status_code, doc, refusal_reasons)

		try:
			xml_bytes = generate_cdar(cdar_dict)
		except Exception as e:
			frappe.throw(
				frappe._("Failed to generate CDAR XML: {0}").format(str(e)),
				title=frappe._("CDAR Generation Error"),
			)

		filename = f"Lifecycle-{status_code}-{doc.invoice_number}.xml"[:255]
		flow_info = self._build_lifecycle_flow_info(filename, doc)
		return self._send_cdar(xml_bytes, filename, flow_info)

	def _build_cdar_data_dict(self, status_code, doc, refusal_reasons=None):
		"""Build the cdar_dict for pyfrctc.generate_cdar. Pure AFNOR XP Z12-013."""
		now = datetime.datetime.now()
		buyer_siret = (doc.buyer_siret or "").replace(" ", "")
		supplier_siret = (doc.supplier_siret or "").replace(" ", "")

		if not buyer_siret:
			frappe.throw(
				frappe._("Cannot send lifecycle: no buyer SIRET on {0}.").format(doc.name),
				title=frappe._("Lifecycle Error"),
			)
		if not supplier_siret:
			frappe.throw(
				frappe._("Cannot send lifecycle: no supplier SIRET on {0}.").format(doc.name),
				title=frappe._("Lifecycle Error"),
			)

		company_name = frappe.db.get_value("Company", doc.company, "company_name") or doc.company or ""
		invoice_date_for_id = str(doc.invoice_date or "")[:10]
		cdar_id = (
			f"{doc.invoice_number}_380_{invoice_date_for_id}#{status_code}_{now.strftime('%Y%m%d%H%M%S')}"
		)

		invoice_date_dt = None
		if doc.invoice_date:
			if isinstance(doc.invoice_date, datetime.datetime):
				invoice_date_dt = doc.invoice_date
			elif isinstance(doc.invoice_date, datetime.date):
				invoice_date_dt = datetime.datetime.combine(doc.invoice_date, datetime.time.min)
			else:
				try:
					invoice_date_dt = datetime.datetime.strptime(str(doc.invoice_date), "%Y-%m-%d")
				except ValueError:
					pass

		cdar_dict = {
			"MDT-2": "REGULATED",
			"MDT-3": "urn.cpro.gouv.fr:1p0:CDV:invoice",
			"MDT-4": cdar_id,
			"MDT-8": now,
			"MDT-21": "BY",
			"MDT-38": {"0002": buyer_siret},
			"MDT-39": company_name,
			"MDT-40": "BY",
			"MDT-57": {"0002": supplier_siret},
			"MDT-58": doc.supplier_name_raw or "",
			"MDT-59": "SE",
			"MDT-73": supplier_siret[:9],
			"MDT-73-1": "0225",
			"MDT-74": False,
			"MDT-77": 23,
			"MDT-78": now,
			"MDT-87": doc.invoice_number or "",
			"MDT-88": LIFECYCLE_STATUS_CODE_MAP.get(status_code, "45"),
			"MDT-91": "380",
			"MDT-100": invoice_date_dt.date() if invoice_date_dt else datetime.date.today(),
			"MDT-105": status_code,
			"MDT-106": LIFECYCLE_STATUS_MAP[status_code],
			"MDT-129": {"0002": supplier_siret},
		}

		if invoice_date_dt:
			cdar_dict["MDT-95"] = invoice_date_dt
		if refusal_reasons:
			cdar_dict["MDG-37"] = refusal_reasons

		return cdar_dict

	def _build_lifecycle_flow_info(self, filename, doc):
		"""Build flowInfo for CDAR submission. Override for PA-specific additions."""
		return {"flowSyntax": "CDAR", "name": filename}
