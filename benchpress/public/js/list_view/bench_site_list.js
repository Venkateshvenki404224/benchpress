// A Bench Site lives inside a bench; its status tracks site creation and availability.
frappe.listview_settings["Bench Site"] = {
	get_indicator(doc) {
		const colors = {
			Creating: "blue",
			Active: "green",
			Inactive: "gray",
			Error: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
