<script setup>
import { ref, computed, onMounted, watch, nextTick } from "vue";

// Helper pour traduction
function __(text, replace) {
	if (window.__) {
		return window.__(text, replace);
	}
	return text;
}

/*** Constants ***/
const CCT_DOCTYPE =
	parseInt((frappe.boot.versions?.frappe || "16").split(".")[0]) >= 16
		? "Categorie Comptable Tiers"
		: "Categorie comptable Tiers";

/*** State ***/
const pendingFlows = ref(0);
const pendingFlowsStatus = ref("ok");
const invoices = ref([]);
const loading = ref(false);
const syncing = ref(false);
const filter = ref("pending");
const expanded = ref(new Set());
const company = ref(frappe.boot.user.defaults.company || "");
const defaultCompany = frappe.defaults.get_user_default("Company") || "";

const switchingTab = ref(false);
watch(filter, () => {
	switchingTab.value = true;
	nextTick(() => {
		switchingTab.value = false;
	});
});

watch(company, async () => {
	const r = await frappe.call({
		method: "erpnext_einvoicing.providers.sync.get_buying_settings",
	});
	buyingSettings.value = r.message || {};
	await fetchInvoices(true);
	await checkPendingFlows();
});
/*** Computed ***/

const filtered = computed(() => {
	if (filter.value === "all")
		return invoices.value.filter((i) => i.conversion_status !== "refused");
	return invoices.value.filter((inv) => inv.conversion_status === filter.value);
});

const counts = computed(() => ({
	pending: invoices.value.filter((i) => i.conversion_status === "pending").length,
	ready: invoices.value.filter((i) => i.conversion_status === "ready").length,
	converted: invoices.value.filter((i) => i.conversion_status === "converted").length,
	refused: invoices.value.filter((i) => i.conversion_status === "refused").length,
}));

const groupedInvoices = computed(() => {
	const result = [];
	const childNames = new Set(
		filtered.value
			.filter((i) => i.is_credit_note && i.referenced_epurchase_invoice)
			.filter((i) => filtered.value.some((p) => p.name === i.referenced_epurchase_invoice))
			.map((i) => i.name)
	);
	for (const inv of filtered.value) {
		if (childNames.has(inv.name)) continue;
		result.push({ ...inv, _indent: false });
		const children = filtered.value.filter(
			(i) => i.is_credit_note && i.referenced_epurchase_invoice === inv.name
		);
		for (const child of children) {
			result.push({ ...child, _indent: true });
		}
	}
	// Orphan CN
	for (const inv of filtered.value) {
		if (inv.is_credit_note && inv.referenced_epurchase_invoice) {
			const parentInList = filtered.value.some(
				(i) => i.name === inv.referenced_epurchase_invoice
			);
			if (!parentInList && !result.find((i) => i.name === inv.name)) {
				result.push({ ...inv, _indent: false });
			}
		}
	}
	return result;
});

/*** Date picker ***/
const showDatePicker = ref(false);
const datePreset = ref("all");
const dateFrom = ref("");
const dateTo = ref("");
const pendingPreset = ref("30");
const pendingFrom = ref("");
const pendingTo = ref("");

const PRESETS = [
	{ key: "all", label: "All dates" },
	{ key: "today", label: "Today" },
	{ key: "7", label: "Last 7 days" },
	{ key: "30", label: "Last 30 days" },
	{ key: "90", label: "Last 90 days" },
	{ key: "365", label: "Last 12 months" },
	{ key: "custom", label: "Custom" },
];

const dateRange = computed(() => {
	const today = frappe.datetime.get_today();
	if (datePreset.value === "all") return { date_from: null, date_to: null };
	if (datePreset.value === "today") return { date_from: today, date_to: today };
	if (datePreset.value === "custom")
		return { date_from: dateFrom.value || null, date_to: dateTo.value || null };
	const from = frappe.datetime.add_days(today, -parseInt(datePreset.value) + 1);
	return { date_from: from, date_to: today };
});

const datePickerLabel = computed(() => {
	const preset = PRESETS.find((p) => p.key === datePreset.value);
	if (datePreset.value === "custom" && dateFrom.value && dateTo.value) {
		return `${frappe.datetime.str_to_user(dateFrom.value)} » ${frappe.datetime.str_to_user(
			dateTo.value
		)}`;
	}
	return preset ? __(preset.label) : __("All dates");
});

function openDatePicker() {
	pendingPreset.value = datePreset.value;
	pendingFrom.value = dateFrom.value;
	pendingTo.value = dateTo.value;
	showDatePicker.value = true;
}

function applyDatePicker() {
	datePreset.value = pendingPreset.value;
	dateFrom.value = pendingFrom.value;
	dateTo.value = pendingTo.value;
	showDatePicker.value = false;
	fetchInvoices(true);
}

function closeDatePicker() {
	showDatePicker.value = false;
}

/*** API ***/

async function fetchInvoices(silent = false) {
	const scrollY = window.scrollY;
	if (!silent) {
		loading.value = true;
	}
	try {
		const res = await frappe.call({
			method: "erpnext_einvoicing.providers.sync.get_einvoicing_inbox",
			args: {
				date_from: dateRange.value.date_from,
				date_to: dateRange.value.date_to,
				company: company.value,
			},
		});
		invoices.value = JSON.parse(JSON.stringify(res.message || []));
	} finally {
		if (!silent) {
			loading.value = false;
		} else {
			await nextTick();
			window.scrollTo(0, scrollY);
		}
	}
}

async function checkPendingFlows() {
	try {
		const r = await frappe.call({
			method: "erpnext_einvoicing.providers.sync.check_pending_flows",
			args: { sync_type: "Purchase Invoice", company: company.value },
		});
		if (r.message?.error) {
			pendingFlowsStatus.value = "error";
			pendingFlows.value = 0;
		} else {
			pendingFlows.value = r.message?.total || 0;
			pendingFlowsStatus.value = pendingFlows.value > 0 ? "pending" : "ok";
		}
	} catch {
		pendingFlowsStatus.value = "error";
		pendingFlows.value = 0;
	}
}

async function syncFlows() {
	syncing.value = true;
	try {
		const r = await frappe.call({
			method: "erpnext_einvoicing.providers.sync.sync_flows",
			args: { sync_type: "Purchase Invoice", company: company.value },
		});
		const msg = r.message || {};
		const indicator = msg.status === "ok" ? "green" : "orange";
		frappe.show_alert({ message: msg.message || __("Sync complete"), indicator }, 5);
		await fetchInvoices(true);
		await checkPendingFlows();
	} finally {
		syncing.value = false;
	}
}

function promptMatchSupplier(invoice) {
	frappe.prompt(
		[
			{
				fieldname: "matched_supplier",
				fieldtype: "Link",
				options: "Supplier",
				label: __("Select Supplier"),
				reqd: 1,
			},
		],
		async (values) => {
			// Compter les autres factures avec le même SIRET
			const siblings = await frappe.call({
				method: "erpnext_einvoicing.providers.sync.count_similar_unmatched",
				args: { name: invoice.name, match_type: "supplier" },
			});
			const count = siblings.message?.count || 0;

			const doMatch = async (apply_to_all) => {
				const r = await frappe.call({
					method: "erpnext_einvoicing.providers.sync.match_supplier",
					args: {
						name: invoice.name,
						matched_supplier: values.matched_supplier,
						apply_to_all,
					},
				});
				const msg = r.message || {};
				if (msg.status === "warning") {
					frappe.msgprint({
						message: msg.message,
						indicator: "orange",
						title: __("Warning"),
					});
					return;
				}
				let message = __("Supplier matched: {0}", [values.matched_supplier]);
				if (msg.matched_items > 0) {
					message +=
						" - " +
						__("{0}/{1} item(s) matched", [msg.matched_items, msg.total_items]);
				}
				if (msg.conversion_status === "ready") {
					message += " - " + __("Invoice is ready to convert");
				}
				frappe.show_alert({ message, indicator: "green" }, 10);
				await fetchInvoices(true);
			};

			if (count > 0) {
				frappe.confirm(
					__("Apply this supplier to {0} other invoice(s) with the same SIRET?", [
						count,
					]),
					() => doMatch(1),
					() => doMatch(0)
				);
			} else {
				await doMatch(0);
			}
		},
		__("Match Supplier"),
		__("Confirm")
	);
}

