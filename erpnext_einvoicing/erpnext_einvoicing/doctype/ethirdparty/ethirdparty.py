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
		cct_doctype = (
			"Categorie Comptable Tiers"
			if frappe.db.table_exists("tabCategorie Comptable Tiers")
			else "Categorie comptable Tiers"
		)
		if self.categorie_comptable_tiers:
			if frappe.db.exists(cct_doctype, self.categorie_comptable_tiers):
				return
			self.categorie_comptable_tiers = ""
		if not self.country_code:
			return
		if not frappe.db.table_exists(f"tab{cct_doctype}"):
			return
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
		code = self.country_code.upper()
		if code == "FR":
			cat = "France"
		elif code in EU_COUNTRIES:
			cat = "UE"
		else:
			cat = "Export"
		if frappe.db.exists(cct_doctype, cat):
			self.categorie_comptable_tiers = cat
