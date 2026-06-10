// Copyright (c) 2026, Venkatesh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Build Log", {
	refresh(frm) {
		frm.trigger("render_log");
		frm.trigger("setup_realtime");

		frm.page.set_indicator(
			frm.doc.log_type === "success"
				? "Build Passed"
				: frm.doc.log_type === "error"
				? "Build Failed"
				: "Building...",
			frm.doc.log_type === "success"
				? "green"
				: frm.doc.log_type === "error"
				? "red"
				: "orange"
		);
	},

	render_log(frm) {
		let raw = frm.doc.message || "";
		let lines = raw.split("\n");
		let step_count = 0;

		let html_lines = lines
			.map(function (line) {
				if (!line.trim()) return "";

				let is_step = line.match(/^Step (\d+)\/(\d+)/);
				let is_success = line.includes("=== Build complete");
				let is_error = line.includes("=== Build failed") || line.startsWith("ERROR");
				let is_cached = line.includes("Using cache");
				let is_arrow = line.startsWith("--->");
				let is_header = line.startsWith("===");

				if (is_step) {
					step_count++;
					let [, current, total] = is_step;
					return (
						'<div style="margin-top: 12px; padding: 8px 12px; background: var(--subtle-fg); border-left: 3px solid var(--blue-500); border-radius: 0 6px 6px 0; font-weight: 600; color: var(--blue-400); font-size: 13px;">' +
						'<span style="color: var(--text-muted); margin-right: 8px;">' +
						current +
						"/" +
						total +
						"</span>" +
						frappe.utils.escape_html(line.replace(/^Step \d+\/\d+ : /, "")) +
						"</div>"
					);
				}

				if (is_success) {
					return (
						'<div style="margin-top: 16px; padding: 12px 16px; background: var(--bg-green); border: 1px solid var(--green-600); border-radius: 6px; color: var(--green-500); font-weight: 600; font-size: 13px;">' +
						'<span style="margin-right: 8px;">✓</span>' +
						frappe.utils.escape_html(line) +
						"</div>"
					);
				}

				if (is_error) {
					return (
						'<div style="margin-top: 16px; padding: 12px 16px; background: var(--bg-red); border: 1px solid var(--red-600); border-radius: 6px; color: var(--red-500); font-weight: 600; font-size: 13px;">' +
						'<span style="margin-right: 8px;">✗</span>' +
						frappe.utils.escape_html(line) +
						"</div>"
					);
				}

				if (is_header) {
					return (
						'<div style="padding: 6px 12px; color: var(--purple-400); font-weight: 600; font-size: 13px;">' +
						frappe.utils.escape_html(line) +
						"</div>"
					);
				}

				if (is_cached) {
					return (
						'<div style="padding: 2px 12px 2px 24px; color: var(--green-500); font-size: 12px;">' +
						'<span style="margin-right: 6px;">●</span>cached</div>'
					);
				}

				if (is_arrow) {
					return (
						'<div style="padding: 2px 12px 2px 24px; color: var(--text-muted); font-size: 12px;">' +
						frappe.utils.escape_html(line) +
						"</div>"
					);
				}

				let color = "var(--text-color)";
				return (
					'<div style="padding: 2px 12px 2px 24px; color: ' +
					color +
					'; font-size: 12px; white-space: pre-wrap;">' +
					frappe.utils.escape_html(line) +
					"</div>"
				);
			})
			.join("");

		let make_status_bar = function (bg, border, icon_html, label, label_color) {
			return (
				'<div style="padding: 10px 16px; background: ' +
				bg +
				"; border-bottom: 1px solid " +
				border +
				'; border-radius: 6px 6px 0 0; display: flex; align-items: center; gap: 8px;">' +
				icon_html +
				'<span style="color: ' +
				label_color +
				'; font-weight: 600; font-size: 13px;">' +
				label +
				"</span>" +
				'<span style="color: var(--text-muted); font-size: 12px; margin-left: auto;">' +
				(frm.doc.lab || "") +
				"</span>" +
				"</div>"
			);
		};

		let status_bar = "";
		if (frm.doc.log_type === "info") {
			status_bar = make_status_bar(
				"var(--subtle-fg)",
				"var(--border-color)",
				'<div style="width: 10px; height: 10px; border-radius: 50%; background: var(--yellow-500); animation: pulse 1.5s infinite;"></div>',
				"Building...",
				"var(--yellow-500)"
			);
		} else if (frm.doc.log_type === "success") {
			status_bar = make_status_bar(
				"var(--bg-green)",
				"var(--green-600)",
				'<span style="color: var(--green-500); font-size: 16px;">✓</span>',
				"Build succeeded",
				"var(--green-500)"
			);
		} else if (frm.doc.log_type === "error") {
			status_bar = make_status_bar(
				"var(--bg-red)",
				"var(--red-600)",
				'<span style="color: var(--red-500); font-size: 16px;">✗</span>',
				"Build failed",
				"var(--red-500)"
			);
		}

		let container =
			"<style>@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }</style>" +
			"<div style=\"background: var(--bg-color); border: 1px solid var(--border-color); border-radius: 6px; font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace; margin-top: 8px;\">" +
			status_bar +
			'<div id="build-log-output" style="padding: 12px 0; max-height: 600px; overflow-y: auto;">' +
			html_lines +
			"</div></div>";

		if (frm.fields_dict.log_html) {
			frm.fields_dict.log_html.$wrapper.html(container);
			let output = document.getElementById("build-log-output");
			if (output) output.scrollTop = output.scrollHeight;
		}
	},

	setup_realtime(frm) {
		if (frm._realtime_setup) return;
		frm._realtime_setup = true;

		frappe.realtime.on("lab_build_log", function (data) {
			if (data.build_log !== frm.doc.name) return;

			frm.doc.message = (frm.doc.message || "") + data.log + "\n";
			frm.trigger("render_log");

			if (data.type === "success" || data.type === "error") {
				frm.reload_doc();
			}
		});
	},
});
