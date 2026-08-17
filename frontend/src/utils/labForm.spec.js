import { describe, expect, it } from "vitest";
import {
	LAB_ID_MAX_LENGTH,
	buildSummary,
	cpuCoresError,
	imagePhrase,
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

describe("imagePhrase", () => {
	it("says the image is shared, because the tag is a content hash of the apps", () => {
		const apps = [
			{
				app_name: "helpdesk",
				git_url: "https://github.com/frappe/helpdesk",
				branch: "main",
			},
		];
		expect(imagePhrase(apps)).toContain("shared with every lab that builds these same apps");
		expect(imagePhrase([])).toContain("bare-bench");
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
			"Docker image shared with every lab that builds these same apps",
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
			"Docker image shared with every lab that builds these same apps",
			"Frappe version-15 with hrms and erpnext",
			"No code server, SSH enabled",
			"A site is created on first deploy, not at build time",
		]);
	});

	it("ignores half-filled app rows and says a bare bench is a bare bench", () => {
		const bare = { ...form(), apps: [{ app_name: "erpnext", git_url: "", branch: "" }] };
		expect(buildSummary(bare)[1]).toBe("Frappe version-16 with no extra apps — a bare bench");
	});

	it("still promises a shared image for a bare bench", () => {
		// The image line follows the apps, not the title: the tag is a hash of the recipe.
		expect(buildSummary({ ...form(), apps: [] })[0]).toContain("bare-bench");
	});
});
