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
	apps: [{ app_name: "crm" }],
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
	frappe_version: "version-16",
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
		Dialog: (props, { slots }) =>
			props.modelValue ? h("div", { "data-test": "dialog" }, [
				slots["body-content"]?.(),
				slots.actions?.(),
			]) : null,
		ErrorMessage: () => null,
		FormControl: passThrough("input"),
		Select: passThrough("div"),
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

	it("opens a preview of what the template contains when its card is clicked", async () => {
		expect(find("dialog")).toBeNull();

		find("template-crm").click();
		await nextTick();

		expect(find("dialog")).not.toBeNull();
		expect(root.textContent).toContain("Leads, deals and a sales pipeline.");
	});

	it("does not open the preview when the action button itself is clicked", async () => {
		find("use-template-crm").click();
		await nextTick();

		expect(find("dialog")).toBeNull();
	});
});
