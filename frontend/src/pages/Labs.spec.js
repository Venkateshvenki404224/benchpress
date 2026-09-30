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
	owner: "support@example.com",
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
const { labsResource } = await import("@/data/labs");
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

	const cards = () =>
		[...root.querySelectorAll('[data-test^="lab-card-"]')].map((card) =>
			card.dataset.test.replace("lab-card-", "")
		);

	async function type(query) {
		const input = find("labs-search");
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

	it("keeps the labs-search and filter-* hooks the e2e suite drives", () => {
		expect(find("labs-search").tagName).toBe("INPUT");
		expect(find("labs-search").placeholder).toBe("Search labs");
		expect(find("filter-status").tagName).toBe("SELECT");
		expect(find("filter-version").tagName).toBe("SELECT");
		expect(find("filter-owner").tagName).toBe("SELECT");
	});

	it("offers each filter only the values the labs have", () => {
		const values = (test) => [...find(test).options].map((option) => option.value);

		expect(values("filter-status")).toEqual(["__all__", "Draft", "Ready"]);
		expect(values("filter-version")).toEqual(["__all__", "version-15", "version-16"]);
		expect(find("filter-status").options[0].textContent).toBe("Status: all");
	});

	it("keeps the owner filter's overflow classes", () => {
		expect(find("filter-owner").classList.contains("max-w-full")).toBe(true);
		expect(find("filter-owner").classList.contains("overflow-hidden")).toBe(true);
	});

	it("searches a lab's app names", async () => {
		await type("helpdesk");

		expect(cards()).toEqual(["support-trial"]);
	});

	it("searches a lab's description", async () => {
		await type("order-to-cash");

		expect(cards()).toEqual(["sales-desk"]);
	});

	it("searches a lab's title", async () => {
		await type("support trial");

		expect(cards()).toEqual(["support-trial"]);
	});

	it("searches a lab's id, ignoring case", async () => {
		await type("BARE");

		expect(cards()).toEqual(["bare-bench"]);
	});

	it("narrows by version", async () => {
		await choose("filter-version", "version-15");

		expect(cards()).toEqual(["support-trial"]);
	});

	it("narrows by owner", async () => {
		await choose("filter-owner", "Administrator");

		expect(cards()).toEqual(["sales-desk", "bare-bench"]);
	});

	it("narrows by status, and Clear filters brings every lab back", async () => {
		await choose("filter-status", "Ready");
		expect(cards()).toEqual(["sales-desk", "bare-bench"]);

		await type("no such lab");
		expect(cards()).toEqual([]);
		expect(root.textContent).toContain("No labs match these filters.");

		find("clear-filters").click();
		await nextTick();

		expect(cards()).toEqual(["sales-desk", "support-trial", "bare-bench"]);
		expect(find("labs-search").value).toBe("");
		expect(find("filter-status").value).toBe("__all__");
	});

	it("hides the bar when there are no labs", async () => {
		const labs = labsResource.data;
		labsResource.data = [];
		try {
			await nextTick();

			expect(find("labs-search")).toBeNull();
		} finally {
			labsResource.data = labs;
		}
	});
});
