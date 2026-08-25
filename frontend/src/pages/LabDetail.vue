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
				@start="runBenchAction('start')"
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
							/>
						</div>

						<div class="flex min-w-0 flex-col gap-4">
							<ConnectionCard
								:connected="vpnStatus.connected"
								@register="router.push('/devices')"
							/>
							<SitesCard v-bind="sitesProps" @open="openSite" />
						</div>
					</div>

					<div v-else-if="tab.key === 'sites'" class="pt-4">
						<SitesCard v-bind="sitesProps" @open="openSite" />
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

			<CodeServerDialog
				v-model="showCodeServerPassword"
				:loading="codeServerCredentials.loading"
				:error="codeServerCredentials.error"
				:password="codeServerCredentials.data?.password ?? ''"
			/>
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
import CodeServerDialog from "@/components/lab/CodeServerDialog.vue";
import ConnectionCard from "@/components/lab/ConnectionCard.vue";
import ConnectionDetails from "@/components/lab/ConnectionDetails.vue";
import ContainerStatusCard from "@/components/lab/ContainerStatusCard.vue";
import LabErrorBanner from "@/components/lab/LabErrorBanner.vue";
import LabHeader from "@/components/lab/LabHeader.vue";
import SitesCard from "@/components/lab/SitesCard.vue";
import { openDeployRun } from "@/data/deployRun";
import { userContext } from "@/data/userContext";
import { reloadVpnStatus, vpnStatus } from "@/data/vpnStatus";
import { ideUrl, siteUrl } from "@/utils/labActions";
import { useSocket } from "@/socket";
import { recordSkew } from "@/utils/clock";
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
// Fetched at the moment the IDE is opened, never on page load: a password on
// screen nobody asked for is a password on a screenshot.
const codeServerCredentials = createResource({
	url: "benchpress.api.get_code_server_credentials",
});
const showCodeServerPassword = ref(false);
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

// Each row carries the address its own Open button opens, resolved through the
// one URL helper — the card renders what it is handed and resolves nothing.
const sitesProps = computed(() => ({
	sites: sites.value.map((site) => ({ ...site, url: siteUrl(bench.value, site) })),
	reachable: vpnStatus.connected,
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

// The header hands over no site, so it opens the bench's own; a row hands over
// its site, and opens that one.
function openSite(site = null) {
	const address = siteUrl(bench.value, site);
	if (address) window.open(address, "_blank");
}

// The tab is opened by the click itself — a `window.open` after an awaited fetch
// is a popup, not a navigation, and browsers block it. The password follows into
// the dialog, so the user reads it beside the login form instead of hunting for
// it behind "Reveal secrets".
//
// `restart_code_server` is the other endpoint with no caller. It belongs in the
// overflow menu the day an acceptance run shows code-server needs a nudge; until
// then it would be a button for a problem nobody has had.
function openCodeServer() {
	const address = ideUrl(bench.value);
	if (!address || !bench.value) return;
	window.open(address, "_blank");
	// The address opened is the helper's, not the one the endpoint returns:
	// issue #130 repoints `ideUrl` alone. The call is for the password, and for
	// the guards it already carries — bench Running, and an address the deploy
	// actually stored.
	codeServerCredentials.reset();
	showCodeServerPassword.value = true;
	// The dialog is where a failure is read, so the rejection is swallowed here
	// rather than reported twice.
	codeServerCredentials.submit({ bench_name: bench.value.name }).catch(() => {});
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

// The push carries full reconcilable state, but this page shows a dozen derived
// facts about the bench — sites, actions, the failure banner — so it reloads
// rather than patching one field and leaving the rest describing a running bench.
function onLeaseExpired(data) {
	if (!bench.value || data.bench !== bench.value.name) return;
	recordSkew(Date.now(), data.server_now_ts * 1000);
	refresh();
}

onMounted(() => {
	socket?.on("bench_deploy_log", onDeployLog);
	socket?.on("lab_build_log", onBuildLog);
	socket?.on("benchpress:lease_expired", onLeaseExpired);
	// Every open button on this page is gated on the tunnel, and the tunnel is
	// brought up outside the app — so ask again on arrival rather than trusting
	// whatever the SPA read at boot.
	reloadVpnStatus();
});

onUnmounted(() => {
	socket?.off("bench_deploy_log", onDeployLog);
	socket?.off("lab_build_log", onBuildLog);
	socket?.off("benchpress:lease_expired", onLeaseExpired);
});
</script>
