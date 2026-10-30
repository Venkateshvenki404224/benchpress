import { createApp, h, nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => {
	const passThrough =
		(tag) =>
		(_props, { slots, attrs }) =>
			h(tag, attrs, slots.default?.());
	return {
		Button: passThrough("button"),
		Dialog: (props, { slots }) =>
			props.modelValue
				? h("div", { "data-test": "dialog", title: props.options?.title }, [
						slots["body-content"]?.(),
						slots.actions?.(),
				  ])
				: null,
		ErrorMessage: () => null,
	};
});

const { default: TemplatePreviewDialog } = await import("./TemplatePreviewDialog.vue");

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
	...CRM,
	key: "helpdesk",
	title: "Helpdesk",
	lab: { name: "helpdesk", status: "Ready" },
};

describe("the template preview dialog", () => {
	let app;
	let root;
	let emitted;

	async function mount(props) {
		emitted = {};
		root = document.createElement("div");
		document.body.append(root);
		app = createApp({
			render() {
				return h(TemplatePreviewDialog, {
					...props,
					onUse: (t) => (emitted.use = t),
					"onGo-to-lab": (t) => (emitted.goToLab = t),
					"onUpdate:modelValue": (v) => (emitted.modelValue = v),
				});
			},
		});
		app.mount(root);
		await nextTick();
	}

	const find = (test) => root.querySelector(`[data-test="${test}"]`);

	afterEach(() => {
		app.unmount();
		root.remove();
	});

	it("renders nothing when closed", async () => {
		await mount({ modelValue: false, template: CRM });
		expect(find("dialog")).toBeNull();
	});

	it("shows the template's description, apps and resources when open", async () => {
		await mount({ modelValue: true, template: CRM });
		expect(find("preview-description").textContent).toContain("sales pipeline");
		expect(find("preview-apps").textContent).toContain("CRM");
		expect(find("preview-resources").textContent).toContain("2 GB");
	});

	it("offers Use template for a template with no lab yet", async () => {
		await mount({ modelValue: true, template: CRM });
		expect(find("preview-use-template")).not.toBeNull();
		expect(find("preview-open-lab")).toBeNull();

		find("preview-use-template").click();
		expect(emitted.use).toBe(CRM);
	});

	it("offers Go to lab for a template already used", async () => {
		await mount({ modelValue: true, template: HELPDESK });
		expect(find("preview-open-lab")).not.toBeNull();
		expect(find("preview-use-template")).toBeNull();

		find("preview-open-lab").click();
		expect(emitted.goToLab).toBe(HELPDESK);
	});

	it("shows the footnote passed in", async () => {
		await mount({ modelValue: true, template: CRM, footnote: "~6 min to deploy" });
		expect(find("preview-footnote").textContent).toContain("~6 min to deploy");
	});
});
