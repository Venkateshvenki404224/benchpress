// `/signup` — the access-request form. A progressive upgrade over the native form post, so
// `noValidate` is set from here and never written into the markup.

(function () {
	const METHOD = "benchpress.waitlist.join";
	const SELECTED = "is-selected";

	// Anything not named here falls back to `control.validationMessage`.
	const MESSAGES = {
		full_name: "Tell us who to open the account for.",
		email: "Enter a valid email address.",
		company: "Tell us the company or team this is for.",
		team_size: "Choose how many people need environments.",
		expected_apps: "Tell us roughly which apps you expect to run.",
		consented: "Please acknowledge that access is granted manually.",
	};

	// --- chips -------------------------------------------------------------------------------

	function wireChips(root) {
		const group = root.querySelector("[data-bp-chips]");
		const value = root.querySelector("[data-bp-chip-value]");
		if (!group || !value) return;

		group.addEventListener("click", (event) => {
			const chip = event.target.closest("[data-bp-chip]");
			if (!chip) return;
			selectChip(group, value, chip.dataset.bpChip);
		});
	}

	function selectChip(group, value, chosen) {
		group.querySelectorAll("[data-bp-chip]").forEach((chip) => {
			const on = chip.dataset.bpChip === chosen;
			chip.classList.toggle(SELECTED, on);
			chip.setAttribute("aria-pressed", String(on));
		});
		value.value = chosen;
	}

	// --- validation --------------------------------------------------------------------------

	function invalidControls(form) {
		return controls(form).filter((control) => !control.checkValidity());
	}

	function showFieldError(control) {
		const slot = errorSlot(control);
		control.setAttribute("aria-invalid", "true");
		if (slot) {
			slot.textContent = MESSAGES[control.name] || control.validationMessage;
			slot.hidden = false;
		}
	}

	function clearFieldError(control) {
		const slot = errorSlot(control);
		control.removeAttribute("aria-invalid");
		if (slot) {
			slot.textContent = "";
			slot.hidden = true;
		}
	}

	function errorSlot(control) {
		const id = control.getAttribute("aria-describedby");
		return id ? document.getElementById(id) : null;
	}

	function controls(form) {
		return Array.prototype.slice.call(form.querySelectorAll("[aria-describedby]"));
	}

	// --- submitting --------------------------------------------------------------------------

	function wireForm(root) {
		const form = root.querySelector("[data-bp-signup-form]");
		// With no `bpSite` the native form post stays the whole story.
		if (!form || !window.bpSite) return;

		form.noValidate = true;
		controls(form).forEach((control) => {
			control.addEventListener("input", () => clearFieldError(control));
			control.addEventListener("change", () => clearFieldError(control));
		});
		form.addEventListener("submit", (event) => {
			event.preventDefault();
			send(root, form);
		});
	}

	async function send(root, form) {
		const banner = root.querySelector("[data-bp-form-alert]");
		const button = form.querySelector("[data-bp-submit]");

		controls(form).forEach(clearFieldError);
		hideAlert(banner);

		const invalid = invalidControls(form);
		if (invalid.length) {
			invalid.forEach(showFieldError);
			invalid[0].focus();
			return;
		}

		setBusy(button, true);
		try {
			const reply = await window.bpSite.postMethod(METHOD, new FormData(form));
			showReceipt(root, form, reply, form.elements.email.value.trim());
			window.bpSite.track("waitlist_submitted");
		} catch (error) {
			showAlert(banner, error.message);
		} finally {
			setBusy(button, false);
		}
	}

	function showReceipt(root, form, reply, email) {
		const receipt = root.querySelector("[data-bp-receipt]");
		if (!receipt) return;

		setText(receipt, "[data-bp-reference]", (reply && reply.reference) || "");
		setText(receipt, "[data-bp-receipt-email]", email);
		form.hidden = true;
		receipt.hidden = false;

		const title = receipt.querySelector("[data-bp-receipt-title]");
		if (title) title.focus();
	}

	function setBusy(button, busy) {
		if (!button) return;
		button.disabled = busy;
		button.setAttribute("aria-busy", String(busy));
	}

	function showAlert(banner, message) {
		if (!banner) return;
		banner.textContent = message;
		banner.hidden = false;
	}

	function hideAlert(banner) {
		if (!banner) return;
		banner.textContent = "";
		banner.hidden = true;
	}

	function setText(root, selector, text) {
		const node = root.querySelector(selector);
		if (node) node.textContent = text;
	}

	function start() {
		const root = document.querySelector(".bp");
		if (!root) return;
		wireChips(root);
		wireForm(root);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