async function rematchAll() {
	syncing.value = true;
	try {
		const r = await frappe.call({
			method: "erpnext_einvoicing.providers.sync.rematch_all",
			freeze: true,
			freeze_message: __("Re-matching..."),
		});
		const msg = r.message || {};
		frappe.show_alert({ message: msg.message, indicator: "green" }, 4);
		await fetchInvoices(true);
	} finally {
		syncing.value = false;
	}
}

async function rematchSupplier(invoice) {
	const r = await frappe.call({
		method: "erpnext_einvoicing.providers.sync.rematch_supplier",
		args: { name: invoice.name },
	});
	const msg = r.message || {};
	if (msg.status === "warning") {
		frappe.msgprint({ message: msg.message, indicator: "orange", title: __("Warning") });
		return;
	}
	if (msg.status === "ok") {
		let message = __("Supplier matched: {0}", [msg.supplier]);
		if (msg.matched_items > 0) {
			message += " - " + __("{0}/{1} item(s) matched", [msg.matched_items, msg.total_items]);
		}
		if (msg.conversion_status === "ready") {
			message += " - " + __("Invoice is ready to convert");
		}
		frappe.show_alert({ message, indicator: "green" }, 10);
	} else {
		frappe.show_alert({ message: __("No supplier found"), indicator: "orange" }, 3);
	}
	await fetchInvoices(true);
}

async function confirmDeleteMatchedSupplier(invoice) {
	const siblings = await frappe.call({
		method: "erpnext_einvoicing.providers.sync.count_similar_unmatched",
		args: { name: invoice.name, match_type: "supplier_matched" },
	});
	const count = siblings.message?.count || 0;

	const doUnlink = async (apply_to_all) => {
		await frappe.call({
			method: "erpnext_einvoicing.providers.sync.unlink_matched_supplier",
			args: { name: invoice.name, apply_to_all },
		});
		await fetchInvoices(true);
	};

	if (count > 0) {
		frappe.confirm(
			__("Unlink this supplier from {0} other invoice(s) with the same SIRET?", [count]),
			() => doUnlink(1),
			() => doUnlink(0)
		);
	} else {
		await doUnlink(0);
	}
}

async function enrichFromSiret(invoice) {
	const r = await frappe.call({
		method: "erpnext_einvoicing.providers.sync.enrich_from_siret",
		args: { name: invoice.name },
		freeze: true,
		freeze_message: __("Looking up SIRET..."),
	});
	const msg = r.message || {};

	if (msg.status === "not_found") {
		frappe.show_alert(
			{ message: __("No company found for this SIRET"), indicator: "orange" },
			5
		);
		const data = msg.data || {};
		frappe.ui.form.make_quick_entry("Supplier", async (doc) => {
			await frappe.call({
				method: "erpnext_einvoicing.providers.sync.match_supplier",
				args: { name: invoice.name, matched_supplier: doc.name },
			});
			await fetchInvoices(true);
		});
		setTimeout(() => {
			const dialog = frappe.quick_entry?.dialog;
			if (dialog) {
				dialog.set_value("supplier_name", data.party_name || invoice.supplier_name_raw);
				dialog.set_value("tax_id", data.siret || invoice.supplier_siret);
				dialog.set_value("siret", data.siret || invoice.supplier_siret);
				dialog.set_value("siren", (data.siret || invoice.supplier_siret)?.substring(0, 9));
			}
		}, 300);
		return;
	}

	if (msg.status === "error") {
		frappe.msgprint({ title: __("Error"), message: msg.error, indicator: "red" });
		return;
	}

	// ok ou warning -> dialog de confirmation
	const data = msg.data || {};
	const missingFields = msg.missing_fields || [];

	const supportsSetIntro = typeof frappe.ui.Dialog.prototype.set_intro === "function";
	const sirenFields = [];
	if (missingFields.length && !supportsSetIntro) {
		sirenFields.push({
			fieldtype: "HTML",
			options: `<div class="alert alert-warning" style="padding:8px">${__(
				"Warning: some fields need your attention: {0}",
				[missingFields.join(", ")]
			)}</div>`,
		});
	}

	const customFieldsRes = await frappe.call({
		method: "erpnext_einvoicing.providers.sync.get_mandatory_supplier_custom_fields",
	});
	const mandatoryCustomFields = (customFieldsRes.message || []).map((f) => ({
		fieldname: f.fieldname,
		fieldtype: f.fieldtype,
		label: __(f.label),
		options: f.options || null,
		default: data[f.fieldname] || null,
		reqd: 1,
	}));
	const d = new frappe.ui.Dialog({
		title: __("Confirm Supplier Data"),
		fields: [
			...sirenFields,
			{
				fieldname: "party_name",
				fieldtype: "Data",
				label: __("Official Name"),
				default: data.party_name,
				reqd: 1,
			},
			{
				fieldname: "address_line1",
				fieldtype: "Data",
				label: __("Address"),
				default: data.address_line1,
			},
			{ fieldname: "zip", fieldtype: "Data", label: __("ZIP"), default: data.zip },
			{ fieldname: "city", fieldtype: "Data", label: __("City"), default: data.city },
			{
				fieldname: "country_code",
				fieldtype: "Data",
				label: __("Country Code"),
				default: data.country_code,
			},
			{ fieldname: "col", fieldtype: "Column Break" },
			{
				fieldname: "supplier_group",
				fieldtype: "Link",
				options: "Supplier Group",
				label: __("Supplier Group"),
				reqd: 1,
			},
			...mandatoryCustomFields,
		],
		primary_action_label: __("Save"),
		primary_action: async (values) => {
			const siblings = await frappe.call({
				method: "erpnext_einvoicing.providers.sync.count_similar_unmatched",
				args: { name: invoice.name, match_type: "supplier" },
			});
			const count = siblings.message?.count || 0;

			const doSave = async (apply_to_all) => {
				const r2 = await frappe.call({
					method: "erpnext_einvoicing.providers.sync.save_ethirdparty",
					args: {
						invoice_name: invoice.name,
						data: { ...data, ...values },
						supplier_group: values.supplier_group,
						apply_to_all,
					},
				});
				if (r2.message?.status === "ok") {
					frappe.show_alert(
						{ message: __("Supplier data saved"), indicator: "green" },
						4
					);
					d.hide();
					await fetchInvoices(true);
				}
			};

			if (count > 0) {
				frappe.confirm(
					__("Apply this supplier to {0} other invoice(s) with the same SIRET?", [
						count,
					]),
					() => doSave(1),
					() => doSave(0)
				);
			} else {
				await doSave(0);
			}
		},
	});

	if (missingFields.length && supportsSetIntro) {
		d.set_intro(
			__("Warning: some fields need your attention: {0}", [missingFields.join(", ")]),
			"orange"
		);
	}

	d.show();
}

function promptEditEThirdParty(invoice, ethirdparty, missingFields) {
	const supportsSetIntro = typeof frappe.ui.Dialog.prototype.set_intro === "function";
	const ethirdpartyFields = [];
	if (missingFields?.length && !supportsSetIntro) {
		ethirdpartyFields.push({
			fieldtype: "HTML",
			options: `<div class="alert alert-warning" style="padding:8px">${__(
				"Missing required fields: {0}",
				[missingFields.join(", ")]
			)}</div>`,
		});
	}

	const d = new frappe.ui.Dialog({
		title: __("Review eThirdParty Data"),
		fields: [
			...ethirdpartyFields,
			{
				fieldname: "party_name",
				fieldtype: "Data",
				label: __("Official Name"),
				default: ethirdparty.party_name,
				reqd: 1,
			},
			{ fieldname: "zip", fieldtype: "Data", label: __("ZIP"), default: ethirdparty.zip },
			{ fieldname: "city", fieldtype: "Data", label: __("City"), default: ethirdparty.city },
			{
				fieldname: "country_code",
				fieldtype: "Data",
				label: __("Country Code"),
				default: ethirdparty.country_code,
			},
			{ fieldname: "col", fieldtype: "Column Break" },
			{
				fieldname: "supplier_group",
				fieldtype: "Link",
				options: "Supplier Group",
				label: __("Supplier Group"),
				default: ethirdparty.supplier_group,
				reqd: 1,
			},
		],
		primary_action_label: __("Save"),
		async primary_action(values) {
			await frappe.call({
				method: "erpnext_einvoicing.providers.sync.update_ethirdparty",
				args: { name: ethirdparty.name, data: values },
			});
			d.hide();
			await fetchInvoices(true);
		},
	});

	if (missingFields?.length && supportsSetIntro) {
		d.set_intro(__("Missing required fields: {0}", [missingFields.join(", ")]), "orange");
	}

	d.show();
}

