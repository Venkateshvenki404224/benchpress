import { createApp, h, nextTick, reactive } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const resources = {};
const SAVED_KEY =
	"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGmGY6wbhu8fIW8Ss6S9Yq5Vs9esVwGK0lP9CmjKHuPv dev@laptop";
let savedKeys = SAVED_KEY;

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
				submit: vi.fn(async (params) =>
					options.url === "benchpress.user.set_ssh_keys" ? params.keys : LAUNCHED
				),
			});
			resources[options.url] = resource;
			return resource;
		},
	};
});

function initialData(url) {
	if (url === "benchpress.api.get_bench_templates") return [FRAPPE_DEVELOP];
	if (url === "benchpress.user.get_ssh_keys") return savedKeys;
	return [];
}

vi.mock("@/data/labs", () => ({ labsResource: { reload: vi.fn() } }));
vi.mock("@/data/deployRun", () => ({ openDeployRun: vi.fn() }));

const { openDeployRun } = await import("@/data/deployRun");
const { toast } = await import("frappe-ui");
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
		savedKeys = SAVED_KEY;
	});

	async function remount() {
		app.unmount();
		app = createApp(Benches);
		app.mount(root);
		await nextTick();
	}

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

	it("loads the saved keys into the key card", () => {
		const input = root.querySelector('[data-test="ssh-keys-input"]');

		expect(input.value).toBe(SAVED_KEY);
		expect(root.querySelector('[data-test="ssh-keys"]').textContent).toContain(
			"~/.ssh/id_ed25519.pub"
		);
	});

	it("saves the pasted keys", async () => {
		const input = root.querySelector('[data-test="ssh-keys-input"]');
		input.value = `${SAVED_KEY}\nssh-rsa AAAA second`;
		input.dispatchEvent(new Event("input"));
		await nextTick();
		root.querySelector('[data-test="save-ssh-keys"]').click();
		await nextTick();

		expect(resources["benchpress.user.set_ssh_keys"].submit).toHaveBeenCalledWith({
			keys: `${SAVED_KEY}\nssh-rsa AAAA second`,
		});
	});

	it("will not prepare a bench until a key is saved, and says why", async () => {
		savedKeys = "";
		await remount();

		const button = root.querySelector('[data-test="prepare-bench-frappe-develop"]');
		button.click();
		await nextTick();

		expect(button.disabled).toBe(true);
		expect(resources["benchpress.api.launch_template"].submit).not.toHaveBeenCalled();
		expect(
			root.querySelector('[data-test="bench-template-frappe-develop"]').textContent
		).toContain("Add an SSH key first");
	});

	it("keeps the refusal on the card and does not report a save", async () => {
		const save = resources["benchpress.user.set_ssh_keys"];
		save.submit.mockRejectedValueOnce(new Error("Line 1 is a private key."));
		toast.success.mockClear();
		const input = root.querySelector('[data-test="ssh-keys-input"]');
		input.value = "-----BEGIN OPENSSH PRIVATE KEY-----";
		input.dispatchEvent(new Event("input"));
		await nextTick();

		root.querySelector('[data-test="save-ssh-keys"]').click();
		await nextTick();
		await nextTick();

		expect(toast.success).not.toHaveBeenCalled();
		expect(resources["benchpress.user.get_ssh_keys"].data).toBe(SAVED_KEY);
	});
});
