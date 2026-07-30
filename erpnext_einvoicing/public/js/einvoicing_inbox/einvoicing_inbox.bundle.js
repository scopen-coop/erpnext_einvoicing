// Copyright (c) 2026, Scopen and contributors
// For license information, please see license.txt

import { createApp } from "vue";
import EInvoicingInbox from "./EInvoicingInbox.vue";

function setup_einvoicing_inbox(wrapper) {
	const app = createApp(EInvoicingInbox);
	app.mount(wrapper.get(0));
	return app;
}

frappe.ui.setup_einvoicing_inbox = setup_einvoicing_inbox;
export default setup_einvoicing_inbox;
