// Copyright (c) 2026, Venkatesh and contributors
// For license information, please see license.txt

// The operator's two ways into the ledger. Both are document actions rather than a writable
// ledger form because only `benchpress.credits.account` may move a balance — a row typed straight
// into Credit Ledger Entry would explain a balance it never changed, and the DocType refuses it.
//
// Both prompts make the reason mandatory. An adjustment is the one entry type no rule produced,
// so a year later the reason is the only record of why the balance is what it is.

frappe.ui.form.on("Credit Account", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Post Adjustment"), () => post_adjustment(frm), __("Credits"));
		frm.add_custom_button(__("Refund an Order"), () => post_refund(frm), __("Credits"));
	},
});

function post_adjustment(frm) {
	frappe.prompt(
		[
			{
				fieldname: "credits",
				fieldtype: "Float",
				label: __("Credits"),
				reqd: 1,
				description: __("Negative takes credits away."),
			},
			{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
		],
		(values) => run(frm, "post_adjustment", values),
		__("Post Adjustment"),
		__("Post")
	);
}

function post_refund(frm) {
	frappe.prompt(
		[
			{
				fieldname: "order",
				fieldtype: "Link",
				options: "Razorpay Order",
				label: __("Razorpay Order"),
				reqd: 1,
				description: __("The order this refunds. The money itself is moved in Razorpay."),
			},
			{
				fieldname: "credits",
				fieldtype: "Float",
				label: __("Credits to take back"),
				reqd: 1,
			},
			{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
		],
		(values) => run(frm, "post_refund", values),
		__("Refund an Order"),
		__("Refund")
	);
}

async function run(frm, method, args) {
	await frm.call(method, args);
	frm.reload_doc();
}
