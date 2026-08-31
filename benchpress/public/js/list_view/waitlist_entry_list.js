// `waitlist.reject` is the only path that mails a decline; flipping `status` in the form
// deliberately mails nobody.
frappe.listview_settings["Waitlist Entry"] = {
	get_indicator(doc) {
		const colors = { Pending: "orange", Approved: "green", Rejected: "gray" };
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},

	onload(listview) {
		listview.page.add_actions_menu_item(__("Approve and invite"), () =>
			approve_selected(listview)
		);
		listview.page.add_actions_menu_item(__("Decline"), () => decline_selected(listview));
	},
};

async function approve_selected(listview) {
	const entries = checked(listview);
	if (!entries) return;

	const response = await frappe.call({
		method: "benchpress.waitlist.approve",
		args: { entries },
		freeze: true,
		freeze_message: __("Inviting…"),
	});

	frappe.show_alert({
		message: __("{0} invited", [response.message.approved]),
		indicator: "green",
	});
	listview.refresh();
}

function decline_selected(listview) {
	const entries = checked(listview);
	if (!entries) return;

	frappe.prompt(
		{
			fieldname: "reason",
			fieldtype: "Small Text",
			label: __("Reason (sent to them, optional)"),
		},
		async ({ reason }) => {
			const response = await frappe.call({
				method: "benchpress.waitlist.reject",
				args: { entries, reason },
				freeze: true,
				freeze_message: __("Declining…"),
			});

			frappe.show_alert({
				message: __("{0} declined", [response.message.rejected]),
				indicator: "orange",
			});
			listview.refresh();
		},
		__("Decline {0} request(s)", [entries.length]),
		__("Send decline")
	);
}

function checked(listview) {
	const entries = listview.get_checked_items(true);
	if (!entries.length) {
		frappe.msgprint(__("Select at least one entry."));
		return null;
	}
	return entries;
}
