<template>
	<div class="animate-fade-up">
		<div class="flex items-center justify-between mb-8">
			<div>
				<h1 class="text-2xl font-bold text-bp-text">Benches</h1>
				<p class="text-bp-muted text-sm mt-1">
					{{ runningCount }} running · {{ benches.length }} total
				</p>
			</div>
		</div>

		<div v-if="loading" class="text-bp-muted text-center py-12">Loading benches...</div>
		<div v-else-if="benches.length === 0" class="text-center py-12">
			<p class="text-bp-muted mb-4">No benches deployed yet</p>
			<router-link to="/dashboard" class="btn-primary">Go to Labs to deploy</router-link>
		</div>
		<div v-else class="space-y-3">
			<router-link
				v-for="bench in benches"
				:key="bench.name"
				:to="`/dashboard/bench/${bench.name}`"
				class="block"
			>
				<GlassCard class="hover:-translate-y-0.5 transition-transform">
					<div class="flex items-center justify-between">
						<div class="flex items-center gap-3">
							<StatusDot :status="bench.status?.toLowerCase() || 'stopped'" />
							<div>
								<h3 class="text-bp-text font-medium">
									{{ bench.bench_name || bench.name }}
								</h3>
								<div class="flex items-center gap-3 text-xs text-bp-dim mt-0.5">
									<span class="px-1.5 py-0.5 rounded bg-white/5">{{
										bench.frappe_version || "v15"
									}}</span>
									<span v-if="bench.wg_ip">{{ bench.wg_ip }}</span>
									<span v-if="bench.lab">{{ bench.lab }}</span>
								</div>
							</div>
						</div>
						<div class="flex items-center gap-6">
							<div class="w-24 hidden sm:block">
								<StatBar label="CPU" :value="bench.cpu_usage || 0" />
							</div>
							<div class="w-24 hidden sm:block">
								<StatBar
									label="RAM"
									:value="bench.memory_usage || 0"
									color="cyan"
								/>
							</div>
							<span
								class="text-xs font-medium px-2 py-1 rounded"
								:class="statusBadgeClass(bench.status)"
							>
								{{ bench.status }}
							</span>
						</div>
					</div>
				</GlassCard>
			</router-link>
		</div>
	</div>
</template>

<script setup>
import { ref, inject, onMounted, computed } from "vue";
import GlassCard from "@/components/GlassCard.vue";
import StatusDot from "@/components/StatusDot.vue";
import StatBar from "@/components/StatBar.vue";

const $call = inject("$call");
const benches = ref([]);
const loading = ref(true);

const runningCount = computed(() => benches.value.filter((b) => b.status === "Running").length);

async function fetchBenches() {
	loading.value = true;
	try {
		benches.value = await $call("benchpress.api.get_benches");
	} catch (e) {
		console.error("Failed to fetch benches:", e);
	}
	loading.value = false;
}

function statusBadgeClass(status) {
	const map = {
		Running: "bg-bp-green/10 text-bp-green",
		Stopped: "bg-white/5 text-bp-muted",
		Deploying: "bg-bp-amber/10 text-bp-amber",
		Error: "bg-bp-red/10 text-bp-red",
		Draft: "bg-white/5 text-bp-dim",
	};
	return map[status] || map.Draft;
}

onMounted(fetchBenches);
</script>
