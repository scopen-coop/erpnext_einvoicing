# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document


class ApprovedPlatforms(Document):
	def validate(self):
		self._validate_auth_payload_map()
		self._validate_urls()

	### Private

	def _validate_auth_payload_map(self):
		if not self.auth_payload_map:
			return
		try:
			json.loads(self.auth_payload_map)
		except json.JSONDecodeError:
			frappe.throw(
				frappe._("Auth Payload Map must be valid JSON."),
				title=frappe._("Invalid Configuration"),
			)

	def _validate_urls(self):
		if self.is_enabled and not self.prod_api_url and not self.test_api_url:
			frappe.throw(
				frappe._("At least one API URL (production or test) must be configured."),
				title=frappe._("Missing Configuration"),
			)
