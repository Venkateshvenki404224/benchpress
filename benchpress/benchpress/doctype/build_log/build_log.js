// Copyright (c) 2026, Venkatesh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Build Log", {
	refresh(frm) {
		frm.trigger("render_log");
		frm.trigger("setup_realtime");

		frm.page.set_indicator(
			frm.doc.log_type === "success" ? "Build Passed" :
			frm.doc.log_type === "error" ? "Build Failed" :
			"Building...",
			frm.doc.log_type === "success" ? "green" :
			frm.doc.log_type === "error" ? "red" : "orange"
		);
	},

	render_log(frm) {
		let raw = frm.doc.message || "";
		let lines = raw.split("\n");
		let step_count = 0;

		let html_lines = lines.map(function(line) {
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
				return '<div style="margin-top: 12px; padding: 8px 12px; background: #161b22; border-left: 3px solid #3b82f6; border-radius: 0 6px 6px 0; font-weight: 600; color: #58a6ff; font-size: 13px;">'
					+ '<span style="color: #8b949e; margin-right: 8px;">' + current + '/' + total + '</span>'
					+ frappe.utils.escape_html(line.replace(/^Step \d+\/\d+ : /, ''))
					+ '</div>';
			}

			if (is_success) {
				return '<div style="margin-top: 16px; padding: 12px 16px; background: #0d1f0d; border: 1px solid #238636; border-radius: 6px; color: #3fb950; font-weight: 600; font-size: 13px;">'
					+ '<span style="margin-right: 8px;">✓</span>'
					+ frappe.utils.escape_html(line)
					+ '</div>';
			}

			if (is_error) {
				return '<div style="margin-top: 16px; padding: 12px 16px; background: #2d0a0a; border: 1px solid #da3633; border-radius: 6px; color: #f85149; font-weight: 600; font-size: 13px;">'
					+ '<span style="margin-right: 8px;">✗</span>'
					+ frappe.utils.escape_html(line)
					+ '</div>';
			}

			if (is_header) {
				return '<div style="padding: 6px 12px; color: #d2a8ff; font-weight: 600; font-size: 13px;">'
					+ frappe.utils.escape_html(line) + '</div>';
			}

			if (is_cached) {
				return '<div style="padding: 2px 12px 2px 24px; color: #3fb950; font-size: 12px;">'
					+ '<span style="margin-right: 6px;">●</span>cached</div>';
			}

			if (is_arrow) {
				return '<div style="padding: 2px 12px 2px 24px; color: #8b949e; font-size: 12px;">'
					+ frappe.utils.escape_html(line) + '</div>';
			}

			let color = "#c9d1d9";
			return '<div style="padding: 2px 12px 2px 24px; color: ' + color + '; font-size: 12px; white-space: pre-wrap;">'
				+ frappe.utils.escape_html(line) + '</div>';
		}).join("");

		let status_bar = '';
		if (frm.doc.log_type === "info") {
			status_bar = '<div style="padding: 10px 16px; background: #161b22; border-bottom: 1px solid #30363d; border-radius: 6px 6px 0 0; display: flex; align-items: center; gap: 8px;">'
				+ '<div style="width: 10px; height: 10px; border-radius: 50%; background: #d29922; animation: pulse 1.5s infinite;"></div>'
				+ '<span style="color: #d29922; font-weight: 600; font-size: 13px;">Building...</span>'
				+ '<span style="color: #8b949e; font-size: 12px; margin-left: auto;">' + (frm.doc.lab || '') + '</span>'
				+ '</div>';
		} else if (frm.doc.log_type === "success") {
			status_bar = '<div style="padding: 10px 16px; background: #0d1f0d; border-bottom: 1px solid #238636; border-radius: 6px 6px 0 0; display: flex; align-items: center; gap: 8px;">'
				+ '<span style="color: #3fb950; font-size: 16px;">✓</span>'
				+ '<span style="color: #3fb950; font-weight: 600; font-size: 13px;">Build succeeded</span>'
				+ '<span style="color: #8b949e; font-size: 12px; margin-left: auto;">' + (frm.doc.lab || '') + '</span>'
				+ '</div>';
		} else if (frm.doc.log_type === "error") {
			status_bar = '<div style="padding: 10px 16px; background: #2d0a0a; border-bottom: 1px solid #da3633; border-radius: 6px 6px 0 0; display: flex; align-items: center; gap: 8px;">'
				+ '<span style="color: #f85149; font-size: 16px;">✗</span>'
				+ '<span style="color: #f85149; font-weight: 600; font-size: 13px;">Build failed</span>'
				+ '<span style="color: #8b949e; font-size: 12px; margin-left: auto;">' + (frm.doc.lab || '') + '</span>'
				+ '</div>';
		}

		let container = '<style>@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }</style>'
			+ '<div style="background: #0d1117; border: 1px solid #30363d; border-radius: 6px; font-family: ui-monospace, SFMono-Regular, \'SF Mono\', Menlo, Consolas, monospace; margin-top: 8px;">'
			+ status_bar
			+ '<div id="build-log-output" style="padding: 12px 0; max-height: 600px; overflow-y: auto;">'
			+ html_lines
			+ '</div></div>';

		if (frm.fields_dict.log_html) {
			frm.fields_dict.log_html.$wrapper.html(container);
			let output = document.getElementById("build-log-output");
			if (output) output.scrollTop = output.scrollHeight;
		}
	},

	setup_realtime(frm) {
		if (frm._realtime_setup) return;
		frm._realtime_setup = true;

		frappe.realtime.on("lab_build_log", function(data) {
			if (data.build_log !== frm.doc.name) return;

			frm.doc.message = (frm.doc.message || "") + data.log + "\n";
			frm.trigger("render_log");

			if (data.type === "success" || data.type === "error") {
				frm.reload_doc();
			}
		});
	},
});
