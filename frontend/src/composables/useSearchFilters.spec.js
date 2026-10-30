import { describe, expect, it } from "vitest";
import { ref } from "vue";
import { ALL } from "@/utils/filters";
import { useSearchFilters } from "./useSearchFilters";

const ROWS = [
	{ id: "crm", status: "Ready", apps: ["crm", "erpnext"], description: "Sales pipeline" },
	{ id: "desk", status: "Draft", apps: ["helpdesk"], description: "Support tickets" },
	{ id: "bare", status: "Ready", apps: [], description: "" },
];

function setup(rows = ROWS) {
	const source = ref(rows);
	const engine = useSearchFilters(source, {
		searchIn: (row) => [row.id, row.description],
		filters: [
			{
				key: "status",
				label: "Status",
				value: (row) => row.status,
				testId: "filter-status",
			},
			{
				key: "apps",
				label: "Apps",
				value: (row) => row.apps,
				labelFor: (app) => app.toUpperCase(),
				testId: "filter-apps",
				class: "max-w-full",
			},
		],
	});
	return { source, ...engine };
}

function ids(rows) {
	return rows.value.map((row) => row.id);
}

describe("useSearchFilters", () => {
	it("starts with the search empty and every filter on ALL", () => {
		const { search, selected, rows } = setup();
		expect(search.value).toBe("");
		expect(selected.value).toEqual({ status: ALL, apps: ALL });
		expect(ids(rows)).toEqual(["crm", "desk", "bare"]);
	});

	it("builds options through labelFor and passes each control's hook and class", () => {
		const { controls } = setup();
		expect(controls.value[0]).toEqual({
			key: "status",
			testId: "filter-status",
			class: undefined,
			options: [
				{ label: "Status: all", value: ALL },
				{ label: "Draft", value: "Draft" },
				{ label: "Ready", value: "Ready" },
			],
		});
		expect(controls.value[1].testId).toBe("filter-apps");
		expect(controls.value[1].class).toBe("max-w-full");
	});

	it("flattens list values into options and matches them by membership", () => {
		const { controls, selected, rows } = setup();
		expect(controls.value[1].options).toEqual([
			{ label: "Apps: all", value: ALL },
			{ label: "CRM", value: "crm" },
			{ label: "ERPNEXT", value: "erpnext" },
			{ label: "HELPDESK", value: "helpdesk" },
		]);
		selected.value = { ...selected.value, apps: "erpnext" };
		expect(ids(rows)).toEqual(["crm"]);
	});

	it("narrows rows by the search and every selected filter", () => {
		const { search, selected, rows } = setup();
		selected.value = { ...selected.value, status: "Ready" };
		expect(ids(rows)).toEqual(["crm", "bare"]);
		search.value = "PIPELINE";
		expect(ids(rows)).toEqual(["crm"]);
		search.value = "tickets";
		expect(ids(rows)).toEqual([]);
	});

	it("recomputes options and rows when the source rows change", () => {
		const { source, controls, rows } = setup();
		source.value = [{ id: "new", status: "Error", apps: [], description: "" }];
		expect(controls.value[0].options.map((option) => option.value)).toEqual([ALL, "Error"]);
		expect(ids(rows)).toEqual(["new"]);
	});

	it("clearFilters resets the search and every filter", () => {
		const { search, selected, rows, clearFilters } = setup();
		search.value = "crm";
		selected.value = { status: "Draft", apps: "helpdesk" };
		expect(ids(rows)).toEqual([]);
		clearFilters();
		expect(search.value).toBe("");
		expect(selected.value).toEqual({ status: ALL, apps: ALL });
		expect(ids(rows)).toEqual(["crm", "desk", "bare"]);
	});
});
