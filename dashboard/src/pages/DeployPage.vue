<template>
	<div class="animate-fade-up max-w-3xl mx-auto">
		<router-link
			to="/dashboard"
			class="text-bp-muted hover:text-bp-text text-sm mb-6 inline-flex items-center gap-1"
		>
			← Back to Labs
		</router-link>

		<h1 class="text-2xl font-bold text-bp-text mb-2">Deploy Bench</h1>
		<p class="text-bp-muted text-sm mb-8" v-if="lab">
			From <span class="text-bp-green">{{ lab.title || lab.lab_id }}</span> ·
			{{ lab.frappe_version }}
		</p>

		<!-- Deploy Form -->
		<GlassCard v-if="!deploying && !deployDone" class="mb-6">
			<div class="space-y-4">
				<div>
					<label class="text-sm text-bp-muted mb-1 block">Lab</label>
					<div class="text-bp-text">{{ lab?.title || labId }}</div>
				</div>
				<div v-if="lab?.apps?.length">
					<label class="text-sm text-bp-muted mb-1 block">Apps to install</label>
					<div class="flex flex-wrap gap-2">
						<span
							v-for="app in lab.apps"
							:key="app.app_name"
							class="px-2 py-1 rounded text-xs bg-white/5 text-bp-muted"
						>
							{{ app.app_name }}
						</span>
					</div>
				</div>
				<button
					@click="startDeploy"
					class="btn-primary w-full py-3 text-center"
					:disabled="!lab"
				>
					Deploy Bench
				</button>
			</div>
		</GlassCard>

		<!-- Deploy Terminal -->
		<div v-if="deploying || deployDone">
			<GlassCard class="mb-4">
				<div class="flex items-center gap-3 mb-4">
					<StatusDot
						:status="deployDone ? (deployError ? 'error' : 'running') : 'deploying'"
					/>
					<span class="font-medium text-bp-text">
						{{
							deployDone
								? deployError
									? "Deploy Failed"
									: "Deploy Complete"
								: "Deploying..."
						}}
					</span>
				</div>
				<Terminal :lines="logLines" />
			</GlassCard>

			<div v-if="deployDone && !deployError" class="flex gap-3">
				<router-link to="/dashboard/benches" class="btn-primary">View Benches</router-link>
				<router-link
					v-if="benchName"
					:to="`/dashboard/bench/${benchName}`"
					class="btn-secondary"
					>Bench Detail</router-link
				>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, inject, onMounted, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import GlassCard from "@/components/GlassCard.vue";
import StatusDot from "@/components/StatusDot.vue";
import Terminal from "@/components/Terminal.vue";

const $call = inject("$call");
const $socket = inject("$socket");
const route = useRoute();

const labId = route.params.lab;
const lab = ref(null);
const deploying = ref(false);
const deployDone = ref(false);
const deployError = ref(false);
const benchName = ref("");
const logLines = ref([]);

async function fetchLab() {
	try {
		lab.value = await $call("benchpress.api.get_lab", { name: labId });
	} catch (e) {
		console.error("Failed to fetch lab:", e);
	}
}

async function startDeploy() {
	deploying.value = true;
	logLines.value = [
		{ message: "Starting deployment...", type: "info", timestamp: new Date().toISOString() },
	];
	try {
		const result = await $call("benchpress.api.create_bench", { data: JSON.stringify({ lab: labId }) });
		benchName.value = result?.bench_name || result?.name || "";
	} catch (e) {
		logLines.value.push({ message: `Error: ${e.message || e}`, type: "error" });
		deployError.value = true;
		deployDone.value = true;
	}
}

function onDeployLog(data) {
	if (data.bench === benchName.value || !benchName.value) {
		logLines.value.push({
			message: data.log || data.message,
			type: data.type || data.log_type || "info",
			timestamp: data.timestamp,
		});
		if (data.type === "success" || data.log_type === "success") {
			deployDone.value = true;
		}
		if (data.type === "error" || data.log_type === "error") {
			deployError.value = true;
			deployDone.value = true;
		}
	}
}

onMounted(() => {
	fetchLab();
	$socket.on("bench_deploy_log", onDeployLog);
});

onUnmounted(() => {
	$socket.off("bench_deploy_log", onDeployLog);
});
</script>
