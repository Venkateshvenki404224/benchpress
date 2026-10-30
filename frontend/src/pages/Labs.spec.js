import { createApp, h, nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

const RUNNING = {
	name: "sales-desk",
	lab_id: "sales-desk",
	title: "Sales desk",
	description: "The sales team's order-to-cash bench.",
	frappe_version: "version-16",
	status: "Ready",
	owner: "Administrator",
	logo: "",
	memory_limit: "4g",
	cpu_cores: 2,
	app_names: ["erpnext", "crm"],
	deployed_as: { status: "Running", site: "sales-desk.benchpress.cloud", expires_at_ts: null },
	last_run: "2026-09-26 10:00:00",
};

const DRAFT = {
	name: "support-trial",
	lab_id: "support-trial",
	title: "Support trial",
	description: "A ticket desk to try before the rollout.",
	frappe_version: "version-15",
	status: "Draft",
	owner: "Administrator",
	logo: "",
	memory_limit: "2g",
	cpu_cores: 1,
	app_names: ["helpdesk"],
	deployed_as: null,
	last_run: null,
};

const BARE = {
	name: "bare-bench",
	lab_id: "bare-bench",
	title: "",
	description: "",
	frappe_version: "version-16",
	status: "Ready",
	owner: "Administrator",
	logo: "",
	memory_limit: "1g",
	cpu_cores: 1,
	app_names: [],
	deployed_as: null,
	last_run: null,
};

vi.mock("frappe-ui", () => {
	const passThrough =
		(tag) =>
		(_props, { slots, attrs }) =>
			h(tag, attrs, slots.default?.());
	const Tabs = {
		props: ["modelValue", "tabs"],
		setup(props, { slots, attrs }) {
			return () =>
				h("div", attrs, slots["tab-panel"]?.({ tab: props.tabs[props.modelValue] }));
		},
	};
	return {
		Badge: passThrough("span"),
		Button: passThrough("button"),
		Dialog: (props, { slots }) =>
			props.modelValue
				? h("div", { "data-test": "dialog" }, [
						slots["body-content"]?.(),
						slots.actions?.(),
				  ])
				: null,
		ErrorMessage: () => null,
		FormControl: passThrough("input"),
		Select: passThrough("div"),
		Tabs,
		createResource: () => ({ data: [], loading: false, error: null }),
		dayjsLocal: () => ({ fromNow: () => "a day ago" }),
		toast: { success: vi.fn() },
	};
});

vi.mock("vue-router", async () => {
	const { reactive } = await import("vue");
	const route = reactive({ name: "Labs" });
	return { useRouter: () => ({ push }), useRoute: () => route };
});

vi.mock("@/data/labs", async () => {
	const { reactive } = await import("vue");
	return {
		labsResource: reactive({ data: [RUNNING, DRAFT, BARE], loading: false, reload: vi.fn() }),
	};
});

vi.mock("@/data/userContext", async () => {
	const { reactive } = await import("vue");
	return { userContext: reactive({ isAdmin: true }) };
});

const { useRoute } = await import("vue-router");
const { userContext } = await import("@/data/userContext");
const { default: Labs } = await import("./Labs.vue");

describe("the Labs page", () => {
	let app;
	let root;

	beforeEach(async () => {
		push.mockClear();
		useRoute().name = "Labs";
		userContext.isAdmin = true;
		root = document.createElement("div");
		document.body.append(root);
		app = createApp(Labs);
		app.mount(root);
		await nextTick();
	});

	afterEach(() => {
		app.unmount();
		root.remove();
	});

	const find = (test) => root.querySelector(`[data-test="${test}"]`);

	it("draws one card per lab, and no table", () => {
		expect(root.querySelectorAll('[data-test^="lab-card-"]')).toHaveLength(3);
		expect(find("lab-card-sales-desk")).not.toBeNull();
		expect(find("lab-card-support-trial")).not.toBeNull();
		expect(find("lab-card-bare-bench")).not.toBeNull();
		expect(find("labs-table")).toBeNull();
	});

	it("badges a deployed lab with its bench's state, and a draft with the image's", () => {
		expect(
			find("lab-card-sales-desk").querySelector('[data-test="status-Running"]')
		).not.toBeNull();
		expect(
			find("lab-card-support-trial").querySelector('[data-test="status-Draft"]')
		).not.toBeNull();
	});

	it("says where a lab is deployed, or that it never was", () => {
		expect(find("lab-card-sales-desk").textContent).toContain("sales-desk.benchpress.cloud");
		expect(find("lab-card-support-trial").textContent).toContain("Never deployed");
	});

	const chipsOf = (name) =>
		[...find(`lab-card-${name}`).querySelector('[data-test="recipe-chips"]').children].map(
			(chip) => chip.textContent.trim()
		);

	it("chips the apps, then memory and CPU", () => {
		expect(chipsOf("sales-desk")).toEqual(["ERPNext", "CRM", "4 GB", "2 vCPU"]);
	});

	it("chips a lab with no apps as Frappe", () => {
		expect(chipsOf("bare-bench")).toEqual(["Frappe", "1 GB", "1 vCPU"]);
	});

	const LAB_DETAIL = { name: "LabDetail", params: { labId: "support-trial" } };

	it("opens the lab from a click on its card", () => {
		find("lab-card-support-trial").click();

		expect(push).toHaveBeenCalledTimes(1);
		expect(push).toHaveBeenCalledWith(LAB_DETAIL);
	});

	it("opens the lab once from its Open lab button", () => {
		find("lab-open-support-trial").click();

		expect(push).toHaveBeenCalledTimes(1);
		expect(push).toHaveBeenCalledWith(LAB_DETAIL);
	});

	it("opens on the labs tab at /labs", () => {
		expect(find("labs-grid")).not.toBeNull();
		expect(find("templates")).toBeNull();
	});

	it("opens on the templates tab at /labs/templates", async () => {
		useRoute().name = "LabTemplates";
		await nextTick();

		expect(find("templates")).not.toBeNull();
		expect(find("labs-grid")).toBeNull();
	});

	const headerActions = () =>
		[...find("labs").firstElementChild.querySelectorAll("button")].map(
			(button) => button.dataset.test
		);

	it("shows New lab to an admin as the only header action, and no From template button", () => {
		expect(headerActions()).toEqual(["new-lab"]);
		expect(find("from-template")).toBeNull();
	});

	it("hides New lab from a normal user, leaving no header action", async () => {
		userContext.isAdmin = false;
		await nextTick();

		expect(headerActions()).toEqual([]);
		expect(find("from-template")).toBeNull();
	});
});
