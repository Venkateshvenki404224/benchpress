// Closing a message is the whole admin workflow for /contact, and it happens in batches after a
// reply run — so it is a bulk action on the list, matching the waitlist.
frappe.listview_settings["Contact Message"] = {
	get_indicator(doc) {
		const colors = { New: "orange", Answered: "green", Spam: "gray" };
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},

	onload(listview) {
		listview.page.add_actions_menu_item(__("Mark answered"), () =>
			mark_answered(listview)
		);
	},
};

async function mark_answered(listview) {
	const messages = listview.get_checked_items(true);
	if (!messages.length) {
		frappe.msgprint(__("Select at least one message."));
		return;
	}

	const response = await frappe.call({
		method: "benchpress.contact.mark_answered",
		args: { messages },
		freeze: true,
		freeze_message: __("Closing…"),
	});

	frappe.show_alert({
		message: __("{0} marked answered", [response.message.answered]),
		indicator: "green",
	});
	listview.refresh();
}
