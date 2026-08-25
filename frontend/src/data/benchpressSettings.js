import { createDocumentResource, dayjsLocal, toast } from "frappe-ui";
import { computed, reactive, ref } from "vue";

import ContainerIcon from "~icons/lucide/container";
import CpuIcon from "~icons/lucide/cpu";
import GlobeIcon from "~icons/lucide/globe";
import NetworkIcon from "~icons/lucide/network";

/** Each group is one nav item and one panel in the settings dialog. */
export const SETTINGS_GROUPS = [
	{
		key: "group-domains",
		tab: "domains",
		title: "Domains",
		icon: GlobeIcon,
		note: "How sites are addressed on the private network.",
		fields: [
			{
				key: "base_domain",
				label: "Base domain",
				mono: true,
				placeholder: "bp.local",
				help: "Sites resolve as <site>.<base domain>",
			},
			{
				key: "default_image",
				label: "Default image",
				mono: true,
				help: "Used when a lab has no image of its own",
			},
		],
	},
	{
		key: "group-docker",
		tab: "docker",
		title: "Docker",
		icon: ContainerIcon,
		note: "Where BenchPress talks to the daemon.",
		fields: [
			{ key: "docker_socket", label: "Docker socket", mono: true },
			{
				key: "traefik_network",
				label: "Traefik network",
				mono: true,
				help: "Containers join this network",
			},
		],
	},
	{
		key: "group-network",
		tab: "network",
		title: "Bench network",
		icon: NetworkIcon,
		note: "The bridge family new benches are placed on. Bridges are created as they are needed.",
		fields: [
			{
				key: "bench_subnet_base",
				label: "Subnet base",
				mono: true,
				help: "Bridge i is <base>.<i×16>.0/20",
			},
			{
				key: "bench_bridge_count",
				label: "Bridge count",
				type: "number",
				help: "The most bridges the family may grow to",
			},
			{
				key: "bench_slots_per_bridge",
				label: "Slots per bridge",
				type: "number",
				help: "Benches a bridge takes before the next one is preferred — a Linux bridge caps at 1024 ports",
			},
		],
	},
	{
		key: "group-container",
		tab: "container",
		title: "Container defaults",
		icon: CpuIcon,
		note: "Applied to new labs unless overridden.",
		fields: [
			{ key: "container_memory_limit", label: "Memory limit", help: "e.g. 512m, 1g, 2g" },
			{
				key: "container_cpu_quota",
				label: "CPU quota",
				type: "number",
				help: "Microseconds — 100000 is one core",
			},
			{ key: "code_server_version", label: "Code server version", mono: true },
		],
	},
];

const FIELDS = SETTINGS_GROUPS.flatMap((group) => group.fields.map((field) => field.key));

// `base_domain` is `reqd` on the DocType, so the form refuses an empty one
// rather than letting the save come back as a server throw.
const REQUIRED = { base_domain: "A base domain is required — sites are addressed under it." };

export const isSettingsOpen = ref(false);
export const form = reactive(Object.fromEntries(FIELDS.map((field) => [field, ""])));

// Only admins can read the doctype, so nothing is fetched until the dialog is
// opened from the account menu, which is admin-only.
export const settingsResource = createDocumentResource({
	doctype: "BenchPress Settings",
	name: "BenchPress Settings",
	auto: false,
	onSuccess: fillForm,
	setValue: {
		onSuccess() {
			toast.success("Settings saved.");
		},
	},
});

export function openSettings() {
	settingsResource.reload();
	isSettingsOpen.value = true;
}

export const isDirty = computed(() =>
	FIELDS.some(
		(field) => String(form[field] ?? "") !== String(settingsResource.doc?.[field] ?? "")
	)
);

/** Who last changed the server's defaults, and when. */
export const lastSaved = computed(() => {
	const doc = settingsResource.doc;
	if (!doc?.modified) return "Never saved";
	return `Last saved by ${doc.modified_by}, ${dayjsLocal(doc.modified).format("D MMMM")}`;
});

export function errorFor(field) {
	return String(form[field] ?? "").trim() ? "" : REQUIRED[field] ?? "";
}

export function saveSettings() {
	const missing = FIELDS.map(errorFor).filter(Boolean);
	if (missing.length) {
		toast.error(missing[0]);
		return;
	}
	settingsResource.setValue.submit({ ...form });
}

export function discardSettings() {
	if (settingsResource.doc) fillForm(settingsResource.doc);
}

function fillForm(doc) {
	for (const field of FIELDS) {
		form[field] = doc[field] ?? "";
	}
}
