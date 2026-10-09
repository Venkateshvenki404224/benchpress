import { createApp, defineComponent, h, nextTick, reactive } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const settingsDoc = reactive({ doc: null });

vi.mock("frappe-ui", () => {
	const passThrough =
		(tag) =>
		(_props, { slots, attrs }) =>
			h(tag, attrs, slots.default?.());
	return {
		Button: passThrough("button"),
		ErrorMessage: () => null,
		FormControl: passThrough("input"),
		Dialog: defineComponent({
			props: { modelValue: Boolean, options: Object },
			setup(props, { slots }) {
				return () => (props.modelValue ? h("div", slots.body?.()) : null);
			},
		}),
		dayjsLocal: () => ({ format: () => "1 September" }),
		toast: { success: vi.fn(), error: vi.fn() },
		createDocumentResource: () =>
			reactive({
				get doc() {
					return settingsDoc.doc;
				},
				reload: vi.fn(),
				setValue: { submit: vi.fn(), loading: false, error: null },
			}),
	};
});

vi.mock("vue-router", () => ({
	useRoute: () => ({ name: "Overview" }),
	useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("@/data/userContext", async () => {
	const { reactive } = await import("vue");
	return {
		userContext: reactive({ isAdmin: false, ready: true }),
		waitForUserContext: () => Promise.resolve(),
	};
});

vi.mock("@/components/settings/SshKeysPanel.vue", async () => {
	const { h } = await import("vue");
	return { default: { render: () => h("div", { "data-test": "ssh-keys-panel" }) } };
});

const { userContext } = await import("@/data/userContext");
const { isSettingsOpen, openSettings, settingsResource } = await import(
	"@/data/benchpressSettings"
);
const { default: SettingsDialog } = await import("./SettingsDialog.vue");

describe("the settings dialog", () => {
	let app;
	let root;

	beforeEach(() => {
		settingsDoc.doc = { base_domain: "bp.local", modified: "2026-09-01" };
		settingsResource.reload.mockClear();
		root = document.createElement("div");
		document.body.append(root);
		app = createApp(SettingsDialog);
		app.mount(root);
	});

	afterEach(() => {
		isSettingsOpen.value = false;
		app.unmount();
		root.remove();
	});

	const find = (test) => root.querySelector(`[data-test="${test}"]`);

	async function open(asAdmin, group) {
		userContext.isAdmin = asAdmin;
		await openSettings(group);
		await nextTick();
	}

	it("gives a non-admin only their SSH keys", async () => {
		await open(false);

		const nav = root.querySelector("nav").textContent;
		expect(nav).toContain("Account");
		expect(nav).toContain("SSH keys");
		expect(nav).not.toContain("Server");
		expect(find("ssh-keys-panel")).not.toBeNull();
		expect(find("save-settings")).toBeNull();
		expect(settingsResource.reload).not.toHaveBeenCalled();
	});

	it("gives an admin the SSH keys first and the server groups after", async () => {
		await open(true);

		const nav = root.querySelector("nav").textContent;
		expect(nav.indexOf("Account")).toBeLessThan(nav.indexOf("Server"));
		expect(find("ssh-keys-panel")).not.toBeNull();
		expect(find("save-settings")).toBeNull();
		expect(settingsResource.reload).toHaveBeenCalled();

		find("tab-domains").click();
		await nextTick();

		expect(find("ssh-keys-panel")).toBeNull();
		expect(find("base_domain")).not.toBeNull();
		expect(find("save-settings")).not.toBeNull();
	});

	it("keeps a non-admin on SSH keys when a server group is asked for", async () => {
		await open(false, "group-domains");

		expect(find("tab-domains")).toBeNull();
		expect(find("ssh-keys-panel")).not.toBeNull();
		expect(find("base_domain")).toBeNull();
		expect(find("save-settings")).toBeNull();
	});
});
