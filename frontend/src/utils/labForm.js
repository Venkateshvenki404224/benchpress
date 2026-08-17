/**
 * The New lab form's rules, as pure functions.
 *
 * Two of them mirror the backend and must not drift: `slugify` produces a lab
 * ID that `docker_manager.validate_lab_id` accepts, and `labIdError` applies
 * that same grammar in the form. A lab ID becomes a Docker image tag and a site
 * domain, so a title that slugifies to something the server rejects has to be
 * caught while the user can still see the field — not thrown back from a save.
 *
 * The third, `buildSummary`, is the summary rail: what this form will actually
 * produce, recomputed from the form on every edit rather than described once in
 * static copy.
 */

import { rateLabel } from "@/utils/credits";
import { cpuLabel, memoryLabel } from "@/utils/labSpecs";

// `docker_manager.LAB_ID_RE` / `LAB_ID_MAX_LENGTH`, verbatim.
const LAB_ID_RE = /^[a-z0-9]+([._-][a-z0-9]+)*$/;
export const LAB_ID_MAX_LENGTH = 64;
export const LAB_ID_RULE = "Lowercase letters, numbers and single '.', '_' or '-' separators";

// `Lab.validate_cpu_cores`.
export const BASELINE_CPU_CORES = 1;

/**
 * A title as a lab ID: "Support Sandbox v2" → "support-sandbox-v2".
 *
 * Accents are folded rather than dropped, so "Café Lab" becomes "cafe-lab" and
 * not "caf-lab". Everything the grammar disallows becomes a separator, repeated
 * separators collapse, and the result is trimmed to the length the tag allows.
 */
export function slugify(title) {
	const folded = String(title ?? "")
		.normalize("NFD")
		.replace(/[\u0300-\u036f]/g, "")
		.toLowerCase();
	const separated = folded.replace(/[^a-z0-9._-]+/g, "-").replace(/[._-]{2,}/g, "-");
	return trimSeparators(separated)
		.slice(0, LAB_ID_MAX_LENGTH)
		.replace(/[._-]+$/, "");
}

function trimSeparators(value) {
	return value.replace(/^[._-]+/, "").replace(/[._-]+$/, "");
}

/** Why this lab ID would be rejected, or "" when it would not. */
export function labIdError(labId) {
	const value = String(labId ?? "").trim();
	if (!value) return "A lab ID is required — give the lab a title and one is derived from it.";
	if (value.length > LAB_ID_MAX_LENGTH) {
		return `A lab ID may be at most ${LAB_ID_MAX_LENGTH} characters — this title is too long.`;
	}
	if (!LAB_ID_RE.test(value)) {
		return `"${value}" is not a valid lab ID. ${LAB_ID_RULE}, e.g. "crm-lab".`;
	}
	return "";
}

/** Why this CPU count would be rejected, or "" when it would not. */
export function cpuCoresError(cpuCores) {
	const cores = Number(cpuCores);
	if (!Number.isFinite(cores) || cores < BASELINE_CPU_CORES) {
		return `CPU cores must be at least ${BASELINE_CPU_CORES}.`;
	}
	return "";
}

/** Every app row that is complete enough to clone. */
export function completeApps(apps) {
	return (apps ?? []).filter((app) => app.app_name && app.git_url && app.branch);
}

/**
 * The image line — a lab no longer owns its image.
 *
 * `docker_manager` tags every build with the build spec's content hash
 * (`benchpress/cache:<hash>`), so a lab whose recipe someone already built reuses that image and
 * skips the build entirely. The tag itself is not derivable here, since the hash is computed
 * server-side, so the line says what the sharing means rather than naming a tag.
 */
export function imagePhrase(apps) {
	return completeApps(apps).length
		? "Docker image shared with every lab that builds these same apps"
		: "Docker image shared with every bare-bench lab — likely built already";
}

/**
 * The size line — the only line on the rail that names a price.
 *
 * Empty when no size is chosen, so a lab with hand-typed limits (a self-hoster's,
 * or one written before sizes existed) simply has one fewer sentence rather than
 * a sentence about nothing. The rate is omitted when credits are off.
 */
export function sizePhrase(size, creditsEnabled) {
	if (!size) return "";
	const specs = `${memoryLabel(size.memory_limit)}, ${cpuLabel(size.cpu_cores)}`;
	const price = creditsEnabled ? ` at ${rateLabel(size.credits_per_hour)}` : "";
	return `${size.size_label} — ${specs}${price}`;
}

/**
 * "What gets built", as sentences derived from the form.
 *
 * The rail is the only place the form says what the user is actually creating,
 * so every line is computed — nothing here is a fixed string describing a
 * default that the fields above may already have changed.
 */
export function buildSummary(form, size, creditsEnabled) {
	return [
		sizePhrase(size, creditsEnabled),
		imagePhrase(form.apps),
		`Frappe ${form.frappe_version} ${appsPhrase(form.apps)}`,
		accessPhrase(form),
		"A site is created on first deploy, not at build time",
	].filter(Boolean);
}

function appsPhrase(apps) {
	const names = completeApps(apps).map((app) => app.app_name);
	if (!names.length) return "with no extra apps — a bare bench";
	return `with ${joinWords(names)}`;
}

/** "a", "a and b", "a, b and c" — the design writes lists, not comma runs. */
export function joinWords(words) {
	if (words.length < 2) return words.join("");
	return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

function accessPhrase(form) {
	const codeServer = form.enable_code_server ? "Code server enabled" : "No code server";
	const ssh = form.enable_ssh ? "SSH enabled" : "SSH off";
	return `${codeServer}, ${ssh}`;
}
