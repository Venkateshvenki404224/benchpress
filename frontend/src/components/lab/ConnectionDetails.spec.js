import { createApp, h, nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => {
	const passThrough =
		(tag) =>
		(_props, { slots, attrs }) =>
			h(tag, attrs, slots.default?.());
	return {
		Button: passThrough("button"),
		FormControl: (_props, { attrs }) =>
			h("input", { "data-test": attrs["data-test"], value: attrs["model-value"] }),
		Tooltip: passThrough("span"),
	};
});

const { default: ConnectionDetails } = await import("./ConnectionDetails.vue");

const BENCH = { ssh_username: "dev", wg_ip: "10.99.0.7", addresses: {} };

describe("the connection details", () => {
	let app;
	let root;

	async function mount(lab) {
		root = document.createElement("div");
		document.body.append(root);
		app = createApp(ConnectionDetails, {
			lab,
			bench: BENCH,
			credentials: { ssh_password: "s3cret" },
		});
		app.mount(root);
		await nextTick();
	}

	afterEach(() => {
		app.unmount();
		root.remove();
	});

	it("shows the saved key in place of a password on a self-managed bench", async () => {
		await mount({ self_managed: 1 });

		expect(root.querySelector('[data-test="detail-ssh-password"]')).toBeNull();
		expect(root.querySelector('[data-test="detail-ssh-key"]').textContent).toContain(
			"your saved key"
		);
		expect(root.querySelector('[data-test="detail-ssh"]').textContent).toContain(
			"ssh dev@10.99.0.7"
		);
	});

	it("keeps the SSH password on an ordinary lab", async () => {
		await mount({ self_managed: 0 });

		expect(root.querySelector('[data-test="detail-ssh-key"]')).toBeNull();
		expect(root.querySelector('[data-test="secret-ssh-password"]').value).toBe("s3cret");
	});
});
