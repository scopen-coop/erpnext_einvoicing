frappe.ui.form.on("Company", {
	refresh(frm) {
		if (!frm.doc.__islocal && frm.doc.einvoicing_approved_platform) {
			frm.fields_dict.einvoicing_healthcheck.$input.html(
				'<i class="fa fa-heartbeat"></i> ' + __("Healthcheck")
			);
			frm.fields_dict.einvoicing_recreate_token.$input.html(
				'<i class="fa fa-key"></i> ' + __("Recreate Access Token")
			);
			frm.fields_dict.einvoicing_delete_token.$input.html(
				'<i class="fa fa-trash"></i> ' + __("Delete Access Token")
			);
			frm.fields_dict.einvoicing_rebuild_lifecycle_logs.$input.html(
				'<i class="fa fa-refresh"></i> ' + __("Rebuild Lifecycle Logs")
			);
		}
	},

	einvoicing_healthcheck(frm) {
		frappe.call({
			method: "erpnext_einvoicing.providers.sync.healthcheck",
			args: { company: frm.doc.name },
			callback(r) {
				const msg = r.message || {};
				frappe.show_alert(
					{
						message: msg.message,
						indicator: msg.status === "ok" ? "green" : "red",
					},
					5
				);
			},
		});
	},

	einvoicing_recreate_token(frm) {
		frappe.call({
			method: "erpnext_einvoicing.providers.sync.recreate_access_token",
			args: { company: frm.doc.name },
			callback(r) {
				const msg = r.message || {};
				frappe.show_alert(
					{
						message: msg.message,
						indicator: msg.status === "ok" ? "green" : "red",
					},
					5
				);
				frm.reload_doc();
			},
		});
	},

	einvoicing_delete_token(frm) {
		frappe.call({
			method: "erpnext_einvoicing.providers.sync.delete_access_token",
			args: { company: frm.doc.name },
			callback(r) {
				frappe.show_alert({ message: __("Token deleted"), indicator: "green" }, 3);
				frm.reload_doc();
			},
		});
	},
	einvoicing_rebuild_lifecycle_logs(frm) {
		frappe.call({
			method: "erpnext_einvoicing.providers.sync.rebuild_lifecycle_logs",
			args: { company: frm.doc.name },
			freeze: true,
			freeze_message: __("Rebuilding lifecycle logs..."),
			callback(r) {
				if (r.message) {
					frappe.show_alert(
						{
							message: r.message.message,
							indicator: r.message.status === "ok" ? "green" : "red",
						},
						10
					);
				}
			},
		});
	},
});
