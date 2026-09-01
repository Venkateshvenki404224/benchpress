// Landing page behaviour: three tab strips, one copy button, one reduced-motion guard.

(function () {
	const COPIED_LABEL = "copied";
	const COPY_LABEL = "copy";
	const COPY_RESET_MS = 1600;

	// --- pipeline phases -------------------------------------------------------------------

	function bindPhaseTabs(root) {
		const strip = root.querySelector("[data-bp-phase-tabs]");
		if (!strip) return;

		strip.addEventListener("click", (event) => {
			const button = event.target.closest("[data-bp-phase]");
			if (button) selectPhase(root, button);
		});
	}

	// One set of nodes is shared by every phase, so the tab carries the list that is lit.
	function selectPhase(root, button) {
		const key = button.dataset.bpPhase;
		const nodes = splitKeys(button.dataset.bpNodes);
		const chips = splitKeys(button.dataset.bpChips);

		const panels = root.querySelectorAll("[data-bp-phase-panel]");
		press(root.querySelectorAll("[data-bp-phase]"), (tab) => tab.dataset.bpPhase === key);
		reveal(panels, (panel) => panel.dataset.bpPhasePanel === key);

		for (const node of root.querySelectorAll("[data-bp-node]")) {
			node.classList.toggle("is-on", nodes.includes(node.dataset.bpNode));
		}
		for (const chip of root.querySelectorAll("[data-bp-chip]")) {
			chip.classList.toggle("is-on", chips.includes(chip.dataset.bpChip));
		}
	}

	// --- console and API tabs --------------------------------------------------------------

	function bindTabs(root, tabAttribute, panelAttribute, stripAttribute) {
		const strip = root.querySelector(`[${stripAttribute}]`);
		if (!strip) return;

		strip.addEventListener("click", (event) => {
			const button = event.target.closest(`[${tabAttribute}]`);
			if (!button) return;
			const key = button.getAttribute(tabAttribute);
			const tabs = root.querySelectorAll(`[${tabAttribute}]`);
			const panels = root.querySelectorAll(`[${panelAttribute}]`);

			press(tabs, (tab) => tab.getAttribute(tabAttribute) === key);
			reveal(panels, (panel) => panel.getAttribute(panelAttribute) === key);
		});
	}

	// --- copy ------------------------------------------------------------------------------

	// `navigator.clipboard` is undefined outside a secure context.
	function bindCopy(root) {
		const button = root.querySelector("[data-bp-copy]");
		if (!button) return;

		button.addEventListener("click", async () => {
			const panel = visiblePanel(root, "[data-bp-api-panel]");
			if (!panel || !navigator.clipboard) return;

			try {
				await navigator.clipboard.writeText(panel.textContent);
			} catch (error) {
				void error;
				return;
			}
			setCopyLabel(button, COPIED_LABEL);
			window.setTimeout(() => setCopyLabel(button, COPY_LABEL), COPY_RESET_MS);
		});
	}

	function setCopyLabel(button, text) {
		const label = button.querySelector("[data-bp-copy-label]");
		if (label) label.textContent = text;
	}

	function visiblePanel(root, selector) {
		return Array.from(root.querySelectorAll(selector)).find((panel) => !panel.hidden) || null;
	}

	// --- the hero film ----------------------------------------------------------------------

	// CSS cannot pause a video. The element is an `img` in the poster-only state, hence the
	// method check rather than a tag check.
	function holdFilm(root) {
		const film = root.querySelector(".bp-film__video");
		if (!film || typeof film.pause !== "function") return;
		if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

		film.autoplay = false;
		film.pause();
	}

	// --- helpers ---------------------------------------------------------------------------

	function press(buttons, isOn) {
		for (const button of buttons) {
			const on = isOn(button);
			button.classList.toggle("is-selected", on);
			button.setAttribute("aria-pressed", String(on));
		}
	}

	function reveal(panels, isOn) {
		for (const panel of panels) panel.hidden = !isOn(panel);
	}

	function splitKeys(value) {
		return (value || "")
			.split(",")
			.map((part) => part.trim())
			.filter(Boolean);
	}

	function start() {
		const root = document.querySelector(".bp");
		if (!root) return;

		bindPhaseTabs(root);
		bindTabs(root, "data-bp-console-tab", "data-bp-console-panel", "data-bp-console-tabs");
		bindTabs(root, "data-bp-api-tab", "data-bp-api-panel", "data-bp-api-tabs");
		bindCopy(root);
		holdFilm(root);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
