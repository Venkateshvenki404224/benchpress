// Landing page behaviour: the how-it-works phase switcher and the waitlist form.
//
// Every phase panel is rendered by Jinja and only toggled here, so the page is complete without
// JavaScript and a crawler reads all four phases. This file moves attributes; it never builds
// markup.

const WAITLIST_ENDPOINT = "/api/method/benchpress.waitlist.join";

function selectPhase(tab) {
	const root = document.querySelector("[data-phases]");
	const active = tab.dataset.phase;
	const nodes = (tab.dataset.nodes || "").split(",");
	const chips = (tab.dataset.chips || "").split(",");

	root.querySelectorAll("[data-phase]").forEach((element) => {
		const isActive = element.dataset.phase === active;
		if (element.classList.contains("tab")) element.setAttribute("aria-selected", isActive);
		else element.hidden = !isActive;
	});
	root.querySelectorAll("[data-node]").forEach((element) => {
		element.dataset.active = nodes.includes(element.dataset.node);
	});
	root.querySelectorAll("[data-chip]").forEach((element) => {
		element.dataset.active = chips.includes(element.dataset.chip);
	});
}

async function submitWaitlist(event) {
	event.preventDefault();
	const form = event.target;
	const status = form.querySelector("[data-status]");
	const button = form.querySelector("button");

	button.disabled = true;
	status.textContent = "Sending…";
	status.dataset.state = "pending";

	try {
		status.textContent = await postWaitlist(new FormData(form));
		status.dataset.state = "done";
		form.reset();
	} catch (error) {
		status.textContent = error.message;
		status.dataset.state = "error";
	} finally {
		button.disabled = false;
	}
}

async function postWaitlist(formData) {
	const response = await fetch(WAITLIST_ENDPOINT, {
		method: "POST",
		headers: csrfHeaders(),
		body: new URLSearchParams(formData),
	});
	const payload = await response.json().catch(() => ({}));

	if (!response.ok) throw new Error(errorMessage(payload));
	return payload.message.message;
}

function csrfHeaders() {
	const token = document.body.dataset.csrfToken;
	return token ? { "X-Frappe-CSRF-Token": token } : {};
}

function errorMessage(payload) {
	const messages = JSON.parse(payload._server_messages || "[]");
	if (!messages.length) return "Something went wrong. Please try again.";
	return JSON.parse(messages[0]).message;
}

function start() {
	document.querySelectorAll(".tab").forEach((tab) => {
		tab.addEventListener("click", () => selectPhase(tab));
	});
	const form = document.querySelector("[data-waitlist]");
	if (form) form.addEventListener("submit", submitWaitlist);
	if (window.lucide) window.lucide.createIcons();
}

document.addEventListener("DOMContentLoaded", start);
