import { createApp, h, nextTick, reactive } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const resources = {};

const FRAPPE_DEVELOP = {
	key: "frappe-develop",
	title: "Frappe develop bench",
	description: "An empty Frappe develop bench you manage yourself.",
	frappe_version: "develop",
	memory_limit: "2g",
	cpu_cores: 2,
	image_ready: false,
};

const LAUNCHED = {
	bench: "b1",
	lab: "frappe-develop",
	lab_title: "Frappe develop bench",
	will_build: true,
};

vi.mock("frappe-ui", () => {
	const passThrough = (tag) => (_props, { slots, attrs }) => h(tag, attrs, slots.default?.());
	return {
		Badge: passThrough("span"),
		Button: passThrough("button"),
		ErrorMessage: () => null,
		ListView: () => null,
		ListHeader: () => null,
		ListRows: () => null,
		dayjsLocal: () => ({ fromNow: () => "a minute ago" }),
		toast: { success: vi.fn() },
		createResource: (options) => {
			const resource = reactive({
				data: options.url === "benchpress.api.get_bench_templates" ? [FRAPPE_DEVELOP] : [],
				loading: false,
				error: null,
				reload: vi.fn(),
				submit: vi.fn(async () => LAUNCHED),
			});
			resources[options.url] = resource;
			return resource;
		},
	};
});

vi.mock("@/data/labs", () => ({ labsResource: { reload: vi.fn() } }));
vi.mock("@/data/deployRun", () => ({ openDeployRun: vi.fn() }));

const { openDeployRun } = await import("@/data/deployRun");
const { default: Benches } = await import("./Benches.vue");

describe("the Benches page", () => {
	let app;
	let root;

	beforeEach(async () => {
		root = document.createElement("div");
		document.body.append(root);
		app = createApp(Benches);
		app.mount(root);
		await nextTick();
	});

	afterEach(() => {
		app.unmount();
		root.remove();
	});

	it("renders a card for each bench template", () => {
		const card = root.querySelector('[data-test="bench-template-frappe-develop"]');

		expect(card.textContent).toContain("Frappe develop bench");
		expect(card.textContent).toContain("develop");
		expect(card.textContent).toContain("2 GB");
	});

	it("warns that the first launch builds the image", () => {
		const card = root.querySelector('[data-test="bench-template-frappe-develop"]');

		expect(card.textContent).toContain("First launch builds, about 30 minutes");
	});

	it("prepares the bench from the template key and opens the deploy dialog", async () => {
		root.querySelector('[data-test="prepare-bench-frappe-develop"]').click();
		await nextTick();
		await nextTick();

		expect(resources["benchpress.api.launch_template"].submit).toHaveBeenCalledWith({
			template: "frappe-develop",
		});
		expect(openDeployRun).toHaveBeenCalledWith({
			labId: "frappe-develop",
			labTitle: "Frappe develop bench",
			benchName: "b1",
			willBuild: true,
		});
	});

	it("says so when the user has no benches yet", () => {
		expect(root.querySelector('[data-test="my-benches"]').textContent).toContain(
			"No benches yet"
		);
	});
});
