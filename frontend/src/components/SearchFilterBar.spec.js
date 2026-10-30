import { createApp, h, nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => ({
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
}));

const { default: SearchFilterBar } = await import("./SearchFilterBar.vue");

const CONTROLS = [
	{
		key: "status",
		testId: "filter-status",
		class: undefined,
		options: [
			{ label: "Status: all", value: "__all__" },
			{ label: "Draft", value: "Draft" },
		],
	},
	{
		key: "owner",
		testId: "filter-owner",
		class: "max-w-full overflow-hidden",
		options: [
			{ label: "Owner: all", value: "__all__" },
			{ label: "Administrator", value: "Administrator" },
		],
	},
];

describe("the search and filter bar", () => {
	let app;
	let root;
	let onSearch;
	let onSelected;
	let selected;

	beforeEach(async () => {
		onSearch = vi.fn();
		onSelected = vi.fn();
		selected = { status: "__all__", owner: "Administrator" };
		root = document.createElement("div");
		document.body.append(root);
		app = createApp(SearchFilterBar, {
			modelValue: "crm",
			selected,
			controls: CONTROLS,
			searchPlaceholder: "Search labs",
			searchTestId: "labs-search",
			"onUpdate:modelValue": onSearch,
			"onUpdate:selected": onSelected,
		});
		app.mount(root);
		await nextTick();
	});

	afterEach(() => {
		app.unmount();
		root.remove();
	});

	const find = (test) => root.querySelector(`[data-test="${test}"]`);

	it("puts the given hooks on the input and each select", () => {
		expect(find("labs-search").tagName).toBe("INPUT");
		expect(find("labs-search").placeholder).toBe("Search labs");
		expect(find("filter-status").tagName).toBe("SELECT");
		expect(find("filter-owner").tagName).toBe("SELECT");
	});

	it("shows the search text and each filter's selected value", () => {
		expect(find("labs-search").value).toBe("crm");
		expect(find("filter-status").value).toBe("__all__");
		expect(find("filter-owner").value).toBe("Administrator");
	});

	it("emits the typed search", () => {
		const input = find("labs-search");
		input.value = "helpdesk";
		input.dispatchEvent(new Event("input"));

		expect(onSearch).toHaveBeenCalledWith("helpdesk");
	});

	it("emits a new selected object that keeps the other filters", () => {
		const select = find("filter-status");
		select.value = "Draft";
		select.dispatchEvent(new Event("change"));

		expect(onSelected).toHaveBeenCalledWith({ status: "Draft", owner: "Administrator" });
		expect(onSelected.mock.calls[0][0]).not.toBe(selected);
		expect(selected.status).toBe("__all__");
	});

	it("passes each control's options and class to its select", () => {
		const labels = [...find("filter-owner").options].map((option) => option.textContent);

		expect(labels).toEqual(["Owner: all", "Administrator"]);
		expect(find("filter-owner").classList.contains("max-w-full")).toBe(true);
		expect(find("filter-status").className).toBe("");
	});
});
