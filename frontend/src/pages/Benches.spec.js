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
	existing_bench: null,
};

const LAUNCHED = {
	bench: "b1",
	lab: "frappe-develop",
	lab_title: "Frappe develop bench",
	will_build: true,
};

vi.mock("frappe-ui", () => {
	const passThrough =
		(tag) =>
		(_props, { slots, attrs }) =>
			h(tag, attrs, slots.default?.());
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
				data: initialData(options.url),
				loading: false,
				error: null,
				reload: vi.fn(),
				setData: vi.fn((data) => (resource.data = data)),
				submit: vi.fn(async () => LAUNCHED),
			});
			resources[options.url] = resource;
			return resource;
		},
	};
});

vi.mock("vue-router", () => ({
	RouterLink: (props, { slots, attrs }) => h("a", { href: props.to, ...attrs }, slots.default?.()),
}));

function initialData(url) {
	if (url === "benchpress.api.get_bench_templates") return [FRAPPE_DEVELOP];
	return [];
}

vi.mock("@/data/labs", () => ({ labsResource: { reload: vi.fn() } }));
vi.mock("@/data/deployRun", () => ({ openDeployRun: vi.fn() }));
vi.mock("@/data/sshKeys", async () => {
	const { ref } = await import("vue");
	return { hasSshKey: ref(true), loadSshKeys: vi.fn() };
});
vi.mock("@/data/benchpressSettings", () => ({
	SSH_KEYS_GROUP: "group-ssh-keys",
	openSettings: vi.fn(),
}));

const { openDeployRun } = await import("@/data/deployRun");
const { hasSshKey, loadSshKeys } = await import("@/data/sshKeys");
const { openSettings } = await import("@/data/benchpressSettings");
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
		hasSshKey.value = true;
		resources["benchpress.api.get_bench_templates"].data = [FRAPPE_DEVELOP];
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

	it("will not prepare a bench until a key is saved, and says why", async () => {
		hasSshKey.value = false;
		await nextTick();

		const button = root.querySelector('[data-test="prepare-bench-frappe-develop"]');
		button.click();
		await nextTick();

		expect(button.disabled).toBe(true);
		expect(resources["benchpress.api.launch_template"].submit).not.toHaveBeenCalled();
		expect(
			root.querySelector('[data-test="bench-template-frappe-develop"]').textContent
		).toContain("Add an SSH key first");
	});

	it("opens Settings on SSH keys from the hint", async () => {
		hasSshKey.value = false;
		await nextTick();

		root.querySelector('[data-test="add-ssh-key-link"]').click();

		expect(openSettings).toHaveBeenCalledWith("group-ssh-keys");
	});

	it("lets a bench be prepared as soon as a key is saved, with no reload", async () => {
		hasSshKey.value = false;
		await nextTick();
		const button = root.querySelector('[data-test="prepare-bench-frappe-develop"]');
		expect(button.disabled).toBe(true);

		hasSshKey.value = true;
		await nextTick();

		expect(button.disabled).toBe(false);
		expect(root.querySelector('[data-test="add-ssh-key-link"]')).toBeNull();
	});

	it("loads the saved keys and prints none of them", () => {
		expect(loadSshKeys).toHaveBeenCalled();
		expect(root.querySelector("textarea")).toBeNull();
		expect(root.querySelector('[data-test="ssh-keys"]')).toBeNull();
	});

	it("shows Open bench when the existing bench is Running", async () => {
		resources["benchpress.api.get_bench_templates"].data = [
			{ ...FRAPPE_DEVELOP, existing_bench: { name: "b1", lab: "lab-1", status: "Running" } },
		];
		await nextTick();

		expect(root.querySelector('[data-test="open-bench-frappe-develop"]')).not.toBeNull();
		expect(root.querySelector('[data-test="prepare-bench-frappe-develop"]')).toBeNull();
	});

	it("shows Start bench and calls bench_action start when the existing bench is Stopped", async () => {
		resources["benchpress.api.get_bench_templates"].data = [
			{
				...FRAPPE_DEVELOP,
				existing_bench: { name: "b1", lab: "lab-1", status: "Stopped" },
			},
		];
		await nextTick();

		const btn = root.querySelector('[data-test="start-bench-frappe-develop"]');
		expect(btn).not.toBeNull();

		btn.click();
		await nextTick();
		await nextTick();

		expect(resources["benchpress.api.bench_action"].submit).toHaveBeenCalledWith({
			bench_name: "b1",
			action: "start",
		});
	});

	it("shows a disabled spinner for a Deploying bench", async () => {
		resources["benchpress.api.get_bench_templates"].data = [
			{
				...FRAPPE_DEVELOP,
				existing_bench: { name: "b1", lab: "lab-1", status: "Deploying" },
			},
		];
		await nextTick();

		const btn = root.querySelector('[data-test="transitioning-bench-frappe-develop"]');
		expect(btn).not.toBeNull();
		expect(btn.disabled).toBe(true);
		expect(root.querySelector('[data-test="prepare-bench-frappe-develop"]')).toBeNull();
	});
});
