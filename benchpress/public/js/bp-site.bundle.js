// window.bpSite: the theme toggle, the mobile nav disclosure, and postMethod(method, values,
// options), which posts to a whitelisted method and resolves with its return value.
(function () {
	const MODES = ["dark", "light"];
	const DEFAULT_MODE = "dark";
	const STORAGE_KEY = "bp-mode";
	const CONTENT_ID = "bp-content";
	const GENERIC_ERROR = "Something went wrong. Please try again.";

	function mode() {
		const wrapper = document.querySelector(".bp");
		return wrapper && wrapper.dataset.mode === "light" ? "light" : DEFAULT_MODE;
	}

	function setMode(next) {
		const value = MODES.indexOf(next) === -1 ? DEFAULT_MODE : next;
		document.querySelectorAll(".bp").forEach((wrapper) => {
			wrapper.dataset.mode = value;
		});
		// A browser in private mode throws on write.
		try {
			localStorage.setItem(STORAGE_KEY, value);
		} catch (error) {
			void error;
		}
		syncToggles(value);
		return value;
	}

	function toggleMode() {
		return setMode(mode() === "dark" ? "light" : "dark");
	}

	async function postMethod(method, values, options) {
		const response = await fetch(`/api/method/${method}`, {
			method: "POST",
			credentials: "same-origin",
			headers: Object.assign({ Accept: "application/json" }, csrfHeader()),
			body: encode(values),
			signal: (options || {}).signal,
		});
		const payload = await response.json().catch(() => ({}));

		if (!response.ok) throw requestError(payload, response.status);
		return payload.message;
	}

	// --- theme -----------------------------------------------------------------------------

	function storedMode() {
		try {
			const saved = localStorage.getItem(STORAGE_KEY);
			return MODES.indexOf(saved) === -1 ? null : saved;
		} catch (error) {
			return null;
		}
	}

	function syncToggles(value) {
		document.querySelectorAll("[data-bp-mode-toggle]").forEach((button) => {
			button.setAttribute("aria-pressed", String(value === "light"));
		});
	}

	function wireModeToggles() {
		document.querySelectorAll("[data-bp-mode-toggle]").forEach((button) => {
			button.addEventListener("click", toggleMode);
		});
	}

	// --- mobile nav ------------------------------------------------------------------------

	function wireNav() {
		const header = document.querySelector("[data-bp-header]");
		const button = header && header.querySelector("[data-bp-nav-toggle]");
		if (!button) return;

		button.addEventListener("click", () => setNavOpen(header, header.dataset.open !== "true"));

		header.addEventListener("keydown", (event) => {
			if (event.key !== "Escape" || header.dataset.open !== "true") return;
			setNavOpen(header, false);
			button.focus();
		});
		header.addEventListener("click", (event) => {
			if (event.target.closest(".bp-navlink")) setNavOpen(header, false);
		});
		document.addEventListener("click", (event) => {
			if (header.dataset.open !== "true" || header.contains(event.target)) return;
			setNavOpen(header, false);
		});
	}

	function setNavOpen(header, open) {
		header.dataset.open = String(open);
		const button = header.querySelector("[data-bp-nav-toggle]");
		if (button) button.setAttribute("aria-expanded", String(open));
	}

	// Without JS the form posts straight to Frappe, which answers with its own "Logged Out" page.
	function wireSignOut() {
		document.querySelectorAll("[data-bp-signout]").forEach((form) => {
			form.addEventListener("submit", async (event) => {
				event.preventDefault();
				try {
					await fetch(form.action, {
						method: "POST",
						credentials: "same-origin",
						headers: { Accept: "application/json" },
						body: new URLSearchParams(new FormData(form)),
					});
				} catch (error) {
					void error;
				}
				window.location.reload();
			});
		});
	}

	// The header's skip link needs something to skip to; the page templates own that element.
	function ensureContentAnchor() {
		if (document.getElementById(CONTENT_ID)) return;
		const header = document.querySelector("[data-bp-header]");
		const target =
			document.querySelector(".bp main") ||
			(header && header.nextElementSibling) ||
			document.querySelector(".bp");
		if (target) target.id = CONTENT_ID;
	}

	// --- posting ---------------------------------------------------------------------------

	function encode(values) {
		if (values instanceof URLSearchParams) return values;
		if (values instanceof FormData) return new URLSearchParams(values);

		const params = new URLSearchParams();
		Object.keys(values || {}).forEach((key) => {
			const value = values[key];
			if (value !== null && value !== undefined) params.append(key, String(value));
		});
		return params;
	}

	function csrfHeader() {
		const token =
			(window.frappe && window.frappe.csrf_token) || document.body.dataset.csrfToken || "";
		return token ? { "X-Frappe-CSRF-Token": token } : {};
	}

	function requestError(payload, status) {
		const error = new Error(serverMessage(payload) || GENERIC_ERROR);
		error.status = status;
		error.payload = payload;
		return error;
	}

	// `_server_messages` is a JSON list of JSON strings.
	function serverMessage(payload) {
		let messages = [];
		try {
			messages = JSON.parse(payload._server_messages || "[]");
		} catch (error) {
			return "";
		}
		if (!messages.length) return "";

		let first = messages[0];
		try {
			first = JSON.parse(first).message;
		} catch (error) {
			void error;
		}
		return String(first || "")
			.replace(/<[^>]*>/g, "")
			.trim();
	}

	function start() {
		const saved = storedMode();
		if (saved) setMode(saved);
		else syncToggles(mode());
		ensureContentAnchor();
		wireModeToggles();
		wireNav();
		wireSignOut();
	}

	window.bpSite = { mode, setMode, toggleMode, postMethod };

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
