// A Lab is a blueprint that gets built into an image; its status tracks that build.
frappe.listview_settings["Lab"] = {
	get_indicator(doc) {
		const colors = {
			Draft: "gray",
			Building: "blue",
			Ready: "green",
			Error: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
