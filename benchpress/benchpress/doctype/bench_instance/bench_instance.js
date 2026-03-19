// Copyright (c) 2026, Venkatesh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bench Instance", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.status === "Draft" || frm.doc.status === "Error") {
			frm.add_custom_button(__("Deploy"), () => {
				frappe.confirm(
					__("This will create a container and set up a Frappe bench. Continue?"),
					() => {
						frm.call("enqueue_deploy");
					}
				);
			}, __("Actions"));
		}

		if (frm.doc.status === "Running") {
			frm.add_custom_button(__("Stop"), () => {
				frm.call("enqueue_stop");
			}, __("Actions"));
		}

		if (frm.doc.status === "Running" || frm.doc.status === "Error") {
			frm.add_custom_button(__("Redeploy"), () => {
				frappe.confirm(
					__("This will destroy the current container and redeploy from scratch. Continue?"),
					() => {
						frm.call("enqueue_redeploy");
					}
				);
			}, __("Actions"));
		}

		if (frm.doc.status === "Stopped") {
			frm.add_custom_button(__("Start"), () => {
				frm.call("enqueue_start");
			}, __("Actions"));
		}

		// Realtime deploy log listener
		frappe.realtime.on("bench_deploy_log", (data) => {
			if (data.bench === frm.doc.name) {
				frm.reload_doc();
			}
		});
	},
});
