<template>
	<div class="page-shell" data-test="lab-detail">
		<p v-if="!lab.data" class="text-body text-ink-gray-5">Loading lab…</p>

		<template v-else>
			<LabHeader
				:lab="labView"
				:bench="bench"
				:site-url="siteAddress"
				:vpn-connected="vpnStatus.connected"
				:is-admin="userContext.isAdmin"
				:busy="busy"
				@deploy="deployLab"
				@rebuild="buildImage"
				@open="openSite"
				@code-server="openCodeServer"
				@stop="runBenchAction('stop')"
				@delete="deleteBench"
			/>

			<ErrorMessage class="mt-3" :message="actionError" />

			<LabErrorBanner
				v-if="lab.data.failure"
				class="mt-4"
				:failure="lab.data.failure"
				:is-admin="userContext.isAdmin"
				@edit="editLab"
				@view-log="showFailingLog"
			/>

			<Tabs v-model="activeTab" class="mt-5" :tabs="tabs">
				<template #tab-panel="{ tab }">
					<div v-if="tab.key === 'dashboard'" class="grid gap-4 pt-4 lg:grid-cols-2">
						<div class="flex min-w-0 flex-col gap-4">
							<ContainerStatusCard
								v-if="bench"
								:bench="bench"
								:lab="lab.data"
								:health-age-seconds="healthAgeSeconds"
								@bought="refresh"
							/>
							<SectionCard v-else :padded="false">
								<EmptyState
									message="This lab has never been deployed. Deploying builds a container, a site, an SSH user and an IDE."
								/>
							</SectionCard>

							<ConnectionDetails
								v-if="bench"
								:lab="lab.data"
								:bench="bench"
								:credentials="credentials.data ?? {}"
								:site-url="siteAddress"
							/>
						</div>

						<div class="flex min-w-0 flex-col gap-4">
							<ConnectionCard
								:connected="vpnStatus.connected"
								@register="router.push('/devices')"
							/>
							<SitesCard v-bind="sitesProps" :can-create="false" @open="openSite" />
						</div>
					</div>

					<div v-else-if="tab.key === 'sites'" class="pt-4">
						<SitesCard
							v-bind="sitesProps"
							:can-create="!!bench"
							@create="createSite"
							@open="openSite"
						/>
					</div>

					<div v-else class="pt-4">
						<!-- The deploy log is the pipeline; the build log is Docker's
						     own output, which has no steps of ours to report. -->
						<DeployPipeline
							v-if="tab.key === 'deploy' && deployText"
							:raw-log="deployText"
							title="Latest deploy"
							:file-name="`${labId}-deploy.log`"
						/>
						<LogViewer
							v-else-if="tab.key === 'build' && buildText"
							:rawLog="buildText"
						/>
						<SectionCard v-else :padded="false">
							<EmptyState :message="LOG_EMPTY[tab.key]" />
						</SectionCard>
					</div>
				</template>
			</Tabs>
		</template>
	</div>
</template>

<script setup>
// The page owns routing, the data resources and the tab state; every region is
// a component. Nothing here polls: the deploy and build logs already arrive over
// socket.io, and the three timers this file used to run raced those handlers —
// `stats_collector` writes with `update_modified=False`, so a poll on `modified`
// would never have seen a stat change anyway.
import EmptyState from "@/components/EmptyState.vue";
import LogViewer from "@/components/LogViewer.vue";
import SectionCard from "@/components/SectionCard.vue";
import DeployPipeline from "@/components/deploy/DeployPipeline.vue";
import ConnectionCard from "@/components/lab/ConnectionCard.vue";
import ConnectionDetails from "@/components/lab/ConnectionDetails.vue";
import ContainerStatusCard from "@/components/lab/ContainerStatusCard.vue";
import LabErrorBanner from "@/components/lab/LabErrorBanner.vue";
import LabHeader from "@/components/lab/LabHeader.vue";
import SitesCard from "@/components/lab/SitesCard.vue";
import { openDeployRun } from "@/data/deployRun";
import { userContext } from "@/data/userContext";
import { vpnStatus } from "@/data/vpnStatus";
import { siteUrl } from "@/utils/labActions";
import { useSocket } from "@/socket";
import { ErrorMessage, Tabs, createListResource, createResource, dayjsLocal } from "frappe-ui";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

