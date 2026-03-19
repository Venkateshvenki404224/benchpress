// Copyright (c) 2026, Venkatesh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bench Instance", {
	refresh(frm) {
		if (frm.doc.wg_config && frm.doc.status === "Running") {
			frm.add_custom_button(__("Download VPN Config"), () => {
				const blob = new Blob([frm.doc.wg_config], { type: "text/plain" });
				const url = URL.createObjectURL(blob);
				const a = document.createElement("a");
				a.href = url;
				a.download = `${frm.doc.bench_name || frm.doc.name}.conf`;
				a.click();
				URL.revokeObjectURL(url);
			}, __("VPN"));

			frm.add_custom_button(__("Copy VPN Config"), () => {
				navigator.clipboard.writeText(frm.doc.wg_config).then(() => {
					frappe.show_alert({
						message: __("WireGuard config copied to clipboard"),
						indicator: "green",
					});
				});
			}, __("VPN"));
		}
	},
});
