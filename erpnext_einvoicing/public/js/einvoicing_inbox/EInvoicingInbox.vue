<script setup>
import { ref, computed, onMounted } from "vue";

// Helper pour traduction
function __(text, replace) {
	if (window.__) {
		return window.__(text, replace);
	}
	return text;
}

/*** State ***/

const invoices = ref([]);
const loading = ref(false);
const syncing = ref(false);
const filter = ref("pending");
const expanded = ref(new Set());

/*** Computed ***/

const filtered = computed(() => {
	if (filter.value === "all") return invoices.value;
	return invoices.value.filter((inv) => inv.conversion_status === filter.value);
});

const counts = computed(() => ({
	pending: invoices.value.filter((i) => i.conversion_status === "pending").length,
	ready: invoices.value.filter((i) => i.conversion_status === "ready").length,
	converted: invoices.value.filter((i) => i.conversion_status === "converted").length,
}));

/*** API ***/

async function fetchInvoices() {
	loading.value = true;
	try {
		const res = await frappe.call({
			method: "erpnext_einvoicing.providers.sync.get_einvoicing_inbox",
		});
		invoices.value = res.message || [];
	} finally {
		loading.value = false;
	}
}

async function syncFlows() {
	syncing.value = true;
	try {
		const r = await frappe.call({
			method: "erpnext_einvoicing.providers.sync.sync_flows",
			args: { sync_type: "Purchase Invoice" },
		});
		const msg = r.message || {};
		const indicator = msg.status === "ok" ? "green" : "orange";
		frappe.show_alert({ message: msg.message || __("Sync complete"), indicator }, 5);
		await fetchInvoices();
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
			await frappe.call({
				method: "erpnext_einvoicing.providers.sync.match_supplier",
				args: { name: invoice.name, matched_supplier: values.matched_supplier },
			});
			await fetchInvoices();
		},
		__("Match Supplier"),
		__("Confirm")
	);
}

function confirmDeleteMatchedSupplier(invoice) {
	frappe.confirm(
		"Are you sure you want to unlink supplier?",
		async () => {
			await frappe.call({
				method: "erpnext_einvoicing.providers.sync.unlink_matched_supplier",
				args: { name: invoice.name },
			});
			await fetchInvoices();
		},
		() => {
			// action to perform if No is selected
		}
	);
}

async function createSupplierFromSiret(invoice) {
	const r = await frappe.call({
		method: "erpnext_einvoicing.providers.sync.create_supplier_from_siret",
		args: { name: invoice.name },
		freeze: true,
		freeze_message: __("Looking up SIRET..."),
	});
	const msg = r.message || {};
	if (msg.status === "ok") {
		frappe.show_alert(
			{ message: __("Supplier created: {0}", [msg.supplier]), indicator: "green" },
			4
		);
		await fetchInvoices();
	} else {
		frappe.msgprint({
			title: __("Error"),
			message: msg.error || __("Failed"),
			indicator: "red",
		});
	}
}

function promptLinkPO(invoice) {
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
						status: ["in", ["To Bill", "Partially Billed"]],
					},
				}),
			},
		],
		async (values) => {
			await frappe.call({
				method: "erpnext_einvoicing.providers.sync.link_purchase_order",
				args: { name: invoice.name, purchase_order: values.purchase_order },
			});
			await fetchInvoices();
		},
		__("Link Purchase Order"),
		__("Confirm")
	);
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
			await fetchInvoices();
		},
		__("Link Purchase Receipt"),
		__("Confirm")
	);
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
			},
		],
		async (values) => {
			await frappe.call({
				method: "erpnext_einvoicing.providers.sync.match_item",
				args: {
					name: invoice.name,
					item_idx: item.idx,
					matched_item: values.matched_item,
				},
			});
			await fetchInvoices();
		},
		__("Match Item: {0}", [item.item_description_raw]),
		__("Confirm")
	);
}

function confirmDeleteMatchedItem(invoice, item) {
	frappe.confirm(
		"Are you sure you want to unlink item?",
		async () => {
			await frappe.call({
				method: "erpnext_einvoicing.providers.sync.unlink_matched_item",
				args: {
					name: invoice.name,
					item_idx: item.idx,
				},
			});
			await fetchInvoices();
		},
		() => {
			// action to perform if No is selected
		}
	);
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
				await fetchInvoices();
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
	if (invoice.conversion_status !== "ready") return false;
	if (buyingSettings.value.po_required && !invoice.purchase_order) return false;
	if (buyingSettings.value.pr_required && !invoice.purchase_receipt) return false;
	return true;
}