const TERMINAL_LOG_TYPES = ["success", "error"];

const LOG_EMPTY = {
	deploy: "No deploy has run yet — deploying this lab streams its log here.",
	build: "No image build has run yet — a rebuild, or a deploy with no cached image, streams its log here.",
};

const route = useRoute();
const router = useRouter();
const labId = route.params.labId;

const activeTab = ref(0);
const liveDeployLog = ref("");
const liveBuildLog = ref("");
// The stored document each live buffer belongs to.
const liveDeployRun = ref("");
const liveBuildRun = ref("");
// True from the click, before the enqueued worker has flipped the lab to
// Building in the database — without it the button races the background job.
const building = ref(false);

const lab = createResource({ url: "benchpress.api.get_lab", params: { name: labId }, auto: true });
const credentials = createResource({ url: "benchpress.api.get_bench_credentials" });
const deployLogs = createResource({ url: "benchpress.api.get_deploy_logs" });
const buildLogs = createListResource({
	doctype: "Build Log",
	fields: ["name", "message", "log_type", "timestamp"],
	filters: { lab: labId },
	orderBy: "timestamp desc",
	pageLength: 1,
	auto: true,
});

// Every action reloads the lab, which is what carries the bench, its sites and
// the failure back to the page.
const refresh = () => lab.reload();
const buildAction = createResource({
	url: "benchpress.api.build_lab_image",
	onError: () => (building.value = false),
});
const deployAction = createResource({ url: "benchpress.api.create_bench", onSuccess: refresh });
const benchAction = createResource({ url: "benchpress.api.bench_action", onSuccess: refresh });
const createSiteAction = createResource({ url: "benchpress.api.create_site", onSuccess: refresh });

const bench = computed(() => lab.data?.bench ?? null);
const sites = computed(() => lab.data?.sites ?? []);
const siteAddress = computed(() => siteUrl(bench.value));
const busy = computed(
	() => buildAction.loading || deployAction.loading || benchAction.loading || !!building.value
);
const actionError = computed(
	() => buildAction.error || deployAction.error || benchAction.error || ""
);

// The lab as the header should read it, including the optimistic build state.
const labView = computed(() => (building.value ? { ...lab.data, status: "Building" } : lab.data));

const sitesProps = computed(() => ({
	sites: sites.value,
	labApps: lab.data?.apps ?? [],
	reachable: vpnStatus.connected,
	creating: createSiteAction.loading,
	createError: createSiteAction.error || "",
}));

/** Age of the health reading in seconds; null when the bench was never polled. */
const healthAgeSeconds = computed(() => {
	const checkedAt = bench.value?.last_health_check;
	return checkedAt ? dayjsLocal().diff(dayjsLocal(checkedAt), "second") : null;
});

// Panels switch on a stable key, never on a tab's position: the polling this
// page used to run compared `tab === 2`, so adding a tab silently repointed it.
const tabs = computed(() => {
	const list = [
		{ key: "dashboard", label: "Dashboard" },
		{ key: "sites", label: "Sites" },
		{ key: "deploy", label: "Deploy log" },
	];
	// A deploy that misses the image cache builds too, so the tab follows the log, not the role.
	if (userContext.isAdmin || buildText.value) list.push({ key: "build", label: "Build log" });
	return list;
});

// The stored log and the live stream are one run: a page opened mid-deploy
// reads the lines it missed from the document and appends the rest as they
// arrive. Reading only the live stream would restart the stepper at step one
// on every reload, and reading another run's document would show its outcome above step one.
const deployText = computed(() => runText(deployLogs.data?.[0], liveDeployRun, liveDeployLog));
const buildText = computed(() => runText(buildLogs.data?.[0], liveBuildRun, liveBuildLog));

