<template>
	<div class="mx-auto max-w-[760px] px-6 pb-10 pt-[22px]" data-test="settings">
		<div class="mb-4">
			<h1 class="text-title font-semibold text-ink-gray-9">Settings</h1>
			<p class="mt-0.5 max-w-[560px] text-body text-ink-gray-5">
				Server-wide defaults. Changing them affects benches deployed from now on, not ones
				already running.
			</p>
		</div>

		<p v-if="!settings.doc" class="text-body text-ink-gray-5">Loading settings…</p>

		<template v-else>
			<div class="flex flex-col gap-4">
				<SectionCard v-for="group in GROUPS" :key="group.title" :data-test="group.key">
					<h2 class="text-sm font-semibold text-ink-gray-9">{{ group.title }}</h2>
					<p class="mt-0.5 text-xs text-ink-gray-5">{{ group.note }}</p>

					<div
						class="mt-3.5 grid gap-3.5"
						style="grid-template-columns: repeat(auto-fit, minmax(210px, 1fr))"
					>
						<div v-for="field in group.fields" :key="field.key">
							<FormControl
								:label="field.label"
								:type="field.type ?? 'text'"
								:class="field.mono ? '[&_input]:font-mono [&_input]:text-xs' : ''"
								v-model="form[field.key]"
								:placeholder="field.placeholder"
								:data-test="field.key"
							/>
							<p v-if="field.help" class="mt-1.5 text-2xs text-ink-gray-5">
								{{ field.help }}
							</p>
							<ErrorMessage class="mt-1" :message="errorFor(field.key)" />
						</div>
					</div>
				</SectionCard>
			</div>

			<div
				class="mt-4 flex flex-wrap items-center gap-2.5 rounded-card border border-outline-gray-1 bg-surface-white px-4 py-3"
			>
				<span class="text-xs text-ink-gray-5" data-test="last-saved">{{ lastSaved }}</span>
				<div class="ml-auto flex items-center gap-2">
					<Button
						variant="subtle"
						:disabled="!isDirty"
						data-test="discard-settings"
						@click="discard"
					>
						Discard
					</Button>
					<Button
						variant="solid"
						:loading="settings.setValue.loading"
						:disabled="!isDirty"
						data-test="save-settings"
						@click="save"
					>
						Save settings
					</Button>
				</div>
			</div>

			<ErrorMessage class="mt-2" :message="settings.setValue.error" />
		</template>
	</div>
</template>

<script setup>
// Settings used to be a page whose entire body was a dialog opened on arrival,
// closing back to /labs through a watcher — a modal over nothing. It is a page
// now: three grouped cards on a narrow column and one save bar.
//
// `base_domain` is `reqd` on the DocType, so the form refuses an empty one
// rather than letting the save come back as a server throw.
import SectionCard from "@/components/SectionCard.vue";
import {
	Button,
	ErrorMessage,
	FormControl,
	createDocumentResource,
	dayjsLocal,
	toast,
} from "frappe-ui";
import { computed, reactive } from "vue";

const GROUPS = [
	{
		key: "group-domains",
		title: "Domains",
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
		title: "Docker",
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
		key: "group-container",
		title: "Container defaults",
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

const FIELDS = GROUPS.flatMap((group) => group.fields.map((field) => field.key));
const REQUIRED = { base_domain: "A base domain is required — sites are addressed under it." };

const form = reactive(Object.fromEntries(FIELDS.map((field) => [field, ""])));

const settings = createDocumentResource({
	doctype: "BenchPress Settings",
	name: "BenchPress Settings",
	auto: true,
	onSuccess: fillForm,
	setValue: {
		onSuccess() {
			toast.success("Settings saved.");
		},
	},
});

function fillForm(doc) {
	for (const field of FIELDS) {
		form[field] = doc[field] ?? "";
	}
}

const isDirty = computed(() =>
	FIELDS.some((field) => String(form[field] ?? "") !== String(settings.doc?.[field] ?? ""))
);

/** Who last changed the server's defaults, and when. */
const lastSaved = computed(() => {
	const doc = settings.doc;
	if (!doc?.modified) return "Never saved";
	return `Last saved by ${doc.modified_by}, ${dayjsLocal(doc.modified).format("D MMMM")}`;
});

function errorFor(field) {
	return String(form[field] ?? "").trim() ? "" : REQUIRED[field] ?? "";
}

function save() {
	const missing = FIELDS.map(errorFor).filter(Boolean);
	if (missing.length) {
		toast.error(missing[0]);
		return;
	}
	settings.setValue.submit({ ...form });
}

function discard() {
	if (settings.doc) fillForm(settings.doc);
}
</script>
