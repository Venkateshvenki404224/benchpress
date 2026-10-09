import { createApp, h, nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => ({
	Badge: () => null,
	Button: (_props, { slots, attrs }) => h("button", attrs, slots.default?.()),
	ConfirmDialog: (props) => h("div", { "data-test": "confirm-message" }, props.message),
	Dropdown: () => null,
}));

const { default: LabHeader } = await import("./LabHeader.vue");

const BENCH = { status: "Draft", container_id: "abc123" };

describe("the redeploy confirmation", () => {
	let app;
	let root;

	async function confirmRedeploy(lab) {
		root = document.createElement("div");
		document.body.append(root);
		app = createApp(LabHeader, { lab: { status: "Ready", ...lab }, bench: BENCH });
		app.mount(root);
		root.querySelector('[data-test="primary-action"]').click();
		await nextTick();
		return root.querySelector('[data-test="confirm-message"]').textContent;
	}

	afterEach(() => {
		app.unmount();
		root.remove();
	});

	it("warns that a lab loses its site database", async () => {
		const message = await confirmRedeploy({ self_managed: 0 });

		expect(message).toContain("the site database — is destroyed");
	});

	it("tells a self-managed bench its databases are kept and its site folders are not", async () => {
		const message = await confirmRedeploy({ self_managed: 1 });

		expect(message).toContain("Your databases are kept");
		expect(message).toContain("~/frappe-bench/sites");
		expect(message).not.toContain("site database");
	});
});
