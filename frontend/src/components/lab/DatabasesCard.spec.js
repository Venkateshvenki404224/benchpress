import { createApp, h, nextTick, reactive } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const resources = {};

const CREATED = {
	db_name: "bp_dev_1a2b3c4d",
	db_user: "bp_dev_1a2b3c4d",
	db_password: "fresh-password",
	command: "bench new-site bp-dev-1a2b3c4d.localhost --db-password fresh-password",
};

const REVEALED = {
	db_password: "old-password",
	command: "bench new-site bp-dev-old00000.localhost --db-password old-password",
};

vi.mock("frappe-ui", () => {
	const passThrough =
		(tag) =>
		(_props, { slots, attrs }) =>
			h(tag, attrs, slots.default?.());
	return {
		Button: passThrough("button"),
		ErrorMessage: () => null,
		Tooltip: passThrough("span"),
		createResource: (options) => {
			const resource = reactive({
				data: null,
				loading: false,
				error: null,
				submit: vi.fn(async () =>
					options.url === "benchpress.api.create_bench_database" ? CREATED : REVEALED
				),
			});
			resources[options.url] = resource;
			return resource;
		},
	};
});

const { default: DatabasesCard } = await import("./DatabasesCard.vue");

const BENCH = {
	name: "b1",
	database_limit: 5,
	databases: [{ db_name: "bp_dev_old00000", db_user: "bp_dev_old00000" }],
};

async function settle() {
	await nextTick();
	await nextTick();
}

describe("the databases card", () => {
	let app;
	let root;
	let created;

	beforeEach(async () => {
		created = vi.fn();
		root = document.createElement("div");
		document.body.append(root);
		app = createApp(DatabasesCard, { bench: BENCH, onCreated: created });
		app.mount(root);
		await nextTick();
	});

	afterEach(() => {
		app.unmount();
		root.remove();
	});

	it("lists each database with its user and no password", () => {
		const row = root.querySelector('[data-test="database-bp_dev_old00000"]');

		expect(row.textContent).toContain("bp_dev_old00000");
		expect(root.textContent).not.toContain("old-password");
	});

	it("shows how many databases are left", () => {
		expect(root.querySelector('[data-test="databases-left"]').textContent.trim()).toBe(
			"4 of 5 left"
		);
	});

	it("counts a new database before the lab reloads", async () => {
		root.querySelector('[data-test="create-database"]').click();
		await settle();

		expect(root.querySelector('[data-test="databases-left"]').textContent.trim()).toBe(
			"3 of 5 left"
		);
	});

	it("creates a database and shows its password and command", async () => {
		root.querySelector('[data-test="create-database"]').click();
		await settle();

		expect(resources["benchpress.api.create_bench_database"].submit).toHaveBeenCalledWith({
			bench: "b1",
		});
		expect(root.querySelector('[data-test="database-password"]').textContent).toContain(
			"fresh-password"
		);
		expect(root.querySelector('[data-test="database-command"]').textContent).toContain(
			CREATED.command
		);
		expect(created).toHaveBeenCalled();
	});

	it("shows an existing database's password and command on request", async () => {
		root.querySelector('[data-test="show-bp_dev_old00000"]').click();
		await settle();

		expect(
			resources["benchpress.api.get_bench_database_password"].submit
		).toHaveBeenCalledWith({ bench: "b1", db_name: "bp_dev_old00000" });
		expect(root.querySelector('[data-test="database-command"]').textContent).toContain(
			REVEALED.command
		);
	});

	it("keeps quiet when the create is refused", async () => {
		resources["benchpress.api.create_bench_database"].submit.mockRejectedValueOnce(
			new Error("This bench already has 5 databases")
		);

		root.querySelector('[data-test="create-database"]').click();
		await settle();

		expect(root.querySelector('[data-test="database-command"]')).toBeNull();
		expect(created).not.toHaveBeenCalled();
	});
});