async function unlinkEThirdParty(invoice) {
	const siblings = await frappe.call({
		method: "erpnext_einvoicing.providers.sync.count_similar_unmatched",
		args: { name: invoice.name, match_type: "supplier_matched" },
	});
	const count = siblings.message?.count || 0;

	const doUnlink = async (apply_to_all) => {
		await frappe.call({
			method: "erpnext_einvoicing.providers.sync.unlink_ethirdparty",
			args: { name: invoice.name, apply_to_all },
		});
		await fetchInvoices(true);
	};

	if (count > 0) {
		frappe.confirm(
			__("Unlink this eThirdParty from {0} other invoice(s) with the same SIRET?", [count]),
			() => doUnlink(1),
			() => doUnlink(0)
		);
	} else {
		await doUnlink(0);
	}
}

function promptLinkPO(invoice) {
	if (invoice.supplier_match_status === "ethirdparty") {
		frappe.confirm(
			__(
				"No Purchase Order available - supplier does not exist in ERPNext yet. Convert supplier and create a Purchase Order?"
			),
			() => convertEthirdpartyAndCreatePO(invoice)
		);
		return;
	}
	frappe.prompt(
		[
			{
				fieldname: "purchase_order",
				fieldtype: "Link",
				options: "Purchase Order",
				label: __("Purchase Order"),
				reqd: 1,
				get_query: () => ({
					filters: {
						supplier: invoice.matched_supplier,
						status: ["in", ["To Receive and Bill", "Partially Billed"]],
					},
				}),
			},
		],
		async (values) => {
			await frappe.call({
				method: "erpnext_einvoicing.providers.sync.link_purchase_order",
				args: { name: invoice.name, purchase_order: values.purchase_order },
			});
			await fetchInvoices(true);
		},
		__("Link Purchase Order"),
		__("Confirm")
	);
}

async function convertEthirdpartyAndCreatePO(invoice) {
	const r = await frappe.call({
		method: "erpnext_einvoicing.providers.sync.convert_ethirdparty_for_po",
		args: { name: invoice.name },
		freeze: true,
		freeze_message: __("Converting supplier..."),
	});
	const result = r.message || {};
	if (result.status !== "ok") {
		frappe.msgprint({ message: result.error || __("Failed"), indicator: "red" });
		return;
	}
	frappe.show_alert(
		{ message: __("Supplier created: {0}", [result.supplier]), indicator: "green" },
		4
	);
	await fetchInvoices(true);
	window.open(
		`/app/purchase-order/new-purchase-order-1?supplier=${encodeURIComponent(result.supplier)}`,
		"_blank"
	);
}

async function unlinkPO(invoice) {
	await frappe.call({
		method: "erpnext_einvoicing.providers.sync.unlink_purchase_order",
		args: { name: invoice.name },
	});
	await fetchInvoices(true);
}

function promptLinkPR(invoice) {
	frappe.prompt(
		[
			{
				fieldname: "purchase_receipt",
				fieldtype: "Link",
				options: "Purchase Receipt",
				label: __("Purchase Receipt"),
				reqd: 1,
				get_query: () => ({
					filters: {
						supplier: invoice.matched_supplier,
						status: ["in", ["To Bill", "Partly Billed"]],
					},
				}),
			},
		],
		async (values) => {
			await frappe.call({
				method: "erpnext_einvoicing.providers.sync.link_purchase_receipt",
				args: { name: invoice.name, purchase_receipt: values.purchase_receipt },
			});
			await fetchInvoices(true);
		},
		__("Link Purchase Receipt"),
		__("Confirm")
	);
}

async function unlinkPR(invoice) {
	await frappe.call({
		method: "erpnext_einvoicing.providers.sync.unlink_purchase_receipt",
		args: { name: invoice.name },
	});
	await fetchInvoices(true);
}

function promptMatchItem(invoice, item) {
	frappe.prompt(
		[
			{
				fieldname: "matched_item",
				fieldtype: "Link",
				options: "Item",
				label: __("Select Item"),
				reqd: 1,
				get_query: () => ({
					filters: { is_purchase_item: 1 },
				}),
			},
		],
		async (values) => {
			const siblings = await frappe.call({
				method: "erpnext_einvoicing.providers.sync.count_similar_unmatched",
				args: { name: invoice.name, match_type: "item", item_idx: item.idx },
			});
			const count = siblings.message?.count || 0;

			const doMatch = async (apply_to_all) => {
				await frappe.call({
					method: "erpnext_einvoicing.providers.sync.match_item",
					args: {
						name: invoice.name,
						item_idx: item.idx,
						matched_item: values.matched_item,
						apply_to_all,
					},
				});
				await fetchInvoices(true);
			};

			if (count > 0) {
				frappe.confirm(
					__("Apply this item to {0} other line(s) with the same supplier reference?", [
						count,
					]),
					() => doMatch(1),
					() => doMatch(0)
				);
			} else {
				await doMatch(0);
			}
		},
		__("Match Item: {0}", [item.item_description_raw]),
		__("Confirm")
	);
}

async function rematchItems(invoice) {
	await frappe.call({
		method: "erpnext_einvoicing.providers.sync.rematch_items",
		args: { name: invoice.name },
	});
	frappe.show_alert({ message: __("Items re-matched"), indicator: "green" }, 3);
	await fetchInvoices(true);
}

function editItemTaxRate(invoice, item) {
	frappe.prompt(
		[
			{
				fieldname: "account_head",
				fieldtype: "Link",
				options: "Account",
				label: __("Tax Account"),
				default: item.tax_account_head || "",
				get_query: () => ({
					filters: {
						company: invoice.company,
						account_type: "Tax",
						root_type: "Asset",
					},
				}),
			},
		],
		async (values) => {
			const doUpdate = async (apply_to_all) => {
				await frappe.call({
					method: "erpnext_einvoicing.providers.sync.update_item_tax_rate",
					args: {
						name: invoice.name,
						item_idx: item.idx,
						account_head: values.account_head,
						apply_to_all,
					},
				});
				await fetchInvoices(true);
			};

			if (!invoice.matched_supplier) {
				await doUpdate(0);
				return;
			}

			const tax_rate = item.tax_rate;
			const siblings = await frappe.call({
				method: "erpnext_einvoicing.providers.sync.count_similar_tax_items",
				args: {
					name: invoice.name,
					tax_rate: item.tax_rate,
				},
			});
			const count = siblings.message?.count || 0;

			if (count > 0) {
				frappe.confirm(
					__(
						"Apply this tax account to {0} other item(s) with the same supplier and tax rate?",
						[count]
					),
					() => doUpdate(1),
					() => doUpdate(0)
				);
			} else {
				await doUpdate(0);
			}
		},
		__("Edit Tax Account"),
		__("Save")
	);
}

async function confirmDeleteMatchedItem(invoice, item) {
	const siblings = await frappe.call({
		method: "erpnext_einvoicing.providers.sync.count_similar_unmatched",
		args: { name: invoice.name, match_type: "item_matched", item_idx: item.idx },
	});
	const count = siblings.message?.count || 0;

	const doUnlink = async (apply_to_all) => {
		await frappe.call({
			method: "erpnext_einvoicing.providers.sync.unlink_matched_item",
			args: { name: invoice.name, item_idx: item.idx, apply_to_all },
		});
		await fetchInvoices(true);
	};

	if (count > 0) {
		frappe.confirm(
			__("Unlink this item from {0} other line(s) with the same supplier reference?", [
				count,
			]),
			() => doUnlink(1),
			() => doUnlink(0)
		);
	} else {
		await doUnlink(0);
	}
}

async function createItem(invoice, item) {
	frappe.prompt(
		[
			{
				fieldname: "item_name",
				fieldtype: "Data",
				label: __("Item Name"),
				default: item.item_description_raw,
				reqd: 1,
			},
			{
				fieldname: "item_group",
				fieldtype: "Link",
				options: "Item Group",
				label: __("Item Group"),
				reqd: 1,
			},
		],
		async (values) => {
			const r = await frappe.call({
				method: "erpnext_einvoicing.providers.sync.create_item",
				args: {
					name: invoice.name,
					item_idx: item.idx,
					item_name: values.item_name,
					item_group: values.item_group,
				},
			});
			const msg = r.message || {};
			if (msg.status === "ok") {
				frappe.show_alert(
					{ message: __("Item created: {0}", [msg.item]), indicator: "green" },
					4
				);
				await fetchInvoices(true);
			} else {
				frappe.msgprint({
					title: __("Error"),
					message: msg.error || __("Failed"),
					indicator: "red",
				});
			}
		},
		__("Create Item"),
		__("Create")
	);
}

