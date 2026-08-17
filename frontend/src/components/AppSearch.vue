<template>
	<button
		type="button"
		class="flex h-7 items-center gap-2 rounded-control border border-outline-gray-1 px-2.5 text-2xs text-ink-gray-5 hover:bg-surface-gray-2"
		data-test="search-trigger"
		@click="open()"
	>
		<SearchIcon class="size-3.5" />
		Search
		<kbd class="font-sans text-ink-gray-4">{{ shortcut }}</kbd>
	</button>

	<Dialog v-model="show" :options="{ size: 'xl', position: 'top' }">
		<template #body>
			<div data-test="search-palette">
				<div class="flex items-center gap-3 px-4">
					<SearchIcon class="size-4 flex-none text-ink-gray-4" />
					<input
						ref="input"
						v-model="query"
						type="text"
						class="w-full border-none bg-transparent py-3.5 text-base text-ink-gray-8 placeholder-ink-gray-4 focus:ring-0"
						placeholder="Search labs and instances"
						autocomplete="off"
						data-test="search-input"
						@keydown.down.prevent="move(1)"
						@keydown.up.prevent="move(-1)"
						@keydown.enter.prevent="choose(results[active])"
					/>
				</div>

				<div class="max-h-96 overflow-auto border-t border-outline-gray-1 py-2">
					<template v-for="group in groups" :key="group.title">
						<p class="px-4 py-1.5 text-2xs text-ink-gray-5">{{ group.title }}</p>
						<button
							v-for="item in group.items"
							:key="item.key"
							type="button"
							class="flex w-full items-center gap-3 px-4 py-2 text-left text-body text-ink-gray-8"
							:class="item === results[active] ? 'bg-surface-gray-2' : ''"
							:data-test="`search-result-${item.key}`"
							@click="choose(item)"
							@mousemove="active = results.indexOf(item)"
						>
							<component :is="item.icon" class="size-4 flex-none text-ink-gray-6" />
							<span class="truncate">{{ item.title }}</span>
							<span class="ml-auto truncate pl-3 text-2xs text-ink-gray-5">
								{{ item.description }}
							</span>
						</button>
					</template>

					<p
						v-if="!results.length"
						class="px-4 py-6 text-center text-body text-ink-gray-5"
					>
						Nothing matches “{{ query }}”.
					</p>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
// The palette searches the same two resources the Labs and Instances pages
// render, so the server scopes it exactly as it scopes those tables — it can
// never surface a lab or a bench the session user may not read.
//
// frappe-ui ships a `CommandPalette`, but in 0.1.278 it binds its search box
// with `v-model` on headlessui's `ComboboxInput`, which declares no
// `modelValue` prop — the typed text never reaches its `searchQuery`, so the
// list cannot filter. The same Dialog-plus-input shape is built here instead.
import { benchesResource } from "@/data/benches";
import { labsResource } from "@/data/labs";
import { benchLabel } from "@/utils/labSpecs";
import { Dialog } from "frappe-ui";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import FlaskConicalIcon from "~icons/lucide/flask-conical";
import SearchIcon from "~icons/lucide/search";
import ServerIcon from "~icons/lucide/server";

const RESULTS_PER_GROUP = 6;

const router = useRouter();
const show = ref(false);
const query = ref("");
const active = ref(0);
const input = ref(null);

const shortcut = computed(() =>
	/Mac|iPhone|iPad/.test(navigator.platform ?? "") ? "⌘K" : "Ctrl K"
);

const groups = computed(() =>
	[
		{ title: "Labs", items: labItems.value },
		{ title: "Instances", items: benchItems.value },
	].filter((group) => group.items.length)
);

/** One flat list so the arrow keys can walk across the group headings. */
const results = computed(() => groups.value.flatMap((group) => group.items));

const labItems = computed(() =>
	matching(labsResource.data, (lab) => ({
		key: `lab-${lab.name}`,
		title: lab.title || lab.lab_id,
		description: lab.lab_id,
		icon: FlaskConicalIcon,
		haystack: [lab.title, lab.lab_id, ...(lab.app_names ?? [])],
		route: { name: "LabDetail", params: { labId: lab.name } },
	}))
);

const benchItems = computed(() =>
	matching(benchesResource.data, (bench) => ({
		key: `bench-${bench.name}`,
		title: benchLabel(bench.lab),
		description: bench.status,
		icon: ServerIcon,
		haystack: [bench.lab, bench.domain, bench.site_name, bench.wg_ip],
		route: { name: "LabDetail", params: { labId: bench.lab } },
	}))
);

function matching(rows, toItem) {
	const needle = query.value.trim().toLowerCase();
	return (rows ?? [])
		.map(toItem)
		.filter((item) => !needle || item.haystack.some((value) => hit(value, needle)))
		.slice(0, RESULTS_PER_GROUP);
}

function hit(value, needle) {
	return (value || "").toLowerCase().includes(needle);
}

watch(query, () => {
	active.value = 0;
});

async function open() {
	show.value = true;
	ensureLoaded();
	await nextTick();
	input.value?.focus();
}

// Both resources are shared with the pages that render them, so opening the
// palette from Labs or Instances costs nothing; from anywhere else it fetches
// the one list it is missing rather than on every page load.
function ensureLoaded() {
	if (!labsResource.data) labsResource.reload();
	if (!benchesResource.data) benchesResource.reload();
}

function move(step) {
	if (!results.value.length) return;
	active.value = (active.value + step + results.value.length) % results.value.length;
}

function choose(item) {
	if (!item) return;
	show.value = false;
	query.value = "";
	router.push(item.route);
}

function onKeydown(event) {
	if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
		event.preventDefault();
		open();
	}
}

onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>
