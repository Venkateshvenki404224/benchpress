// Copyright (c) 2026, Venkatesh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lab", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(
				__("Build Image"),
				function () {
					frappe.confirm(
						__(
							"This will build a Docker image for this lab. It may take 5-10 minutes. Proceed?"
						),
						function () {
							frm.set_value("status", "Building");
							frm.save();
							frappe.call({
								method: "benchpress.api.build_lab_image",
								args: { lab_name: frm.doc.name },
								callback: function (r) {
									frappe.show_alert({
										message: __(
											"Image build started. Check Build Log in the sidebar."
										),
										indicator: "blue",
									});
									// Wait a moment for the Build Log to be created, then reload to show link
									setTimeout(function () {
										frm.reload_doc();
									}, 2000);
								},
							});
						}
					);
				},
				__("Actions")
			);
		}

		frm.trigger("show_latest_build_status");
	},

	show_latest_build_status(frm) {
		if (frm.is_new()) return;

		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Build Log",
				filters: { lab: frm.doc.name },
				fields: ["name", "log_type", "creation"],
				order_by: "creation desc",
				limit_page_length: 1,
			},
			callback: function (r) {
				if (!r.message || r.message.length === 0) return;

				let log = r.message[0];
				let color =
					log.log_type === "success"
						? "green"
						: log.log_type === "error"
						? "red"
						: "orange";
				let label =
					log.log_type === "success"
						? "Build Passed"
						: log.log_type === "error"
						? "Build Failed"
						: "Building...";

				if (frm.fields_dict.build_log_html) {
					frm.fields_dict.build_log_html.$wrapper.html(
						'<div style="padding: 12px;">' +
							'<a href="/app/build-log/' +
							log.name +
							'" style="color: var(--text-color); text-decoration: none;">' +
							'<div style="display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: var(--subtle-fg); border: 1px solid var(--border-color); border-radius: 8px;">' +
							'<span class="indicator-pill ' +
							color +
							'">' +
							label +
							"</span>" +
							'<span style="color: var(--text-muted); font-size: 12px;">Latest build — ' +
							frappe.datetime.prettyDate(log.creation) +
							"</span>" +
							'<span style="margin-left: auto; color: var(--text-muted);">→</span>' +
							"</div></a></div>"
					);
				}
			},
		});
	},
});
