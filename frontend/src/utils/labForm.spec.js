import { describe, expect, it } from "vitest";
import {
	LAB_ID_MAX_LENGTH,
	buildSummary,
	cpuCoresError,
	imageTag,
	joinWords,
	labIdError,
	slugify,
} from "./labForm";

// The grammar `docker_manager.LAB_ID_RE` enforces, restated here so a drift on
// either side fails a test rather than a save.
const BACKEND_LAB_ID_RE = /^[a-z0-9]+([._-][a-z0-9]+)*$/;

describe("slugify", () => {
	const cases = [
		["Support Sandbox", "support-sandbox"],
		["CRM Lab v2", "crm-lab-v2"],
		["  Leading and trailing  ", "leading-and-trailing"],
		["Café Lab", "cafe-lab"],
		["HR / Payroll", "hr-payroll"],
		["ERPNext  ---  Demo", "erpnext-demo"],
		["under_score.and.dots", "under_score.and.dots"],
		["!!!", ""],
		["", ""],
	];

	for (const [title, expected] of cases) {
		it(`turns "${title}" into "${expected}"`, () => {
			expect(slugify(title)).toBe(expected);
		});
	}

	it("produces an ID the backend grammar accepts", () => {
		for (const [title] of cases) {
			const slug = slugify(title);
			if (slug) expect(BACKEND_LAB_ID_RE.test(slug)).toBe(true);
		}
	});

	it("never exceeds the tag length, and never ends on a separator", () => {
		const slug = slugify("a very long lab title ".repeat(20));
		expect(slug.length).toBeLessThanOrEqual(LAB_ID_MAX_LENGTH);
		expect(BACKEND_LAB_ID_RE.test(slug)).toBe(true);
	});
});

describe("labIdError", () => {
	it("accepts the IDs the backend accepts", () => {
		for (const id of ["crm-lab", "dev-v15", "a", "under_score.and.dots", "x1"]) {
			expect(labIdError(id)).toBe("");
		}
	});

	it("rejects a title that slugifies to nothing", () => {
		expect(labIdError(slugify("!!!"))).toContain("required");
	});

	it("rejects uppercase, spaces and doubled separators", () => {
		for (const id of ["CRM", "crm lab", "crm--lab", "-crm", "crm-"]) {
			expect(labIdError(id)).not.toBe("");
			expect(BACKEND_LAB_ID_RE.test(id)).toBe(false);
		}
	});

	it("rejects an ID past the length ceiling", () => {
		expect(labIdError("a".repeat(LAB_ID_MAX_LENGTH + 1))).toContain("at most");
	});
});

describe("cpuCoresError", () => {
	it("requires at least one core, as Lab.validate_cpu_cores does", () => {
		expect(cpuCoresError(1)).toBe("");
		expect(cpuCoresError(4)).toBe("");
		expect(cpuCoresError(0)).toContain("at least 1");
		expect(cpuCoresError(-2)).toContain("at least 1");
		expect(cpuCoresError("")).toContain("at least 1");
	});
});

describe("imageTag", () => {
	it("is the tag docker_manager gives every build of the lab", () => {
		expect(imageTag("crm-lab")).toBe("benchpress/crm-lab:latest");
		expect(imageTag("")).toBe("");
	});
});

describe("joinWords", () => {
	it("writes a list, not a comma run", () => {
		expect(joinWords([])).toBe("");
		expect(joinWords(["erpnext"])).toBe("erpnext");
		expect(joinWords(["erpnext", "hrms"])).toBe("erpnext and hrms");
		expect(joinWords(["erpnext", "hrms", "crm"])).toBe("erpnext, hrms and crm");
	});
});

describe("buildSummary", () => {
	const form = () => ({
		lab_id: "support-sandbox",
		frappe_version: "version-16",
		enable_code_server: true,
		enable_ssh: false,
		apps: [
			{
				app_name: "helpdesk",
				git_url: "https://github.com/frappe/helpdesk",
				branch: "main",
			},
		],
	});

	it("names the image, the version, the apps and the access", () => {
		expect(buildSummary(form())).toEqual([
			"Docker image benchpress/support-sandbox:latest",
			"Frappe version-16 with helpdesk",
			"Code server enabled, SSH off",
			"A site is created on first deploy, not at build time",
		]);
	});

	it("recomputes when the form changes", () => {
		const changed = {
			...form(),
			lab_id: "hr-lab",
			frappe_version: "version-15",
			enable_code_server: false,
			enable_ssh: true,
			apps: [
				{ app_name: "hrms", git_url: "https://github.com/frappe/hrms", branch: "main" },
				{
					app_name: "erpnext",
					git_url: "https://github.com/frappe/erpnext",
					branch: "main",
				},
			],
		};
		expect(buildSummary(changed)).toEqual([
			"Docker image benchpress/hr-lab:latest",
			"Frappe version-15 with hrms and erpnext",
			"No code server, SSH enabled",
			"A site is created on first deploy, not at build time",
		]);
	});

	it("ignores half-filled app rows and says a bare bench is a bare bench", () => {
		const bare = { ...form(), apps: [{ app_name: "erpnext", git_url: "", branch: "" }] };
		expect(buildSummary(bare)[1]).toBe("Frappe version-16 with no extra apps — a bare bench");
	});

	it("says the tag is not settled yet when there is no title", () => {
		expect(buildSummary({ ...form(), lab_id: "" })[0]).toContain("once the lab has a title");
	});
});