function canConvert(invoice) {
	if (invoice.is_credit_note && creditNoteBlockReason(invoice) !== null) return false;
	if (invoice.conversion_status !== "ready") return false;
	if (buyingSettings.value.po_required) {
		const hasPO =
			invoice.purchase_order ||
			invoice.items?.some((i) => i.purchase_order && i.match_status === "matched");
		if (!hasPO) return false;
	}
	if (buyingSettings.value.pr_required) {
		const hasPR =
			invoice.purchase_receipt ||
			invoice.items?.some((i) => i.purchase_receipt && i.match_status === "matched");
		if (!hasPR) return false;
	}
	return true;
}

async function convertToPI(invoice) {
	frappe.confirm(__("Convert {0} to a Purchase Invoice draft?", [invoice.name]), async () => {
		const r = await frappe.call({
			method: "erpnext_einvoicing.providers.sync.convert_to_purchase_invoice",
			args: { name: invoice.name },
			freeze: true,
			freeze_message: __("Converting..."),
		});
		if (r.message) {
			frappe.show_alert(
				{
					message: __("Purchase Invoice {0} created", [r.message]),
					indicator: "green",
				},
				5
			);
			await fetchInvoices(true);
		}
	});
}

async function convertAll() {
	const readyNames = filtered.value
		.filter((i) => i.conversion_status === "ready")
		.map((i) => i.name);

	frappe.confirm(__("Convert all {0} ready invoice(s)?", [readyNames.length]), async () => {
		syncing.value = true;
		try {
			const r = await frappe.call({
				method: "erpnext_einvoicing.providers.sync.convert_all_ready",
				args: { names: JSON.stringify(readyNames) },
				freeze: true,
				freeze_message: __("Converting..."),
			});
			const msg = r.message || {};
			frappe.show_alert(
				{
					message: msg.message,
					indicator: msg.status === "ok" ? "green" : "orange",
				},
				5
			);
			await fetchInvoices(true);
		} finally {
			syncing.value = false;
		}
	});
}

async function cancelConversion(invoice) {
	frappe.confirm(
		__("Delete the linked Purchase Invoice draft and reset this invoice?"),
		async () => {
			const r = await frappe.call({
				method: "erpnext_einvoicing.providers.sync.cancel_conversion",
				args: { name: invoice.name },
			});
			const msg = r.message || {};
			if (msg.status === "ok") {
				frappe.show_alert({ message: __("Conversion cancelled"), indicator: "green" }, 3);
			} else {
				frappe.msgprint({ message: msg.error, indicator: "red" });
			}
			await fetchInvoices(true);
		}
	);
}

function promptRefuse(invoice) {
	if (invoice.is_credit_note) {
		const ref_status = invoice.ref_status;
		if (
			!invoice.referenced_epurchase_invoice ||
			ref_status === "pending" ||
			ref_status === "ready"
		) {
			frappe.msgprint({
				message: creditNoteBlockReason(invoice),
				indicator: "orange",
				title: __("Action not allowed"),
			});
			return;
		}
	}
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
		async (values) => {
			const r = await frappe.call({
				method: "erpnext_einvoicing.providers.sync.refuse_invoice",
				args: {
					name: invoice.name,
					reason_code: values.reason_code,
					reason_comment: values.reason_comment || null,
				},
				freeze: true,
				freeze_message: __("Sending refusal..."),
			});
			const msg = r.message || {};
			if (msg.status === "ok") {
				frappe.show_alert(
					{ message: __("Invoice successfully refused"), indicator: "green" },
					10
				);
				await fetchInvoices(true);
			} else {
				frappe.msgprint({ message: msg.error || __("Failed"), indicator: "red" });
			}
		},
		__("Refuse Invoice"),
		__("Confirm Refusal")
	);
}

/*** UI helpers ***/

function supplierReady(invoice) {
	return invoice.supplier_match_status === "matched" || !!invoice.ethirdparty_doc;
}

function toggleExpand(name) {
	if (expanded.value.has(name)) {
		expanded.value.delete(name);
	} else {
		expanded.value.add(name);
	}
	expanded.value = new Set(expanded.value);
}

function formatCurrency(amount, currency) {
	return new Intl.NumberFormat(frappe.boot.lang || "fr-FR", {
		style: "currency",
		currency: currency || "EUR",
	}).format(amount || 0);
}

function formatDate(dateStr) {
	if (!dateStr) return "";
	return frappe.datetime.str_to_user(dateStr);
}

function isLocked(invoice) {
	return ["converted", "refused"].includes(invoice.conversion_status);
}

function poStatusIcon(status) {
	if (status === "matched") return { icon: "fa fa-check-circle", color: "#5cb85c" };
	if (status === "partial") return { icon: "fa fa-info-circle", color: "#5bc0de" };
	if (status === "ambiguous") return { icon: "fa fa-exclamation-triangle", color: "#f0ad4e" };
	return { icon: "fa fa-circle-o", color: "#ddd" };
}

async function promptSelectPO(invoice, item) {
	const r = await frappe.call({
		method: "erpnext_einvoicing.providers.sync.get_po_candidates",
		args: { name: invoice.name, item_idx: item.idx },
	});
	const candidates = r.message || [];
	if (!candidates.length) {
		frappe.show_alert(
			{ message: __("No Purchase Order found for this item"), indicator: "orange" },
			4
		);
		return;
	}
	const d = new frappe.ui.Dialog({
		title: __("Select Purchase Order Line"),
		fields: candidates.map((c, i) => ({
			fieldname: `po_${i}`,
			fieldtype: "HTML",
			options: `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px;border:1px solid #f0f0f0;border-radius:4px;margin-bottom:6px;cursor:pointer"
                data-idx="${i}"
                onclick="this.closest('.modal-body').querySelectorAll('[data-idx]').forEach(el=>el.style.background='');this.style.background='#e8f4f0';window._selectedPOIdx=${i}">
                <span style="font-weight:500">${c.parent}</span>
                <span style="color:#888;font-size:12px">${c.item_name}</span>
                <span style="color:#333;font-size:12px">${__("Remaining")}: <b>${
				c.remaining_qty
			}</b></span>
            </div>`,
		})),
		primary_action_label: __("Link"),
		primary_action: async () => {
			const idx = window._selectedPOIdx;
			if (idx === undefined || idx === null) {
				frappe.show_alert({ message: __("Please select a line"), indicator: "orange" }, 3);
				return;
			}
			const selected = candidates[idx];
			await frappe.call({
				method: "erpnext_einvoicing.providers.sync.match_item_po",
				args: {
					name: invoice.name,
					item_idx: item.idx,
					purchase_order: selected.parent,
					po_detail: selected.name,
				},
			});
			d.hide();
			window._selectedPOIdx = null;
			await fetchInvoices(true);
		},
	});
	d.show();
}

async function promptSelectPR(invoice, item) {
	const r = await frappe.call({
		method: "erpnext_einvoicing.providers.sync.get_pr_candidates",
		args: { name: invoice.name, item_idx: item.idx },
	});
	const candidates = r.message || [];
	if (!candidates.length) {
		frappe.show_alert(
			{ message: __("No Purchase Receipt found for this item"), indicator: "orange" },
			4
		);
		return;
	}
	const d = new frappe.ui.Dialog({
		title: __("Select Purchase Receipt Line"),
		fields: candidates.map((c, i) => ({
			fieldname: `pr_${i}`,
			fieldtype: "HTML",
			options: `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px;border:1px solid #f0f0f0;border-radius:4px;margin-bottom:6px;cursor:pointer"
                data-idx="${i}"
                onclick="this.closest('.modal-body').querySelectorAll('[data-idx]').forEach(el=>el.style.background='');this.style.background='#e8f4f0';window._selectedPRIdx=${i}">
                <span style="font-weight:500">${c.parent}</span>
                <span style="color:#888;font-size:12px">${c.item_name}</span>
                <span style="color:#333;font-size:12px">${__("Remaining")}: <b>${
				c.remaining_qty
			}</b></span>
            </div>`,
		})),
		primary_action_label: __("Link"),
		primary_action: async () => {
			const idx = window._selectedPRIdx;
			if (idx === undefined || idx === null) {
				frappe.show_alert({ message: __("Please select a line"), indicator: "orange" }, 3);
				return;
			}
			const selected = candidates[idx];
			await frappe.call({
				method: "erpnext_einvoicing.providers.sync.match_item_pr",
				args: {
					name: invoice.name,
					item_idx: item.idx,
					purchase_receipt: selected.parent,
					pr_detail: selected.name,
				},
			});
			d.hide();
			window._selectedPRIdx = null;
			await fetchInvoices(true);
		},
	});
	d.show();
}

