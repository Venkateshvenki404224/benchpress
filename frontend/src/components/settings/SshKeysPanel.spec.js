import { createApp, defineComponent, h, nextTick, reactive } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const resources = {};

const ROWS = [
	{
		fingerprint: "SHA256:azc4Qc3RUbB63tfNAI4eRP/Bz/Fin7oPOwPKBrejxGk",
		type: "ssh-ed25519",
		comment: "dev@laptop",
	},
	{
		fingerprint: "SHA256:0BXSTa/ZJm5+6zmrW1yE9DGMkYbOnScPAT9ivh90sHI",
		type: "ssh-rsa",
		comment: "",
	},
];
const PASTED =
	"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGmGY6wbhu8fIW8Ss6S9Yq5Vs9esVwGK0lP9CmjKHuPv dev@laptop";

vi.mock("frappe-ui", () => {
	const passThrough =
		(tag) =>
		(_props, { slots, attrs }) =>
			h(tag, attrs, slots.default?.());
	return {
		Badge: (props) => h("span", props.label),
		Button: passThrough("button"),
		ErrorMessage: (props) =>
			props.message ? h("p", { "data-test": "error" }, String(props.message)) : null,
		Dialog: defineComponent({
			props: { modelValue: Boolean, options: Object },
			setup(props, { slots }) {
				return () =>
					props.modelValue
						? h("div", { "data-test": "dialog" }, [
								slots["body-content"]?.(),
								slots.actions?.(),
						  ])
						: null;
			},
		}),
		Textarea: defineComponent({
			props: { modelValue: String },
			emits: ["update:modelValue"],
			setup(props, { emit }) {
				return () =>
					h("textarea", {
						value: props.modelValue,
						onInput: (event) => emit("update:modelValue", event.target.value),
					});
			},
		}),
		toast: { success: vi.fn() },
		createResource: (options) => {
			const resource = reactive({
				data: null,
				fetched: false,
				loading: false,
				error: null,
				fetch: vi.fn(),
				reload: vi.fn(),
				reset: vi.fn(() => (resource.error = null)),
				setData: vi.fn((data) => (resource.data = data)),
				submit: vi.fn(async () => [...ROWS, { ...ROWS[0], comment: "new" }]),
			});
			resources[options.url] = resource;
			return resource;
		},
	};
});

const { toast } = await import("frappe-ui");
const { default: SshKeysPanel } = await import("./SshKeysPanel.vue");

const listed = () => resources["benchpress.user.list_ssh_keys"];
const addKey = () => resources["benchpress.user.add_ssh_key"];

async function settle() {
	await nextTick();
	await nextTick();
}

describe("the SSH keys panel", () => {
	let app;
	let root;

	beforeEach(async () => {
		listed().data = ROWS;
		toast.success.mockClear();
		root = document.createElement("div");
		document.body.append(root);
		app = createApp(SshKeysPanel);
		app.mount(root);
		await nextTick();
	});

	afterEach(() => {
		app.unmount();
		root.remove();
	});

	const find = (test) => root.querySelector(`[data-test="${test}"]`);

	async function openAndType(text) {
		find("add-ssh-key").click();
		await nextTick();
		const input = root.querySelector("textarea");
		input.value = text;
		input.dispatchEvent(new Event("input"));
		await nextTick();
		return input;
	}

	it("shows each key by its fingerprint and never prints the key body", () => {
		expect(find("ssh-key-0").textContent).toContain(ROWS[0].fingerprint);
		expect(find("ssh-key-0").textContent).toContain("dev@laptop");
		expect(find("ssh-key-0").textContent).toContain("ed25519");
		expect(find("ssh-key-1").textContent).toContain(ROWS[1].fingerprint);
		expect(find("ssh-key-1").textContent).toContain("rsa");
		expect(root.textContent).not.toContain("AAAA");
	});

	it("adds the pasted key and closes the dialog", async () => {
		const input = await openAndType("");
		expect(find("save-ssh-key").disabled).toBe(true);

		input.value = PASTED;
		input.dispatchEvent(new Event("input"));
		await nextTick();
		find("save-ssh-key").click();
		await settle();

		expect(addKey().submit).toHaveBeenCalledWith({ key: PASTED });
		expect(find("dialog")).toBeNull();
		expect(find("ssh-key-2").textContent).toContain("new");
		expect(toast.success).toHaveBeenCalledWith("SSH key added.");
	});

	it("keeps the dialog and the draft when the key is refused", async () => {
		addKey().submit.mockImplementationOnce(async () => {
			addKey().error = "Line 1 is a private key. Paste the .pub file instead.";
			throw new Error(addKey().error);
		});
		await openAndType("-----BEGIN OPENSSH PRIVATE KEY-----");

		find("save-ssh-key").click();
		await settle();

		expect(find("dialog")).not.toBeNull();
		expect(root.querySelector("textarea").value).toBe("-----BEGIN OPENSSH PRIVATE KEY-----");
		expect(find("error").textContent).toContain("Line 1 is a private key");
		expect(toast.success).not.toHaveBeenCalled();
	});

	it("clears the last refusal when the dialog opens again", async () => {
		addKey().error = "That key is already saved.";

		find("add-ssh-key").click();
		await nextTick();

		expect(addKey().reset).toHaveBeenCalled();
		expect(find("error")).toBeNull();
	});

	it("says the keys are loading until they arrive", async () => {
		listed().data = null;
		listed().loading = true;
		await nextTick();

		expect(root.textContent).toContain("Loading keys…");
		expect(root.textContent).not.toContain("No SSH key yet");

		listed().loading = false;
		listed().data = [];
		await nextTick();

		expect(root.textContent).not.toContain("Loading keys…");
	});

	it("says why the keys could not load", async () => {
		listed().data = null;
		listed().error = "Not permitted";
		await nextTick();

		expect(find("error").textContent).toContain("Not permitted");
		listed().error = null;
	});

	it("says what to add when there are no keys", async () => {
		listed().data = [];
		await nextTick();

		expect(root.textContent).toContain("No SSH key yet");
		expect(find("ssh-key-0")).toBeNull();
	});
});
