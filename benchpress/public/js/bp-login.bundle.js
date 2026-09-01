/* /login — hash normalisation and the password reveal, on top of Frappe's own login script.
 *
 * Loaded without `defer` on purpose: the inline `login.js` below calls `login.route()` as the
 * page parses, and `normaliseHash()` has to have run by then.
 */
(function () {
	"use strict";

	// Every hash `login.route()` can dispatch. It dispatches unguarded, so an unknown hash throws
	// after the cards are hidden and leaves a blank page.
	var ROUTES = ["", "login", "email", "steptwo", "forgot", "login-with-email-link", "signup"];

	var REVEAL = "[data-bp-reveal]";

	function currentRoute() {
		return (window.location.hash || "").replace(/^#/, "");
	}

	function normaliseHash() {
		if (ROUTES.indexOf(currentRoute()) !== -1) return;
		// `replaceState` fires no `hashchange`, so the framework's handler is not re-entered.
		window.history.replaceState(null, "", window.location.pathname + window.location.search);
	}

	function setRevealed(button, revealed) {
		var input = document.getElementById(button.getAttribute("data-bp-reveal"));
		if (!input) return;

		input.type = revealed ? "text" : "password";
		button.setAttribute("aria-pressed", String(revealed));
		var label = revealed ? "Hide password" : "Show password";
		button.setAttribute("aria-label", label);
		button.setAttribute("title", label);
	}

	function hideAllPasswords() {
		var buttons = document.querySelectorAll(REVEAL);
		for (var i = 0; i < buttons.length; i++) setRevealed(buttons[i], false);
	}

	// Delegated: `section.for-email-login` renders a second copy of the same field.
	function bindReveal() {
		document.addEventListener("click", function (event) {
			var button = event.target.closest ? event.target.closest(REVEAL) : null;
			if (!button) return;
			setRevealed(button, button.getAttribute("aria-pressed") !== "true");
		});
	}

	function start() {
		bindReveal();
		window.addEventListener("hashchange", hideAllPasswords);
	}

	normaliseHash();
	window.addEventListener("hashchange", normaliseHash);

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
