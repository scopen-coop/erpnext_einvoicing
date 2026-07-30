# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class eThirdParty(Document):
	def before_save(self):
		self._set_categorie_comptable()

	### Private

	def _set_categorie_comptable(self):
		"""Détermine la catégorie comptable tiers depuis le code pays si non renseignée."""
		if self.categorie_comptable_tiers:
			return
		if not self.country_code:
			return

		code = self.country_code.upper()

		EU_COUNTRIES = {
			"AT",
			"BE",
			"BG",
			"CY",
			"CZ",
			"DE",
			"DK",
			"EE",
			"ES",
			"FI",
			"GR",
			"HR",
			"HU",
			"IE",
			"IT",
			"LT",
			"LU",
			"LV",
			"MT",
			"NL",
			"PL",
			"PT",
			"RO",
			"SE",
			"SI",
			"SK",
		}

		if code == "FR":
			self.categorie_comptable_tiers = "France"
		elif code in EU_COUNTRIES:
			self.categorie_comptable_tiers = "UE"
		else:
			self.categorie_comptable_tiers = "Export"
