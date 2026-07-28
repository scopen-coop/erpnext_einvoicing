# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class eInvoicingSettings(Document):
	def validate(self):
		self._warn_if_misconfigured()

	### Private

	def _warn_if_misconfigured(self):
		if not self.approved_platform:
			return

		platform = frappe.get_doc("Approved Platforms", self.approved_platform)

		if not platform.is_enabled:
			frappe.msgprint(
				frappe._("Platform '{0}' is disabled.").format(platform.name),
				indicator="orange",
				alert=True,
			)
			return

		if not self.api_key:
			frappe.msgprint(
				frappe._("API Key is not configured."),
				indicator="orange",
				alert=True,
			)

		env = "production" if self.live_mode else "test"
		url = platform.prod_api_url if self.live_mode else platform.test_api_url
		if not url:
			frappe.msgprint(
				frappe._("No {0} API URL configured on platform '{1}'.").format(env, platform.name),
				indicator="orange",
				alert=True,
			)


### Factory


def get_provider(settings, platform):
	"""Returns the correct BaseProvider instance based on platform.provider_type."""
	if platform.provider_type == "Esalink":
		from erpnext_einvoicing.providers.esalink_provider import EsalinkProvider

		return EsalinkProvider(settings, platform)

	frappe.throw(
		frappe._("Unsupported provider type: '{0}'.").format(platform.provider_type),
		title=frappe._("Configuration Error"),
	)
