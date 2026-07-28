# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

from abc import ABC, abstractmethod
from datetime import timedelta

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime


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
