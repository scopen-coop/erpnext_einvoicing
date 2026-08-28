// Copyright (c) 2026, Scopen and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		if (!frm.doc.einvoice_source) return;
		_load_einvoicing_buttons(frm);
	},
});

/*** Lifecycle buttons ***/

function _load_einvoicing_buttons(frm) {
	frappe.call({
		method: "erpnext_einvoicing.providers.sync.get_pi_lifecycle_last_status",
		args: { pi_name: frm.doc.name },
		callback(r) {
			frm.page.$title_area.find(".einvoicing-badge").remove();
			const info = r.message || {};
			const last_status = info.status_code;
			const ack_status = info.ack_status;

			if (last_status) {
				const color =
					ack_status === "ok"
						? "#c8ebd0"
						: ack_status === "error"
						? "#f5d0d0"
						: "#faeac8";
				const textColor =
					ack_status === "ok"
						? "#2d6a36"
						: ack_status === "error"
						? "#8b2020"
						: "#7a5000";
				const label = `[${last_status}] ${info.status_label || last_status}`;
				const icon =
					ack_status === "ok"
						? "fa-check"
						: ack_status === "error"
						? "fa-times"
						: "fa-hourglass-half";
				const $badge = $(`<span class="einvoicing-badge" style="
					display: inline-flex;
					align-items: center;
					gap: 6px;
					margin-left: 10px;
					padding: 2px 8px;
					border-radius: 10px;
					font-size: 11px;
					font-weight: 500;
					color: ${textColor};
					background: ${color};
					vertical-align: middle;
				"><i class="fa ${icon}"></i>${label}</span>`);
				if (ack_status === "error") {
					const $retry = $(
						`<i class="fa fa-refresh" style="cursor:pointer;margin-left:2px" title="${__(
							"Retry"
						)}"></i>`
					);
					$retry.on("click", () => _retry(frm, info));
					$badge.append($retry);
				}
				if (ack_status === "pending") {
					const $poll = $(
						`<i class="fa fa-refresh" style="cursor:pointer;margin-left:4px;opacity:0.7" title="${__(
							"Check status"
						)}"></i>`
					);
					$poll.on("click", () => {
						frappe.call({
							method: "erpnext_einvoicing.providers.sync.poll_single_lifecycle_log",
							args: { log_name: info.log_name },
							callback() {
								frm.refresh();
							},
						});
					});
					$badge.append($poll);
				}
				const $indicator = frm.page.$title_area.find(".indicator-pill").first();
				if ($indicator.length) {
					$indicator.after($badge);
				} else {
					frm.page.$title_area.find("h3, .title-text").first().after($badge);
				}
			}

			const effective = info.effective_status;
			if (["204", "205", "206"].includes(effective)) {
				frm.add_custom_button(__("Dispute"), () => _prompt_dispute(frm), __("eInvoicing"));
			}
			if (effective === "207") {
				frm.add_custom_button(
					__("Resolve Dispute"),
					() => _confirm_resolve(frm),
					__("eInvoicing")
				);
			}
			if (effective !== "208") {
				frm.add_custom_button(__("Suspend"), () => _prompt_suspend(frm), __("eInvoicing"));
			}
			if (ack_status === "pending") {
				const $group = frm.page.inner_toolbar.find(
					`.inner-group-button[data-label="${__("eInvoicing")}"] > button`
				);
				$group
					.prop("disabled", true)
					.attr("title", __("Waiting for platform acknowledgement..."));
			}
		},
	});
}

function _retry(frm, info) {
	if (info.status_code === "207") {
		_prompt_dispute(frm);
		return;
	}
	if (info.status_code === "208") {
		_prompt_suspend(frm);
		return;
	}
	frappe.call({
		method: "erpnext_einvoicing.providers.sync.retry_lifecycle",
		args: { pi_name: frm.doc.name },
		freeze: true,
		freeze_message: __("Retrying..."),
		callback(r) {
			if ((r.message || {}).status === "ok") {
				frappe.show_alert(
					{ message: __("Lifecycle status resent"), indicator: "green" },
					5
				);
				frm.refresh();
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

function _prompt_suspend(frm) {
	frappe.prompt(
		[
			{
				fieldname: "reason_code",
				fieldtype: "Link",
				options: "eInvoicing Suspension Reason",
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
				method: "erpnext_einvoicing.providers.sync.send_invoice_suspend",
				args: {
					pi_name: frm.doc.name,
					reason_code: values.reason_code,
					reason_comment: values.reason_comment || null,
				},
				freeze: true,
				freeze_message: __("Sending suspension..."),
				callback(r) {
					if ((r.message || {}).status === "ok") {
						frappe.show_alert(
							{ message: __("Invoice suspended"), indicator: "green" },
							5
						);
						frm.refresh();
					}
				},
			});
		},
		__("Suspend Invoice"),
		__("Confirm")
	);
}
