// Copyright (c) 2026, Venkatesh and contributors
// For license information, please see license.txt

frappe.ui.form.on("BenchPress Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Setup WireGuard"), () => {
			frappe.call({
				method: "benchpress.wg_manager.setup_wg_server",
				freeze: true,
				freeze_message: __("Setting up WireGuard server..."),
				callback(r) {
					if (r.message) {
						frappe.msgprint({
							title: __("WireGuard Server Active"),
							message: __("Public Key: {0}", [r.message.public_key]),
							indicator: "green",
						});
						frm.reload_doc();
					}
				},
			});
		});
	},
});
