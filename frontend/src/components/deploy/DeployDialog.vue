<template>
	<Dialog
		v-model="isOpen"
		:options="{ title: dialogTitle, size: 'xl' }"
		data-test="deploy-dialog"
	>
		<template #body-content>
			<p class="text-body text-ink-gray-6" data-test="deploy-summary">
				{{ summary }}
			</p>

			<ol
				class="mt-3 divide-y divide-outline-gray-1 rounded-card border border-outline-gray-1"
			>
				<DeployStepRow v-for="step in run.steps" :key="step.key" :step="step" />
			</ol>

			<div class="mt-3 rounded-md bg-surface-gray-2 px-3 py-2" data-test="deploy-log-tail">
				<p
					v-for="(line, index) in tail"
					:key="index"
					class="truncate font-mono text-2xs leading-5 text-ink-gray-6"
				>
					{{ line }}
				</p>
				<p v-if="!tail.length" class="font-mono text-2xs leading-5 text-ink-gray-5">
					{{ placeholder }}
				</p>
			</div>
		</template>

		<template #actions>
			<div class="flex items-center gap-2">
				<Button variant="subtle" data-test="run-in-background" @click="closeDeployRun">
					Run in background
				</Button>
				<Button
					class="ml-auto"
					variant="solid"
					:disabled="cta.disabled"
					:loading="cta.loading"
					data-test="deploy-cta"
					@click="runCta"
				>
					{{ cta.label }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import DeployStepRow from "@/components/deploy/DeployStepRow.vue";
import { appendBuildLine, appendDeployLine, closeDeployRun, deployRun } from "@/data/deployRun";
import { vpnStatus } from "@/data/vpnStatus";
import { useSocket } from "@/socket";
import { ACTIVE, deriveRun } from "@/utils/deploySteps";
import { CONNECT_VPN, OPEN, VIEW_LOG, deployDialogAction, siteUrl } from "@/utils/labActions";
import { Button, Dialog, createResource } from "frappe-ui";
import { computed, onMounted, onUnmounted, watch } from "vue";
import { useRouter } from "vue-router";

// The dialog every deploy opens, wherever it was started from. Its steps come
// from the same derivation the Deploy log tab uses, so the two can never
// disagree, and its copy comes from the lab that was clicked — there is no
// ERPNext anywhere in this file.
const TAIL_LINES = 3;
const WAITING_FOR_WORKER = "Waiting for the worker to pick the deploy up…";
const WAITING_FOR_DOCKER = "Waiting for Docker…";
// A stepper sitting on step 2 for half an hour has to read as expected rather
// than as stuck, so the summary says what is happening and how long it takes.
const BUILDING_SUMMARY =
	"Building the lab image. A first build can take up to 40 minutes; the deploy starts on its own when it finishes.";

const router = useRouter();
const socket = useSocket();

const lab = createResource({ url: "benchpress.api.get_lab" });

const isOpen = computed({
	get: () => deployRun.open,
	set: (value) => !value && closeDeployRun(),
});

const run = computed(() => deriveRun(deployRun.log));
const bench = computed(() => lab.data?.bench ?? null);
// The launch hands back the title, so the heading is right from the first
// frame — `get_lab` has not resolved when the dialog opens.
const dialogTitle = computed(
	() => `Deploying ${deployRun.labTitle || lab.data?.title || "your lab"}`
);

const activeKey = computed(() => run.value.steps.find((step) => step.state === ACTIVE)?.key || "");

// The deploy has an `image` step too, but adopting a cached image is instant and
// streams no build log. A non-empty build buffer is what says Docker is running.
const building = computed(() => activeKey.value === "image" && Boolean(deployRun.buildLog));

// One box, whichever stream is live: during the build the pipeline emits
// nothing, so showing the deploy log there would read as a stalled run.
const tail = computed(() =>
	(building.value ? deployRun.buildLog : deployRun.log)
		.split("\n")
		.filter((line) => line.trim())
		.slice(-TAIL_LINES)
);

const placeholder = computed(() => (building.value ? WAITING_FOR_DOCKER : WAITING_FOR_WORKER));

/** What this run is building — the site and the apps of the lab that was clicked. */
const summary = computed(() => {
	if (building.value) return BUILDING_SUMMARY;
	const site = bench.value?.site_name;
	const apps = (lab.data?.apps ?? []).map((app) => app.app_label || app.app_name);
	const installing = apps.length ? apps.join(", ") : "Frappe";
	return site ? `Creating ${site} with ${installing}.` : `Installing ${installing}.`;
});

const address = computed(() => siteUrl(bench.value));

const cta = computed(() =>
	deployDialogAction({
		runState: run.value.state,
		vpnConnected: vpnStatus.connected,
		siteUrl: address.value,
	})
);

const RUN_CTA = { [VIEW_LOG]: openLab, [CONNECT_VPN]: openDevices, [OPEN]: openSite };

function runCta() {
	RUN_CTA[cta.value.action]?.();
}

function openSite() {
	if (address.value) window.open(address.value, "_blank");
}

function openDevices() {
	closeDeployRun();
	router.push("/devices");
}

function openLab() {
	closeDeployRun();
	router.push({ name: "LabDetail", params: { labId: deployRun.labId } });
}

// The lab is reloaded when the run ends because that is when the bench gains
// the address the CTA opens.
function onTerminalState() {
	if (deployRun.labId) lab.submit({ name: deployRun.labId });
}

watch(
	() => deployRun.open,
	(open) => open && deployRun.labId && lab.submit({ name: deployRun.labId })
);

watch(
	() => run.value.state,
	(state) => ["success", "failed"].includes(state) && onTerminalState()
);

onMounted(() => {
	socket?.on("bench_deploy_log", onDeployLog);
	socket?.on("lab_build_log", onBuildLog);
});

onUnmounted(() => {
	socket?.off("bench_deploy_log", onDeployLog);
	socket?.off("lab_build_log", onBuildLog);
});

// Both events are published server-side into one user's room, so the id is the
// only thing worth checking — there is no ownership left to filter on.
function onDeployLog(data) {
	if (!deployRun.open || data.bench !== deployRun.benchName) return;
	appendDeployLine(data.log);
}

function onBuildLog(data) {
	if (!deployRun.open || data.lab !== deployRun.labId) return;
	appendBuildLine(data.log);
}
</script>