async function convertToPI(invoice) {
	frappe.confirm(__("Convert {0} to a Purchase Invoice draft?", [invoice.name]), async () => {
		const r = await frappe.call({
			method: "frappe.client.run_doc_method",
			args: {
				dt: "ePurchase Invoice",
				dn: invoice.name,
				method: "convert_to_purchase_invoice",
			},
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
			await fetchInvoices();
		}
	});
}

/*** UI helpers ***/

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

/*** Lifecycle ***/
const buyingSettings = ref({ po_required: false, pr_required: false });
onMounted(async () => {
	const r = await frappe.call({
		method: "erpnext_einvoicing.providers.sync.get_buying_settings",
	});
	buyingSettings.value = r.message || {};
	await fetchInvoices();
});
</script>

<template>
	<div class="einvoicing-inbox" style="padding: 16px">
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
					v-for="tab in ['all', 'pending', 'ready', 'converted']"
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
			<button class="btn btn-sm btn-default" :disabled="syncing" @click="syncFlows">
				<i :class="['fa', syncing ? 'fa-spinner fa-spin' : 'fa-refresh']"></i>
				{{ __("Sync") }}
			</button>
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
		<div v-else>
			<div
				v-for="invoice in filtered"
				:key="invoice.name"
				style="
					border: 1px solid #d1d8dd;
					border-radius: 6px;
					margin-bottom: 12px;
					background: #fff;
				"
			>
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
							:class="`indicator-pill ${
								{ pending: 'orange', ready: 'green', converted: 'blue' }[
									invoice.conversion_status
								] || 'grey'
							}`"
						>
							{{ invoice.conversion_status }}
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
							:class="`indicator-pill ${
								{ unmatched: 'red', matched: 'green', created: 'blue' }[
									invoice.supplier_match_status
								] || 'grey'
							}`"
							style="font-size: 11px"
						>
							{{ invoice.supplier_match_status }}
						</span>

						<template v-if="invoice.supplier_match_status !== 'unmatched'">
							<span style="color: #888"
								><i class="fa fa-arrow-circle-o-right" aria-hidden="true"></i
							></span>
							<a
								:href="`/app/supplier/${invoice.matched_supplier}`"
								target="_blank"
								>{{ invoice.matched_supplier }}</a
							>
							<span
								@click="confirmDeleteMatchedSupplier(invoice)"
								style="cursor: pointer"
								><i
									class="fa fa-times"
									style="color: #c11d1d"
									aria-hidden="true"
								></i
							></span>
						</template>
						<template v-else>
							<button
								class="btn btn-xs btn-default"
								@click="promptMatchSupplier(invoice)"
							>
								<i class="fa fa-link"></i> {{ __("Match") }}
							</button>
							<button
								v-if="invoice.supplier_siret"
								class="btn btn-xs btn-default"
								@click="createSupplierFromSiret(invoice)"
							>
								<i class="fa fa-search"></i> {{ __("SIRENE") }}
							</button>
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
								<span @click="unlinkPO(invoice)" style="cursor: pointer">
									<i class="fa fa-times" style="color: #c11d1d"></i>
								</span>
							</template>
							<button
								v-else
								class="btn btn-xs btn-default"
								@click="promptLinkPO(invoice)"
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
								<span @click="unlinkPR(invoice)" style="cursor: pointer">
									<i class="fa fa-times" style="color: #c11d1d"></i>
								</span>
							</template>
							<button
								v-else
								class="btn btn-xs btn-warning"
								@click="promptLinkPR(invoice)"
							>
								<i class="fa fa-link"></i> {{ __("Link Receipt") }}
							</button>
						</template>
					</div>
				</div>

				<!-- Items section -->
				<div style="padding: 0">
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
								<span style="font-weight: 500">{{
									item.item_description_raw
								}}</span>
								<span
									v-if="item.item_ref_raw"
									style="color: #888; margin-left: 8px; font-size: 12px"
								>
									{{ item.item_ref_raw }}
								</span>
								<span style="color: #666; margin-left: 8px; font-size: 12px">
									{{ item.qty }} ×
									{{ formatCurrency(item.unit_price, invoice.currency) }}
								</span>
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
									{{ item.match_status }}
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
										@click="confirmDeleteMatchedItem(invoice, item)"
										style="cursor: pointer"
										><i
											class="fa fa-times"
											style="color: #c11d1d"
											aria-hidden="true"
										></i
									></span>
								</template>
								<template v-else>
									<button
										class="btn btn-xs btn-default"
										@click="promptMatchItem(invoice, item)"
									>
										<i class="fa fa-link"></i> {{ __("Match") }}
									</button>
									<button
										class="btn btn-xs btn-default"
										@click="createItem(invoice, item)"
									>
										<i class="fa fa-plus"></i> {{ __("Create") }}
									</button>
								</template>
							</div>
						</div>
					</div>
				</div>

				<!-- Card footer -->
				<div
					v-if="canConvert(invoice)"
					style="padding: 10px 16px; border-top: 1px solid #f0f0f0; text-align: right"
				>
					<button class="btn btn-sm btn-primary" @click="convertToPI(invoice)">
						{{ __("Convert to Purchase Invoice") }}
						<i class="fa fa-arrow-circle-o-right"></i>
					</button>
				</div>
				<div
					v-else-if="invoice.conversion_status === 'ready'"
					style="
						padding: 10px 16px;
						border-top: 1px solid #f0f0f0;
						text-align: right;
						color: #888;
						font-size: 12px;
					"
				>
					<i class="fa fa-exclamation-triangle"></i>
					{{
						buyingSettings.pr_required && !invoice.purchase_receipt
							? __("Purchase Receipt required")
							: __("Purchase Order required")
					}}
				</div>
			</div>
		</div>
	</div>
</template>
