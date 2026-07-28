# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

import json

import frappe


def after_install():
	_create_esalink_platform()


### Private


def _create_esalink_platform():
	if frappe.db.exists("Approved Platforms", "Esalink"):
		return

	doc = frappe.new_doc("Approved Platforms")
	doc.provider_name = "Esalink"
	doc.provider_type = "Esalink"
	doc.is_enabled = 1
	doc.is_standard = 1
	doc.prod_api_url = "https://hubtimize.fr/api/orchestrator/"
	doc.test_api_url = "https://ppd.hubtimize.fr/api/orchestrator/"
	doc.prod_token_url = "https://hubtimize.fr/api/orchestrator/v1/oauth2/token"
	doc.test_token_url = "https://ppd.hubtimize.fr/api/orchestrator/v1/oauth2/token"
	doc.auth_type = "OAuth2"
	doc.api_key_header = "hubtimize-api-key"
	doc.auth_payload_map = json.dumps(
		{
			"grant_type": "client_credentials",
			"client_id": "client_id",
			"client_secret": "client_secret",
		},
		indent=2,
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
