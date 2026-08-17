// Copyright (c) 2026, Scopen and contributors
// For license information, please see license.txt

frappe.ui.form.on("eInvoicing Settings", {
	refresh(frm) {
		frm.fields_dict.healthcheck.$input.html(
			'<i class="fa fa-heartbeat"></i> ' + __("Healthcheck")
		);
		frm.fields_dict.recreate_access_token.$input.html(
			'<i class="fa fa-key"></i> ' + __("Recreate Access Token")
		);
		frm.fields_dict.delete_access_token.$input.html(
			'<i class="fa fa-trash"></i> ' + __("Delete Access Token")
		);
		frm.fields_dict.send_sample_invoice.$input.html(
			'<i class="fa fa-paper-plane"></i> ' + __("Send Sample Invoice")
		);
		frm.fields_dict.rebuild_lifecycle_logs.$input.html(
			'<i class="fa fa-refresh"></i> ' + __("Rebuild Lifecycle Logs")
		);
	},

	healthcheck(frm) {
		_run_action(frm, {
			method: "erpnext_einvoicing.providers.sync.healthcheck",
			freeze_message: __("Checking connection..."),
			title: __("Healthcheck"),
		});
	},

	recreate_access_token(frm) {
		_run_action(frm, {
			method: "erpnext_einvoicing.providers.sync.recreate_access_token",
			freeze_message: __("Generating access token..."),
			title: __("Recreate Access Token"),
			on_success: () => frm.reload_doc(),
		});
	},

	delete_access_token(frm) {
		frappe.confirm(__("Are you sure you want to delete the access token?"), () =>
			_run_action(frm, {
				method: "erpnext_einvoicing.providers.sync.delete_access_token",
				freeze_message: __("Deleting access token..."),
				title: __("Delete Access Token"),
				on_success: () => frm.reload_doc(),
			})
		);
	},

	send_sample_invoice(frm) {
		_run_action(frm, {
			method: "erpnext_einvoicing.providers.sync.send_sample_invoice",
			freeze_message: __("Sending sample invoice..."),
			title: __("Send Sample Invoice"),
		});
	},
	rebuild_lifecycle_logs(frm) {
		frappe.call({
			method: "erpnext_einvoicing.providers.sync.rebuild_lifecycle_logs",
			freeze: true,
			freeze_message: __("Rebuilding lifecycle logs..."),
			callback(r) {
				if (r.message) {
					frappe.show_alert({
						message: r.message.message,
						indicator: r.message.status === "ok" ? "green" : "red",
					}, 10);
				}
			},
		});
	},
});

/*** Helpers ***/

function _run_action(frm, {method, freeze_message, title, on_success}) {
	const run = () => {
		frappe.call({
			method: method,
			freeze: true,
			freeze_message: freeze_message,
			callback(r) {
				if (r.exc) {
					frappe.msgprint({
						title: __("Unexpected Error"),
						message: r.exc,
						indicator: "red",
					});
					return;
				}
				const {status, message} = r.message;
				const indicator =
					{ok: "green", warning: "orange", error: "red"}[status] ?? "blue";
				frappe.msgprint({title, message, indicator});
				if (status === "ok" && on_success) {
					on_success();
				}
			},
		});
	};

	if (frm.is_dirty()) {
		frappe.confirm(
			__("The form has unsaved changes. Save before continuing?"),
			() => frm.save().then(run),
			run
		);
	} else {
		run();
	}
}
