// A Bench Instance is a live container; its status tracks the container lifecycle.
frappe.listview_settings["Bench Instance"] = {
	get_indicator(doc) {
		const colors = {
			Draft: "gray",
			Deploying: "blue",
			Running: "green",
			Stopped: "gray",
			Error: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
