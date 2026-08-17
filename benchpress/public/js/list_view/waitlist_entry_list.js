// Approval is the whole admin workflow for the waitlist, so it lives on the list view as a
// bulk action rather than on the form — invites go out in batches, not one at a time.
frappe.listview_settings["Waitlist Entry"] = {
	get_indicator(doc) {
		const colors = { Pending: "orange", Approved: "green", Rejected: "gray" };
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},

	onload(listview) {
		listview.page.add_actions_menu_item(__("Approve and invite"), () =>
			approve_selected(listview)
		);
	},
};

async function approve_selected(listview) {
	const entries = listview.get_checked_items(true);
	if (!entries.length) {
		frappe.msgprint(__("Select at least one entry."));
		return;
	}

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
