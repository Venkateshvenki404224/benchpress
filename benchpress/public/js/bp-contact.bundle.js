// `/contact` behaviour: the topic chips, and posting the message without leaving the page.

(function () {
	const METHOD = "benchpress.contact.submit";

	// --- topic chips -------------------------------------------------------------------------

	function bindChips(form) {
		const group = form.querySelector("[data-bp-chips]");
		const value = form.querySelector("[data-bp-chip-value]");
		if (!group || !value) return;

		group.addEventListener("click", (event) => {
			const chip = event.target.closest("[data-bp-chip]");
			if (!chip) return;

			for (const button of group.querySelectorAll("[data-bp-chip]")) {
				const on = button === chip;
				button.classList.toggle("is-selected", on);
				button.setAttribute("aria-pressed", String(on));
			}
			value.value = chip.dataset.bpChip;
		});
	}

	// --- validation --------------------------------------------------------------------------

	function firstInvalid(form) {
		let first = null;
		for (const field of form.querySelectorAll("input[required], textarea[required]")) {
			const valid = field.checkValidity();
			showFieldError(field, valid ? "" : field.validationMessage);
			if (!valid && !first) first = field;
		}
		return first;
	}

	function showFieldError(field, message) {
		const slot = document.getElementById(`${field.id}-error`);
		field.setAttribute("aria-invalid", message ? "true" : "false");
		if (!slot) return;
		slot.textContent = message;
		slot.hidden = !message;
	}

	function bindLiveClearing(form) {
		form.addEventListener("input", (event) => {
			const field = event.target;
			if (field.matches("input, textarea") && field.checkValidity())
				showFieldError(field, "");
		});
	}

	// --- submitting --------------------------------------------------------------------------

	function bindSubmit(form) {
		const banner = form.querySelector("[data-bp-form-alert]");
		const sent = document.querySelector("[data-bp-sent]");

		// Only now, so a visitor without this script keeps the browser's own bubbles.
		form.noValidate = true;

		form.addEventListener("submit", async (event) => {
			event.preventDefault();
			hide(banner);

			const invalid = firstInvalid(form);
			if (invalid) {
				invalid.focus();
				return;
			}

			busy(form, true);
			try {
				const data = new FormData(form);
				const reply = await window.bpSite.postMethod(METHOD, data);
				showSent(form, sent, reply);
				window.bpSite.track("contact_submitted", {
					topic: String(data.get("topic") || ""),
				});
			} catch (error) {
				show(banner, error.message);
			} finally {
				busy(form, false);
			}
		});
	}

	function showSent(form, sent, reply) {
		form.hidden = true;
		if (!sent) return;

		const body = sent.querySelector("[data-bp-sent-body]");
		const title = sent.querySelector("[data-bp-sent-title]");
		if (body && reply && reply.message) body.textContent = reply.message;

		sent.hidden = false;
		if (title) title.focus();
	}

	function busy(form, isBusy) {
		const button = form.querySelector("[data-bp-submit]");
		if (!button) return;
		button.disabled = isBusy;
		button.setAttribute("aria-busy", String(isBusy));
	}

	// --- helpers -----------------------------------------------------------------------------

	function show(element, message) {
		if (!element) return;
		element.textContent = message;
		element.hidden = false;
	}

	function hide(element) {
		if (!element) return;
		element.hidden = true;
	}

	function start() {
		const form = document.querySelector("[data-bp-contact-form]");
		if (!form) return;

		bindChips(form);
		bindLiveClearing(form);
		bindSubmit(form);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
