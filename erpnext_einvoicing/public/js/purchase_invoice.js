frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || !frm.doc.einvoice_source) return;
		_load_einvoicing_buttons(frm);
	},
});

/*** Lifecycle buttons ***/

function _load_einvoicing_buttons(frm) {
	frappe.call({
		method: "erpnext_einvoicing.providers.sync.get_pi_lifecycle_last_status",
		args: { pi_name: frm.doc.name },
		callback(r) {
			const last_status = (r.message || {}).status_code;
			if (["204", "205", "206"].includes(last_status)) {
				frm.add_custom_button(__("Dispute"), () => _prompt_dispute(frm), __("eInvoicing"));
			}
			if (["207", "209"].includes(last_status)) {
				frm.add_custom_button(
					__("Resolve Dispute"),
					() => _confirm_resolve(frm),
					__("eInvoicing")
				);
			}
		},
	});
}

function _prompt_dispute(frm) {
	frappe.prompt(
		[
			{
				fieldname: "reason_code",
				fieldtype: "Link",
				options: "eInvoicing Refusal Reason",
				label: __("Reason"),
				reqd: 1,
			},
			{
				fieldname: "reason_comment",
				fieldtype: "Small Text",
				label: __("Comment"),
			},
		],
		(values) => {
			frappe.call({
				method: "erpnext_einvoicing.providers.sync.send_invoice_dispute",
				args: {
					pi_name: frm.doc.name,
					reason_code: values.reason_code,
					reason_comment: values.reason_comment || null,
				},
				freeze: true,
				freeze_message: __("Sending dispute..."),
				callback(r) {
					if ((r.message || {}).status === "ok") {
						frappe.show_alert({ message: __("Dispute sent"), indicator: "green" }, 5);
						frm.refresh();
					}
				},
			});
		},
		__("Invoice Dispute"),
		__("Confirm")
	);
}

function _confirm_resolve(frm) {
	frappe.confirm(__("Confirm that the dispute has been resolved?"), () => {
		frappe.call({
			method: "erpnext_einvoicing.providers.sync.send_dispute_resolved",
			args: { pi_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Sending resolution..."),
			callback(r) {
				if ((r.message || {}).status === "ok") {
					frappe.show_alert({ message: __("Dispute resolved"), indicator: "green" }, 5);
					frm.refresh();
				}
			},
		});
	});
}
