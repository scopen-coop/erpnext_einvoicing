// Copyright (c) 2026, Scopen and contributors
// For license information, please see license.txt

frappe.pages["einvoicing-inbox"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("eInvoicing Inbox"),
		single_column: true,
	});

	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update ?? [];
		frappe.hot_update.push(() => _load_vue(wrapper));
	}
};

frappe.pages["einvoicing-inbox"].on_page_show = (wrapper) => _load_vue(wrapper);

async function _load_vue(wrapper) {
	const $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();
	await frappe.require("einvoicing_inbox.bundle.js");
	frappe.einvoicing_inbox_app = frappe.ui.setup_einvoicing_inbox($parent);
}