function runText(stored, liveRun, liveLog) {
	if (!liveRun.value) return stored?.message ?? "";
	const base = stored?.name === liveRun.value ? stored.message : "";
	return base + liveLog.value;
}

// Credentials and deploy history belong to a bench, so both follow its identity.
watch(
	() => bench.value?.name,
	(name) => {
		if (!name) return;
		credentials.submit({ bench_name: name });
		deployLogs.submit({ bench_name: name });
	},
	{ immediate: true }
);

// Drop the optimistic flag once the build reaches a terminal state.
watch(
	() => lab.data?.status,
	(status) => {
		if (status === "Ready" || status === "Error") building.value = false;
	}
);

async function deployLab() {
	endRun(liveDeployRun, liveDeployLog);
	const bench = await deployAction.submit({ data: JSON.stringify({ lab: labId }) });
	if (deployAction.error || !bench?.name) return;
	openDeployRun({ labId, benchName: bench.name });
}

function buildImage() {
	endRun(liveBuildRun, liveBuildLog);
	building.value = true;
	buildAction.submit({ lab_name: labId });
}

function runBenchAction(action) {
	if (!bench.value) return;
	benchAction.submit({ bench_name: bench.value.name, action });
}

async function deleteBench() {
	if (!bench.value) return;
	await benchAction.submit({ bench_name: bench.value.name, action: "delete" });
	router.push("/labs");
}

function createSite({ siteName, apps }) {
	createSiteAction.submit({
		data: JSON.stringify({
			site_name: siteName,
			bench: bench.value?.name,
			apps: apps.map((name) => ({ name })),
		}),
	});
}

function openSite() {
	if (siteAddress.value) window.open(siteAddress.value, "_blank");
}

function openCodeServer() {
	if (bench.value?.code_server_url) window.open(bench.value.code_server_url, "_blank");
}

/** Lab recipes are edited on the desk form; the SPA has no editor yet. */
function editLab() {
	window.open(`/app/lab/${labId}`, "_blank");
}

function showFailingLog() {
	goToTab(lab.data?.failure?.source === "build" ? "build" : "deploy");
}

function goToTab(key) {
	const index = tabs.value.findIndex((tab) => tab.key === key);
	if (index >= 0) activeTab.value = index;
}

const socket = useSocket();

// On a terminal line the stored document already holds every line the stream
// delivered, so the live buffer is dropped once the reload lands — clearing it
// any earlier would flash the previous run.
async function onDeployLog(data) {
	if (!bench.value || data.bench !== bench.value.name) return;
	startRun(liveDeployRun, liveDeployLog, data.deploy_log);
	liveDeployLog.value += `${data.log}\n`;
	if (!TERMINAL_LOG_TYPES.includes(data.type)) return;
	refresh();
	await deployLogs.reload();
	endRun(liveDeployRun, liveDeployLog);
}

async function onBuildLog(data) {
	if (data.lab !== labId) return;
	startRun(liveBuildRun, liveBuildLog, data.build_log);
	liveBuildLog.value += `${data.log}\n`;
	if (!TERMINAL_LOG_TYPES.includes(data.type)) return;
	refresh();
	await buildLogs.reload();
	endRun(liveBuildRun, liveBuildLog);
}

function startRun(liveRun, liveLog, logName) {
	if (!logName || liveRun.value === logName) return;
	liveRun.value = logName;
	liveLog.value = "";
}

function endRun(liveRun, liveLog) {
	liveRun.value = "";
	liveLog.value = "";
}

onMounted(() => {
	socket?.on("bench_deploy_log", onDeployLog);
	socket?.on("lab_build_log", onBuildLog);
});

onUnmounted(() => {
	socket?.off("bench_deploy_log", onDeployLog);
	socket?.off("lab_build_log", onBuildLog);
});
</script>
