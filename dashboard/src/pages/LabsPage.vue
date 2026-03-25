<template>
	<div class="animate-fade-up">
		<div class="flex items-center justify-between mb-8">
			<div>
				<h1 class="text-2xl font-bold text-bp-text">Labs</h1>
				<p class="text-bp-muted text-sm mt-1">
					Pre-configured bench templates ready to deploy
				</p>
			</div>
			<a href="/app/lab/new" class="btn-primary">+ New Lab</a>
		</div>

		<div v-if="loading" class="text-bp-muted text-center py-12">Loading labs...</div>
		<div v-else-if="labs.length === 0" class="text-center py-12">
			<p class="text-bp-muted mb-4">No labs created yet</p>
			<a href="/app/lab/new" class="btn-primary">Create your first lab</a>
		</div>
		<div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
			<GlassCard
				v-for="lab in labs"
				:key="lab.name"
				:shimmer="lab.status === 'Ready'"
				class="cursor-pointer hover:-translate-y-0.5 transition-transform"
			>
				<div class="flex items-start justify-between mb-4">
					<div>
						<h3 class="text-lg font-semibold text-bp-text">
							{{ lab.title || lab.lab_id }}
						</h3>
						<p class="text-bp-muted text-sm">{{ lab.frappe_version }}</p>
					</div>
					<span
						class="px-2 py-0.5 rounded text-xs font-medium"
						:class="statusClass(lab.status)"
					>
						{{ lab.status }}
					</span>
				</div>
				<div class="flex items-center gap-4 text-sm text-bp-dim mb-4">
					<span>{{ lab.app_count || 0 }} apps</span>
					<span>{{ lab.memory_limit || "512m" }} RAM</span>
					<span>{{ lab.cpu_cores || 1 }} CPU</span>
				</div>
				<div class="flex gap-2">
					<router-link
						:to="`/dashboard/deploy/${lab.name}`"
						class="btn-primary text-xs"
						v-if="lab.status === 'Ready'"
					>
						Deploy
					</router-link>
					<button
						@click.stop="buildImage(lab.name)"
						class="btn-secondary text-xs"
						:disabled="lab.status === 'Building'"
					>
						{{ lab.status === "Building" ? "Building..." : "Build Image" }}
					</button>
				</div>
			</GlassCard>
		</div>
	</div>
</template>

<script setup>
import { ref, inject, onMounted } from "vue";
import GlassCard from "@/components/GlassCard.vue";

const $call = inject("$call");
const labs = ref([]);
const loading = ref(true);

async function fetchLabs() {
	loading.value = true;
	try {
		labs.value = await $call("benchpress.api.get_labs");
	} catch (e) {
		console.error("Failed to fetch labs:", e);
	}
	loading.value = false;
}

async function buildImage(labName) {
	try {
		await $call("benchpress.api.build_lab_image", { lab_name: labName });
		// Refresh to see updated status
		await fetchLabs();
	} catch (e) {
		console.error("Build failed:", e);
	}
}

function statusClass(status) {
	const map = {
		Ready: "bg-bp-green/10 text-bp-green",
		Building: "bg-bp-amber/10 text-bp-amber",
		Draft: "bg-white/5 text-bp-muted",
		Error: "bg-bp-red/10 text-bp-red",
	};
	return map[status] || map.Draft;
}

onMounted(fetchLabs);
</script>