async function unlinkItemPO(invoice, item) {
	await frappe.call({
		method: "erpnext_einvoicing.providers.sync.unlink_item_po",
		args: { name: invoice.name, item_idx: item.idx },
	});
	await fetchInvoices(true);
}

async function unlinkItemPR(invoice, item) {
	await frappe.call({
		method: "erpnext_einvoicing.providers.sync.unlink_item_pr",
		args: { name: invoice.name, item_idx: item.idx },
	});
	await fetchInvoices(true);
}

function creditNoteBlockReason(invoice) {
	if (!invoice.is_credit_note) return null;
	const ref_status = invoice.ref_status;
	if (!invoice.referenced_epurchase_invoice)
		return __("Referenced invoice not found - cannot process this credit note");
	if (ref_status === "refused")
		return __("Referenced invoice {0} was refused - you must refuse this credit note", [
			invoice.referenced_invoice_number,
		]);
	if (ref_status === "pending" || ref_status === "ready")
		return __("Referenced invoice {0} must be accepted before processing this credit note", [
			invoice.referenced_invoice_number,
		]);
	return null;
}

/*** Lifecycle ***/
const buyingSettings = ref({ po_required: false, pr_required: false });
const companies = ref([]);
onMounted(async () => {
	const bs = await frappe.call({
		method: "erpnext_einvoicing.providers.sync.get_buying_settings",
	});
	buyingSettings.value = bs.message || {};
	const comp = await frappe.call({
		method: "frappe.client.get_list",
		args: { doctype: "Company", fields: ["name"], limit: 100 },
	});
	companies.value = (comp.message || []).map((c) => c.name);
	await fetchInvoices();
	await checkPendingFlows();
});

function lifecycleIcon(log) {
	if (log.ack_status === "ok") return "fa fa-check-circle";
	if (log.ack_status === "error") return "fa fa-exclamation-circle";
	return "fa fa-clock-o";
}

function lifecycleIconColor(log) {
	if (log.ack_status === "ok") return "#5cb85c";
	if (log.ack_status === "error") return "#d9534f";
	return "#aaa";
}

function lifecycleTooltip(log) {
	if (log.ack_status === "ok") return __("Acknowledged by platform");
	if (log.ack_status === "error" && log.error_type === "data")
		return (log.ack_message || "") + " - " + __("Data error (contact support)");
	if (log.ack_status === "error" && log.error_type === "platform")
		return (log.ack_message || "") + " - " + __("Platform error");
	return __("Pending acknowledgement");
}

async function refreshLifecycleLog(invoice) {
	if (!invoice.last_lifecycle_log) return;
	await frappe.call({
		method: "erpnext_einvoicing.providers.sync.poll_single_lifecycle_log",
		args: { log_name: invoice.last_lifecycle_log.name },
	});
	await fetchInvoices(true);
}
</script>

