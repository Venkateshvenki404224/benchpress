// A Database Server is the MariaDB container behind one or more benches.
frappe.listview_settings["Database Server"] = {
	get_indicator(doc) {
		const colors = {
			Pending: "orange",
			Active: "green",
			Stopped: "gray",
			Error: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
