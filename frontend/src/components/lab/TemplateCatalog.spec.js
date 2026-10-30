import { createApp, h, nextTick, reactive } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { push, catalog } = vi.hoisted(() => ({ push: vi.fn(), catalog: [] }));

const resources = {};

const CRM = {
	key: "crm",
	title: "CRM",
	description: "Leads, deals and a sales pipeline.",
	frappe_version: "version-16",
	logo: "",
	apps: [{ app_name: "crm" }, { app_name: "erpnext" }],
	memory_limit: "2g",
	cpu_cores: 1,
	eta_minutes: 6,
	most_used: false,
	lab: null,
};

const HELPDESK = {
	key: "helpdesk",
	title: "Helpdesk",
	description: "A ticket desk with an agent portal.",
	frappe_version: "version-15",
	logo: "",
	apps: [{ app_name: "helpdesk" }],
	memory_limit: "2g",
	cpu_cores: 1,
	eta_minutes: 6,
	most_used: false,
	lab: { name: "helpdesk", status: "Ready" },
};

const RUN = { lab: "crm", lab_title: "CRM", bench: "crm-bench-1", will_build: true };

vi.mock("frappe-ui", () => {
	const passThrough =
		(tag) =>
		(_props, { slots, attrs }) =>
			h(tag, attrs, slots.default?.());
	return {
		Badge: passThrough("span"),
		Button: passThrough("button"),
		ErrorMessage: () => null,
		FormControl: {
			props: ["modelValue"],
			emits: ["update:modelValue"],
			setup(props, { emit }) {
				return () =>
					h("input", {
						value: props.modelValue,
						onInput: (event) => emit("update:modelValue", event.target.value),
					});
			},
		},
		Select: {
			props: ["modelValue", "options"],
			emits: ["update:modelValue"],
			setup(props, { emit }) {
				return () =>
					h(
						"select",
						{
							value: props.modelValue,
							onChange: (event) => emit("update:modelValue", event.target.value),
						},
						props.options.map((option) =>
							h("option", { value: option.value }, option.label)
						)
					);
			},
		},
		toast: { success: vi.fn() },
		createResource: (options) => {
			const resource = reactive({
				data: options.url === "benchpress.api.get_lab_templates" ? [...catalog] : null,
				loading: false,
				error: null,
				reload: vi.fn(),
				submit: vi.fn(async () => RUN),
			});
			resources[options.url] = resource;
			return resource;
		},
	};
});

vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));

vi.mock("@/data/labs", () => ({ labsResource: { reload: vi.fn() } }));

vi.mock("@/data/userContext", () => ({ userContext: { isAdmin: true } }));

const { deployRun } = await import("@/data/deployRun");
const { userContext } = await import("@/data/userContext");
const { default: TemplateCatalog } = await import("./TemplateCatalog.vue");

describe("the template catalog", () => {
	let app;
	let root;

	async function mount(templates = [CRM, HELPDESK]) {
		catalog.splice(0, catalog.length, ...templates);
		root = document.createElement("div");
		document.body.append(root);
		app = createApp(TemplateCatalog);
		app.mount(root);
		await nextTick();
	}

	async function remountEmpty() {
		app.unmount();
		root.remove();
		await mount([]);
	}

	const find = (test) => root.querySelector(`[data-test="${test}"]`);

	beforeEach(async () => {
		push.mockClear();
		userContext.isAdmin = true;
		await mount();
	});

	afterEach(() => {
		app.unmount();
		root.remove();
	});

	it("draws one card per template", () => {
		expect(
			root.querySelectorAll('[data-test^="template-"]:not([data-test*="-footnote-"])')
		).toHaveLength(2);
		expect(find("template-crm")).not.toBeNull();
		expect(find("template-helpdesk")).not.toBeNull();
	});

	it("launches a template, reloads the catalog and opens the deploy", async () => {
		find("use-template-crm").click();
		await nextTick();
		await nextTick();

		expect(resources["benchpress.api.launch_template"].submit).toHaveBeenCalledWith({
			template: "crm",
		});
		expect(resources["benchpress.api.get_lab_templates"].reload).toHaveBeenCalled();
		expect(deployRun.open).toBe(true);
		expect(deployRun.benchName).toBe("crm-bench-1");
	});

	it("offers Go to lab, not Use template, for a template already used", () => {
		expect(find("open-lab-helpdesk")).not.toBeNull();
		expect(find("use-template-helpdesk")).toBeNull();
		expect(find("open-lab-crm")).toBeNull();
	});

	it("opens the lab from Go to lab", () => {
		find("open-lab-helpdesk").click();

		expect(push).toHaveBeenCalledWith("/labs/helpdesk");
	});

	it("offers New lab to an admin when the catalog is empty", async () => {
		await remountEmpty();

		expect(find("templates-new-lab")).not.toBeNull();
		expect(root.textContent).toContain("create a lab from scratch");
	});

	it("offers no New lab to a normal user when the catalog is empty", async () => {
		userContext.isAdmin = false;
		await remountEmpty();

		expect(find("templates-new-lab")).toBeNull();
		expect(root.textContent).toContain("ask an admin to add a template");
		expect(root.textContent).not.toContain("create a lab from scratch");
	});

	const cards = () =>
		[...root.querySelectorAll('[data-test^="template-"]:not([data-test*="-footnote-"])')].map(
			(card) => card.dataset.test.replace("template-", "")
		);

	async function type(query) {
		const input = find("templates-search");
		input.value = query;
		input.dispatchEvent(new Event("input"));
		await nextTick();
	}

	async function choose(test, value) {
		const select = find(test);
		select.value = value;
		select.dispatchEvent(new Event("change"));
		await nextTick();
	}

	it("keeps the templates-* hooks", () => {
		expect(find("templates-search").tagName).toBe("INPUT");
		expect(find("templates-search").placeholder).toBe("Search templates");
		expect(find("templates-filter-apps").tagName).toBe("SELECT");
		expect(find("templates-filter-version").tagName).toBe("SELECT");
	});

	it("labels the apps filter with each app's friendly name", () => {
		const labels = [...find("templates-filter-apps").options].map(
			(option) => option.textContent
		);

		expect(labels).toEqual(["Apps: all", "CRM", "ERPNext", "Helpdesk"]);
	});

	it("searches a template's app names", async () => {
		await type("erpnext");

		expect(cards()).toEqual(["crm"]);
	});

	it("searches a template's description", async () => {
		await type("agent portal");

		expect(cards()).toEqual(["helpdesk"]);
	});

	it("keeps only the templates on the chosen version", async () => {
		await choose("templates-filter-version", "version-16");

		expect(cards()).toEqual(["crm"]);
	});

	it("keeps only the templates that install the chosen app", async () => {
		await choose("templates-filter-apps", "helpdesk");

		expect(cards()).toEqual(["helpdesk"]);
	});

	it("offers Clear filters when nothing matches, and it brings every template back", async () => {
		await type("no such template");
		expect(cards()).toEqual([]);

		find("templates-clear-filters").click();
		await nextTick();

		expect(cards()).toEqual(["crm", "helpdesk"]);
		expect(find("templates-search").value).toBe("");
	});

	it("shows no bar when the catalog is empty", async () => {
		await remountEmpty();

		expect(find("templates-search")).toBeNull();
	});
});