<template>
	<div class="einvoicing-inbox" style="padding: 16px">
		<div
			v-if="defaultCompany"
			style="font-size: 16px; font-weight: 600; color: #333; margin-bottom: 12px"
		>
			{{ __("Company") + ": " + company }}
		</div>

		<!-- Toolbar -->
		<div
			style="
				display: flex;
				justify-content: space-between;
				align-items: center;
				margin-bottom: 16px;
			"
		>
			<div class="btn-group">
				<button
					v-for="tab in ['all', 'pending', 'ready', 'converted', 'refused']"
					:key="tab"
					:class="['btn btn-sm', filter === tab ? 'btn-primary' : 'btn-default']"
					@click="filter = tab"
				>
					{{ __(`${tab.charAt(0).toUpperCase()}${tab.slice(1)}`) }}
					<span
						v-if="tab !== 'all' && counts[tab]"
						class="badge"
						style="margin-left: 4px"
					>
						{{ counts[tab] }}
					</span>
				</button>
			</div>

			<!-- Date picker -->
			<div style="position: relative">
				<button
					class="btn btn-sm btn-default"
					style="font-size: 12px; display: flex; align-items: center; gap: 6px"
					@click="openDatePicker"
				>
					<i class="fa fa-calendar" style="color: #888"></i>
					{{ datePickerLabel }}
					<i class="fa fa-caret-down" style="color: #888; font-size: 10px"></i>
				</button>

				<!-- Dropdown -->
				<div
					v-if="showDatePicker"
					style="
						position: absolute;
						top: calc(100% + 6px);
						right: 0;
						z-index: 1000;
						background: #fff;
						border: 1px solid #d1d8dd;
						border-radius: 8px;
						box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
						display: flex;
						min-width: 480px;
					"
				>
					<!-- Presets -->
					<div style="width: 180px; border-right: 1px solid #f0f0f0; padding: 8px 0">
						<div
							v-for="preset in PRESETS"
							:key="preset.key"
							@click="pendingPreset = preset.key"
							style="
								padding: 8px 16px;
								cursor: pointer;
								font-size: 13px;
								border-radius: 4px;
								margin: 0 6px;
							"
							:style="
								pendingPreset === preset.key
									? 'background: #e8f4f0; color: #2490ef; font-weight: 500'
									: 'color: #333'
							"
						>
							{{ __(preset.label) }}
						</div>
					</div>

					<!-- Right side -->
					<div
						style="
							flex: 1;
							padding: 16px;
							display: flex;
							flex-direction: column;
							justify-content: space-between;
						"
					>
						<!-- Custom inputs -->
						<div v-if="pendingPreset === 'custom'">
							<div
								style="
									font-size: 12px;
									color: #888;
									margin-bottom: 12px;
									text-transform: uppercase;
									letter-spacing: 0.5px;
								"
							>
								{{ __("Date range") }}
							</div>
							<div style="display: flex; align-items: center; gap: 8px">
								<div style="flex: 1">
									<div style="font-size: 11px; color: #aaa; margin-bottom: 4px">
										{{ __("From") }}
									</div>
									<input
										v-model="pendingFrom"
										type="date"
										class="form-control form-control-sm"
										style="font-size: 12px"
									/>
								</div>
								<div style="color: #ccc; margin-top: 16px">&raquo;</div>
								<div style="flex: 1">
									<div style="font-size: 11px; color: #aaa; margin-bottom: 4px">
										{{ __("To") }}
									</div>
									<input
										v-model="pendingTo"
										type="date"
										class="form-control form-control-sm"
										style="font-size: 12px"
									/>
								</div>
							</div>
						</div>

						<!-- Preset summary -->
						<div v-else style="color: #aaa; font-size: 13px; padding-top: 8px">
							{{ __(PRESETS.find((p) => p.key === pendingPreset)?.label || "") }}
						</div>

						<!-- Footer -->
						<div
							style="
								display: flex;
								justify-content: flex-end;
								gap: 8px;
								margin-top: 24px;
							"
						>
							<button class="btn btn-sm btn-default" @click="closeDatePicker">
								{{ __("Cancel") }}
							</button>
							<button
								class="btn btn-sm btn-primary"
								style="min-width: 80px"
								@click="applyDatePicker"
							>
								{{ __("Apply") }}
							</button>
						</div>
					</div>
				</div>

				<!-- Backdrop -->
				<div
					v-if="showDatePicker"
					style="position: fixed; inset: 0; z-index: 999"
					@click="closeDatePicker"
				></div>
			</div>
			<div style="display: flex; align-items: center; gap: 8px">
				<select
					v-if="companies.length > 1"
					v-model="company"
					class="form-control form-control-sm"
					style="width: auto; font-size: 12px"
					@change="fetchInvoices(true)"
				>
					<option v-for="c in companies" :key="c" :value="c">{{ c }}</option>
				</select>
				<button
					v-if="filter === 'pending'"
					class="btn btn-sm btn-default"
					style="margin-right: 10px"
					:disabled="syncing"
					@click="rematchAll"
					:title="__('Re-match all pending invoices')"
				>
					<i class="fa fa-magic"></i>
					{{ __("Re-match All") }}
				</button>
				<button
					v-if="filter === 'ready' && counts.ready > 0"
					class="btn btn-sm btn-primary"
					style="margin-right: 10px"
					:disabled="syncing"
					@click="convertAll"
				>
					<i class="fa fa-arrow-circle-o-right"></i> {{ __("Convert All") }}
				</button>
				<button class="btn btn-sm btn-default" :disabled="syncing" @click="syncFlows">
					<i :class="['fa', syncing ? 'fa-spinner fa-spin' : 'fa-refresh']"></i>
					{{ __("Sync") }}
					<span style="display: inline-flex; align-items: center; margin-left: 4px">
						<span
							v-if="pendingFlowsStatus === 'pending'"
							style="font-size: 11px; color: #f0ad4e"
							:title="pendingFlows + ' ' + __('invoices pending')"
						>
							<i class="fa fa-circle" style="font-size: 8px"></i>
							{{ pendingFlows }}
						</span>
						<span
							v-else-if="pendingFlowsStatus === 'ok'"
							style="font-size: 11px; color: #5cb85c"
							:title="__('Up to date')"
						>
							<i class="fa fa-check" style="font-size: 10px"></i>
						</span>
						<span
							v-else-if="pendingFlowsStatus === 'error'"
							style="font-size: 11px; color: #d9534f"
							:title="__('Provider error')"
						>
							<i
								class="fa fa-exclamation-circle"
								style="font-size: 10px; opacity: 0.7"
							></i>
						</span>
					</span>
				</button>
			</div>
		</div>

		<!-- Loading -->
		<div v-if="loading" style="text-align: center; padding: 40px; color: #888">
			<i class="fa fa-spinner fa-spin fa-2x"></i>
		</div>

		<!-- Empty -->
		<div
			v-else-if="filtered.length === 0"
			style="text-align: center; padding: 60px; color: #888"
		>
			<i class="fa fa-inbox fa-3x" style="margin-bottom: 12px"></i>
			<p>{{ __("No invoices to display") }}</p>
		</div>

		<!-- Invoice list -->
		<TransitionGroup
			v-else
			:name="switchingTab ? '' : 'invoice-fade'"
			tag="div"
			style="position: relative"
		>
			<div
				v-for="invoice in groupedInvoices"
				:key="invoice.name"
				:style="`
					position: relative;
					border: 1px solid #d1d8dd;
					border-left: 3px solid ${invoice.is_credit_note ? '#5bc0de' : '#d1d8dd'};
					margin-left: ${invoice._indent ? '32px' : '0'};
					border-radius: 6px;
					margin-bottom: 12px;
					background: #fff;
				`"
			>
				<div
					v-if="invoice._indent"
					style="
						position: absolute;
						left: -20px;
						top: 5%;
						transform: translateY(-50%);
						color: #5bc0de;
						font-size: 14px;
					"
				>
					<i class="fa fa-level-up fa-rotate-90"></i>
				</div>
				<!-- Card header -->
				<div
					style="
						display: flex;
						justify-content: space-between;
						align-items: center;
						padding: 12px 16px;
						border-bottom: 1px solid #f0f0f0;
					"
				>
					<div style="display: flex; align-items: center; gap: 10px">
						<a
							:href="`/app/epurchase-invoice/${invoice.name}`"
							style="font-weight: 600"
						>
							{{ invoice.name }}
						</a>
						<span
							v-if="invoice.is_credit_note"
							class="indicator-pill blue"
							style="font-size: 11px"
						>
							{{ __("Credit Note") }}
						</span>
						<a
							v-if="invoice.pdf_url"
							:href="invoice.pdf_url"
							target="_blank"
							style="color: #888; margin-right: 6px"
							:title="__('View PDF')"
						>
							<i class="fa fa-file-pdf-o" style="font-size: 13px"></i>
						</a>
						<span v-if="invoice.buyer_siret" style="color: #888; font-size: 12px">
							{{ invoice.company || invoice.buyer_siret }}
						</span>
						<span
							:class="`indicator-pill ${
								{
									pending: 'orange',
									ready: 'green',
									converted: 'blue',
									refused: 'red',
								}[invoice.conversion_status] || 'grey'
							}`"
						>
							{{ __(invoice.conversion_status) }}
						</span>
						<span
							v-if="invoice.last_lifecycle_log"
							style="display: flex; align-items: center; gap: 4px; margin-left: 4px"
						>
							<i
								:class="lifecycleIcon(invoice.last_lifecycle_log)"
								:style="`color: ${lifecycleIconColor(
									invoice.last_lifecycle_log
								)}; opacity: 0.6; font-size: 11px`"
								:title="lifecycleTooltip(invoice.last_lifecycle_log)"
							></i>
							<span style="font-size: 11px; color: #bbb">
								[{{ invoice.last_lifecycle_log.status_code }}]
								{{ invoice.last_lifecycle_log.status_label }}
								<span
									v-if="invoice.last_lifecycle_log.ack_status === 'error'"
									style="font-size: 10px; color: #ccc"
								>
									·
									{{
										invoice.last_lifecycle_log.error_type === "data"
											? __("Data error")
											: __("Platform error")
									}}
								</span>
							</span>
							<i
								v-if="invoice.last_lifecycle_log.ack_status !== 'ok'"
								class="fa fa-refresh"
								style="
									font-size: 10px;
									color: #ccc;
									cursor: pointer;
									margin-left: 2px;
								"
								:title="__('Re-poll acknowledgement')"
								@click.stop="refreshLifecycleLog(invoice)"
							></i>
						</span>
					</div>
					<div
						style="
							display: flex;
							align-items: center;
							gap: 16px;
							color: #6c757d;
							font-size: 13px;
						"
					>
						<span>{{ invoice.invoice_number }}</span>
						<span>{{ formatDate(invoice.invoice_date) }}</span>
						<strong style="color: #333">{{
							formatCurrency(invoice.total_ttc, invoice.currency)
						}}</strong>
					</div>
				</div>

				<!-- Supplier section -->
				<div style="padding: 12px 16px; border-bottom: 1px solid #f0f0f0">
					<div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
						<span
							style="
								font-size: 12px;
								color: #888;
								text-transform: uppercase;
								letter-spacing: 0.5px;
							"
							>{{ __("Supplier") }}</span
						>
						<span style="font-weight: 500">{{ invoice.supplier_name_raw }}</span>
						<span v-if="invoice.supplier_siret" style="color: #888; font-size: 12px">
							SIRET: {{ invoice.supplier_siret }}
						</span>
						<span
							v-else-if="invoice.supplier_siren"
							style="color: #888; font-size: 12px"
						>
							SIREN: {{ invoice.supplier_siren }}
						</span>
						<span
							:class="`indicator-pill ${
								{
									unmatched: 'red',
									matched: 'green',
									ethirdparty: 'orange',
									created: 'blue',
								}[invoice.supplier_match_status] || 'grey'
							}`"
							style="font-size: 11px"
						>
							{{ __(invoice.supplier_match_status) }}
						</span>

						<!-- Badge SIRENE status -->
						<span
							v-if="invoice.sirene_status && invoice.sirene_status !== 'not_found'"
							:class="`indicator-pill ${
								invoice.sirene_status === 'ok' ? 'green' : 'orange'
							}`"
							style="font-size: 11px; cursor: pointer"
							@click="enrichFromSiret(invoice)"
							:title="__('Click to review')"
						>
							SIRENE
							<i
								:class="
									invoice.sirene_status === 'warning'
										? 'fa fa-exclamation-triangle'
										: 'fa fa-check'
								"
							></i>
						</span>
						<template v-if="!isLocked(invoice)">
							<!-- Supplier matched -->
							<template v-if="invoice.supplier_match_status === 'matched'">
								<i class="fa fa-link" style="color: green"></i>
								<a
									:href="`/app/supplier/${invoice.matched_supplier}`"
									target="_blank"
									>{{ invoice.matched_supplier }}</a
								>
								<span
									@click="confirmDeleteMatchedSupplier(invoice)"
									style="cursor: pointer"
								>
									<i class="fa fa-times" style="color: #c11d1d"></i>
								</span>
							</template>

							<!-- eThirdParty -->
							<template v-else-if="invoice.ethirdparty_doc">
								<i class="fa fa-user-o" style="color: #6c757d"></i>
								<a
									:href="`/app/ethirdparty/${invoice.ethirdparty_doc.name}`"
									target="_blank"
								>
									<span>{{
										invoice.ethirdparty_doc.party_name ||
										invoice.supplier_name_raw
									}}</span>
								</a>
								<button
									v-if="invoice.ethirdparty_doc.status === 'warning'"
									class="btn btn-xs btn-warning"
									@click="
										promptEditEThirdParty(invoice, invoice.ethirdparty_doc, [])
									"
								>
									<i class="fa fa-edit"></i> {{ __("Edit") }}
								</button>
								<span @click="unlinkEThirdParty(invoice)" style="cursor: pointer">
									<i class="fa fa-times" style="color: #c11d1d"></i>
								</span>
							</template>

							<!-- Unmatched -->
							<template v-else>
								<button
									class="btn btn-xs btn-default"
									@click="rematchSupplier(invoice)"
								>
									<i class="fa fa-refresh"></i> {{ __("Check") }}
								</button>
								<button
									class="btn btn-xs btn-default"
									@click="promptMatchSupplier(invoice)"
								>
									<i class="fa fa-link"></i> {{ __("Match") }}
								</button>
								<button
									v-if="invoice.supplier_siret || invoice.supplier_siren"
									class="btn btn-xs btn-default"
									@click="enrichFromSiret(invoice)"
								>
									<i class="fa fa-search"></i> {{ __("SIRENE") }}
								</button>
								<span
									v-if="invoice.sirene_status === 'not_found'"
									class="indicator-pill red"
									style="font-size: 11px"
								>
									SIRENE <i class="fa fa-close"></i>
								</span>
							</template>
						</template>
					</div>
				</div>

				<!-- Purchase Flow section -->
				<div
					v-if="buyingSettings.po_required || buyingSettings.pr_required"
					style="padding: 12px 16px; border-bottom: 1px solid #f0f0f0"
				>
					<div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap">
						<span
							style="
								font-size: 12px;
								color: #888;
								text-transform: uppercase;
								letter-spacing: 0.5px;
							"
						>
							{{ __("Purchase Flow") }}
						</span>

						<!-- PO -->
						<template v-if="buyingSettings.po_required">
							<span style="font-size: 12px">{{ __("PO") }}:</span>
							<template v-if="invoice.purchase_order">
								<a
									:href="`/app/purchase-order/${invoice.purchase_order}`"
									target="_blank"
									style="font-size: 12px"
								>
									{{ invoice.purchase_order }}
								</a>
								<span
									v-if="!isLocked(invoice)"
									@click="unlinkPO(invoice)"
									style="cursor: pointer"
								>
									<i class="fa fa-times" style="color: #c11d1d"></i>
								</span>
							</template>
							<button
								v-else-if="!isLocked(invoice)"
								class="btn btn-xs btn-default"
								@click="promptLinkPO(invoice)"
								:disabled="invoice.supplier_match_status === 'unmatched'"
								:title="
									invoice.supplier_match_status === 'unmatched'
										? __('Match a supplier first')
										: ''
								"
							>
								<i class="fa fa-link"></i> {{ __("Link PO") }}
							</button>
						</template>

						<!-- PR -->
						<template v-if="buyingSettings.pr_required">
							<span style="font-size: 12px">{{ __("PR") }}:</span>
							<template v-if="invoice.purchase_receipt">
								<a
									:href="`/app/purchase-receipt/${invoice.purchase_receipt}`"
									target="_blank"
									style="font-size: 12px"
								>
									{{ invoice.purchase_receipt }}
								</a>
								<span
									v-if="!isLocked(invoice)"
									@click="unlinkPR(invoice)"
									style="cursor: pointer"
								>
									<i class="fa fa-times" style="color: #c11d1d"></i>
								</span>
							</template>
							<button
								v-else-if="!isLocked(invoice)"
								class="btn btn-xs btn-warning"
								@click="promptLinkPR(invoice)"
								:disabled="!supplierReady(invoice)"
								:title="
									invoice.supplier_match_status === 'ethirdparty'
										? __(
												'Supplier is an eThirdParty - a matched ERPNext Supplier is required to link Receipts'
										  )
										: !invoice.matched_supplier
										? __('Match a supplier first')
										: ''
								"
							>
								<i class="fa fa-link"></i> {{ __("Link Receipt") }}
							</button>
						</template>
					</div>
				</div>

				<!-- Items section -->
				<div style="padding: 0; background: #fafafa">
					<div
						style="
							display: flex;
							justify-content: space-between;
							align-items: center;
							padding: 10px 16px;
							cursor: pointer;
							user-select: none;
						"
						@click="toggleExpand(invoice.name)"
					>
						<span
							style="
								font-size: 12px;
								color: #888;
								text-transform: uppercase;
								letter-spacing: 0.5px;
							"
						>
							{{ __("Items") }} ({{ invoice.items?.length || 0 }})
						</span>
						<i
							:class="[
								'fa',
								expanded.has(invoice.name) ? 'fa-chevron-up' : 'fa-chevron-down',
							]"
							style="color: #888"
						></i>
					</div>

					<div v-if="expanded.has(invoice.name)" style="padding: 0 16px 12px">
						<div
							v-for="item in invoice.items"
							:key="item.idx"
							style="
								display: flex;
								justify-content: space-between;
								align-items: center;
								padding: 6px 0;
								border-top: 1px solid #f5f5f5;
							"
						>
							<div style="flex: 1">
								<!-- Ligne principale -->
								<div
									style="
										display: flex;
										align-items: center;
										flex-wrap: wrap;
										gap: 4px;
									"
								>
									<span style="font-weight: 500">{{
										item.item_description_raw
									}}</span>
									<span
										v-if="item.item_ref_raw"
										style="color: #888; font-size: 12px"
									>
										- {{ item.item_ref_raw }} -
									</span>
									<span style="color: #666; font-size: 12px">
										{{ item.qty }} ×
										{{ formatCurrency(item.unit_price, invoice.currency) }}
									</span>
									<span style="font-size: 11px; color: #aaa; margin-left: 8px">
										<span v-if="item.tax_account_name">
											{{ item.tax_account_name }}
											<span style="opacity: 0.6"
												>({{ item.tax_rate }}%)</span
											>
										</span>
										<span v-else-if="item.tax_rate"
											>TVA {{ item.tax_rate }}%</span
										>
										<span v-else>{{ __("No tax") }}</span>
										<i
											v-if="!isLocked(invoice) && supplierReady(invoice)"
											class="fa fa-pencil"
											style="cursor: pointer; margin-left: 6px"
											@click="editItemTaxRate(invoice, item)"
										></i>
									</span>
								</div>

								<!-- Ligne PO/PR — uniquement si item matché -->
								<div
									v-if="item.match_status === 'matched'"
									style="
										display: flex;
										align-items: center;
										gap: 16px;
										margin-top: 4px;
									"
								>
									<!-- PO -->
									<span
										style="
											display: flex;
											align-items: center;
											gap: 4px;
											font-size: 11px;
										"
									>
										<i
											:class="poStatusIcon(item.po_match_status).icon"
											:style="`color: ${
												poStatusIcon(item.po_match_status).color
											}; font-size: 11px`"
										></i>
										<template
											v-if="
												item.po_match_status === 'matched' ||
												item.po_match_status === 'partial'
											"
										>
											<a
												:href="`/app/purchase-order/${item.purchase_order}`"
												target="_blank"
												style="color: #666; font-size: 11px"
											>
												{{ item.purchase_order }}
											</a>
											<span
												v-if="item.po_match_status === 'partial'"
												style="color: #5bc0de; font-size: 10px"
												:title="__('Quantity differs from PO line')"
											>
												{{ __("Partial") }}
											</span>
											<i
												v-if="!isLocked(invoice)"
												class="fa fa-times"
												style="
													color: #ccc;
													cursor: pointer;
													font-size: 10px;
												"
												@click.stop="unlinkItemPO(invoice, item)"
											></i>
										</template>
										<template v-else-if="item.po_match_status === 'ambiguous'">
											<template v-if="invoice.purchase_order">
												<a
													:href="`/app/purchase-order/${invoice.purchase_order}`"
													target="_blank"
													style="color: #666; font-size: 11px"
												>
													{{ invoice.purchase_order }}
												</a>
												<span style="color: #aaa; font-size: 10px">{{
													__("(header)")
												}}</span>
											</template>
											<button
												v-else-if="!isLocked(invoice)"
												class="btn btn-xs btn-warning"
												style="font-size: 10px; padding: 1px 6px"
												@click.stop="promptSelectPO(invoice, item)"
											>
												{{ __("Select PO") }}
											</button>
										</template>
										<template v-else>
											<span style="color: #ccc; font-size: 11px">
												{{ __("No PO") }}
											</span>
											<button
												v-if="
													item.match_status === 'matched' &&
													!isLocked(invoice)
												"
												class="btn btn-xs btn-default"
												style="
													font-size: 10px;
													padding: 1px 6px;
													margin-left: 2px;
												"
												@click.stop="promptSelectPO(invoice, item)"
												:disabled="
													invoice.supplier_match_status === 'unmatched'
												"
											>
												<i class="fa fa-link"></i>
											</button>
										</template>
									</span>

									<!-- PR -->
									<span
										style="
											display: flex;
											align-items: center;
											gap: 4px;
											font-size: 11px;
										"
									>
										<i
											:class="poStatusIcon(item.pr_match_status).icon"
											:style="`color: ${
												poStatusIcon(item.pr_match_status).color
											}; font-size: 11px`"
										></i>
										<template
											v-if="
												item.pr_match_status === 'matched' ||
												item.pr_match_status === 'partial'
											"
										>
											<a
												:href="`/app/purchase-receipt/${item.purchase_receipt}`"
												target="_blank"
												style="color: #666; font-size: 11px"
											>
												{{ item.purchase_receipt }}
											</a>
											<span
												v-if="item.pr_match_status === 'partial'"
												style="color: #5bc0de; font-size: 10px"
												:title="__('Quantity differs from PR line')"
											>
												{{ __("Partial") }}
											</span>
											<i
												v-if="!isLocked(invoice)"
												class="fa fa-times"
												style="
													color: #ccc;
													cursor: pointer;
													font-size: 10px;
												"
												@click.stop="unlinkItemPR(invoice, item)"
											></i>
										</template>
										<template v-else-if="item.pr_match_status === 'ambiguous'">
											<template v-if="invoice.purchase_receipt">
												<a
													:href="`/app/purchase-receipt/${invoice.purchase_receipt}`"
													target="_blank"
													style="color: #666; font-size: 11px"
												>
													{{ invoice.purchase_receipt }}
												</a>
												<span style="color: #aaa; font-size: 10px">{{
													__("(header)")
												}}</span>
											</template>
											<button
												v-else-if="!isLocked(invoice)"
												class="btn btn-xs btn-warning"
												style="font-size: 10px; padding: 1px 6px"
												@click.stop="promptSelectPR(invoice, item)"
											>
												{{ __("Select PR") }}
											</button>
										</template>
										<template v-else>
											<span style="color: #ccc; font-size: 11px">
												{{ __("No PR") }}
											</span>
											<button
												v-if="
													item.match_status === 'matched' &&
													!isLocked(invoice)
												"
												class="btn btn-xs btn-default"
												style="
													font-size: 10px;
													padding: 1px 6px;
													margin-left: 2px;
												"
												@click.stop="promptSelectPR(invoice, item)"
												:disabled="
													invoice.supplier_match_status === 'unmatched'
												"
											>
												<i class="fa fa-link"></i>
											</button>
										</template>
									</span>
								</div>
							</div>
							<div style="display: flex; align-items: center; gap: 8px">
								<span
									:class="`indicator-pill ${
										{ unmatched: 'red', matched: 'green', created: 'blue' }[
											item.match_status
										] || 'grey'
									}`"
									style="font-size: 11px"
								>
									{{ __(item.match_status) }}
								</span>
								<template v-if="item.match_status !== 'unmatched'">
									<a
										:href="`/app/item/${item.matched_item}`"
										target="_blank"
										style="font-size: 12px"
									>
										{{ item.matched_item }}
									</a>
									<span
										v-if="!isLocked(invoice)"
										@click="confirmDeleteMatchedItem(invoice, item)"
										style="cursor: pointer"
									>
										<i
											class="fa fa-times"
											style="color: #c11d1d"
											aria-hidden="true"
										></i
									></span>
								</template>
								<template v-else>
									<button
										v-if="!isLocked(invoice)"
										:disabled="!supplierReady(invoice)"
										class="btn btn-xs btn-default"
										@click="rematchItems(invoice)"
										:title="
											!supplierReady(invoice)
												? __('Match a supplier first')
												: ''
										"
									>
										<i class="fa fa-refresh"></i>
									</button>
									<span
										v-if="!isLocked(invoice)"
										:title="
											!supplierReady(invoice)
												? __('Match a supplier first')
												: ''
										"
										style="display: inline-block"
									>
										<button
											v-if="!isLocked(invoice)"
											:disabled="!supplierReady(invoice)"
											class="btn btn-xs btn-default"
											@click="promptMatchItem(invoice, item)"
										>
											<i class="fa fa-link"></i> {{ __("Match") }}
										</button>
									</span>
									<span
										v-if="!isLocked(invoice)"
										:title="
											!supplierReady(invoice)
												? __('Match a supplier first')
												: ''
										"
										style="display: inline-block"
									>
										<button
											:disabled="!supplierReady(invoice)"
											class="btn btn-xs btn-default"
											@click="createItem(invoice, item)"
										>
											<i class="fa fa-plus"></i> {{ __("Create") }}
										</button>
									</span>
								</template>
							</div>
						</div>
					</div>
				</div>

				<!-- Footer: pending ou ready -->
				<div
					v-if="['pending', 'ready'].includes(invoice.conversion_status)"
					style="
						padding: 10px 16px;
						border-top: 1px solid #f0f0f0;
						display: flex;
						flex-direction: column;
						gap: 8px;
					"
				>
					<div
						v-if="invoice.is_credit_note && creditNoteBlockReason(invoice)"
						style="color: #888; font-size: 12px"
					>
						<i class="fa fa-exclamation-triangle" style="color: #f0ad4e"></i>
						{{ creditNoteBlockReason(invoice) }}
					</div>
					<div
						style="display: flex; justify-content: space-between; align-items: center"
					>
						<button
							v-if="
								!(
									invoice.is_credit_note &&
									creditNoteBlockReason(invoice) &&
									invoice.ref_status !== 'refused'
								)
							"
							class="btn btn-sm btn-danger"
							@click="promptRefuse(invoice)"
						>
							<i class="fa fa-ban"></i> {{ __("Refuse") }}
						</button>
						<div>
							<span
								v-if="
									!canConvert(invoice) && invoice.conversion_status === 'ready'
								"
								style="color: #888; font-size: 12px; margin-right: 8px"
							>
								<i class="fa fa-exclamation-triangle"></i>
								{{
									buyingSettings.po_required &&
									!invoice.purchase_order &&
									!invoice.items?.some((i) => i.purchase_order)
										? __("Purchase Order required")
										: __("Purchase Receipt required")
								}}
							</span>
							<button
								v-if="canConvert(invoice)"
								class="btn btn-sm btn-primary"
								@click="convertToPI(invoice)"
							>
								{{ __("Convert to Purchase Invoice") }}
								<i class="fa fa-arrow-circle-o-right"></i>
							</button>
						</div>
					</div>
				</div>

				<!-- Footer: converted -->
				<div
					v-if="invoice.conversion_status === 'converted'"
					style="padding: 10px 16px; border-top: 1px solid #f0f0f0; text-align: right"
				>
					<a
						v-if="invoice.purchase_invoice"
						:href="`/app/purchase-invoice/${invoice.purchase_invoice}`"
						target="_blank"
						class="btn btn-xs btn-default"
					>
						<i class="fa fa-file-text-o"></i> {{ invoice.purchase_invoice }}
					</a>
					<button
						v-if="invoice.last_lifecycle_log?.status_code === '204'"
						class="btn btn-xs btn-danger ml-1"
						@click="cancelConversion(invoice)"
					>
						<i class="fa fa-undo"></i> {{ __("Reset") }}
					</button>
				</div>

				<!-- Footer: refused -->
				<div
					v-if="invoice.conversion_status === 'refused'"
					style="padding: 10px 16px; border-top: 1px solid #f0f0f0; text-align: right"
				>
					<span class="indicator-pill red">{{ __("Refused") }}</span>
				</div>
			</div>
		</TransitionGroup>
	</div>
</template>
<style>
.invoice-fade-move,
.invoice-fade-enter-active,
.invoice-fade-leave-active {
	transition: all 1s ease;
}

.invoice-fade-enter-from,
.invoice-fade-leave-to {
	opacity: 0;
	transform: translateX(3000px);
}

.invoice-fade-leave-active {
	position: absolute;
	width: calc(100% - 32px);
}
</style>
