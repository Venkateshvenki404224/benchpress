<template>
	<div class="p-6" v-if="lab.doc">
		<!-- Header -->
		<div class="mb-6 flex items-start justify-between">
			<div>
				<div class="flex items-center gap-3">
					<h1 class="text-2xl font-bold text-ink-gray-9">{{ lab.doc.title }}</h1>
				</div>
				<div class="mt-2 flex items-center gap-2 text-sm text-ink-gray-5">
					<span>Lab ID:</span>
					<code
						class="rounded bg-surface-gray-2 px-1.5 py-0.5 font-mono text-xs text-ink-gray-7"
						>{{ lab.doc.lab_id }}</code
					>
				</div>
				<p v-if="lab.doc.description" class="mt-3 max-w-xl text-sm text-ink-gray-6">
					{{ lab.doc.description }}
				</p>
				<div class="mt-3 flex gap-3">
					<Badge :label="lab.doc.frappe_version" theme="blue" variant="outline" />
					<Badge :label="`${lab.doc.memory_limit} RAM`" theme="gray" variant="outline" />
					<Badge :label="`${lab.doc.cpu_cores} CPU`" theme="gray" variant="outline" />
				</div>
			</div>
			<div class="flex gap-2">
				<Button
					v-if="lab.doc.status !== 'Ready' && userContext.isAdmin"
					theme="blue"
					variant="solid"
					size="lg"
					:loading="buildAction.loading || lab.doc.status === 'Building'"
					@click="buildLabImage"
					>{{ lab.doc.status === "Building" ? "Building..." : "Build Image" }}</Button
				>
				<!-- Lab ready, no instance or instance stopped/errored: show Deploy -->
				<Button
					v-if="
						lab.doc.status === 'Ready' &&
						(!activeBench ||
							activeBench.status === 'Stopped' ||
							activeBench.status === 'Error')
					"
					theme="green"
					variant="solid"
					size="lg"
					:loading="deployAction.loading"
					@click="showDeployConfirm = true"
					>Deploy</Button
				>
				<Button
					v-if="
						activeBench &&
						activeBench.status === 'Running' &&
						lab.doc.enable_code_server &&
						codeServerUrl
					"
					theme="blue"
					variant="solid"
					size="lg"
					@click="openCodeServer"
					>Open VS Code</Button
				>
				<!-- Instance running: show Stop -->
				<Button
					v-if="activeBench && activeBench.status === 'Running'"
					theme="red"
					variant="solid"
					size="lg"
					:loading="benchAction.loading"
					@click="showStopConfirm = true"
					>Stop</Button
				>
			</div>
		</div>

		<ErrorMessage class="mb-4" :message="buildAction.error" />
		<ErrorMessage class="mb-4" :message="deployAction.error" />
		<ErrorMessage class="mb-4" :message="benchAction.error" />
		<ErrorMessage class="mb-4" :message="createSiteAction.error" />

		<!-- Tabs -->
		<Tabs :tabs="tabs" v-model="activeTab">
			<template #tab-panel="{ tab }">
				<!-- Dashboard Tab -->
				<div v-if="tab.label === 'Dashboard'" class="p-4">
					<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
						<!-- Left column -->
						<div class="flex flex-col gap-6">
							<!-- Lab Information -->
							<div
								class="rounded-lg border border-outline-gray-1 bg-surface-white p-5"
							>
								<h2 class="mb-3 text-base font-semibold text-ink-gray-9">
									Lab Information
								</h2>
								<p v-if="lab.doc.description" class="mb-4 text-sm text-ink-gray-6">
									{{ lab.doc.description }}
								</p>
								<p
									v-if="!activeBench && !lab.doc.description"
									class="mb-4 text-sm text-ink-gray-5"
								>
									This lab is not deployed yet. Click "Deploy" to start.
								</p>
								<div v-if="lab.doc.apps?.length" class="mt-4">
									<h3 class="mb-2 text-sm font-medium text-ink-gray-7">
										Installed Apps
									</h3>
									<div class="flex flex-wrap gap-2">
										<Badge
											v-for="app in lab.doc.apps"
											:key="app.app_name"
											:label="app.app_label || app.app_name"
											theme="blue"
											variant="outline"
										/>
									</div>
								</div>
							</div>

							<!-- Connection Info -->
							<ConnectionInfo
								v-if="activeBench && activeBench.status === 'Running'"
								:bench="activeBench"
								:enable-code-server="!!lab.doc.enable_code_server"
								:visibility-loading="visibilityAction.loading"
								:bench-ip="benchIp"
								:ssh-command="sshCommand"
								:ssh-username="sshUsername"
								:ssh-password="sshPassword"
								:admin-password="adminPassword"
								:site-url="siteUrl"
								:code-server-url="codeServerUrl"
								:code-server-password="codeServerPassword"
								@toggle-visibility="onVisibilityChange"
							/>
						</div>

						<!-- Right column -->
						<div class="flex flex-col gap-6">
							<!-- Container Status -->
							<ResourceUsage v-if="activeBench" :bench="activeBench" />

							<!-- No deployment yet -->
							<div
								v-if="!activeBench && !benches.loading"
								class="rounded-lg border border-outline-gray-1 bg-surface-white p-5"
							>
								<div class="py-6 text-center">
									<div class="text-sm text-ink-gray-5">No active deployment</div>
									<p class="mt-1 text-xs text-ink-gray-4">
										Click "Deploy" to create a new bench instance from this
										lab.
									</p>
								</div>
							</div>
						</div>
					</div>
				</div>

				<!-- Sites Tab -->
				<SitesTab
					v-if="tab.label === 'Sites'"
					v-model="showNewSite"
					:rows="sites.data"
					:apps="lab.doc.apps"
					:active-bench="activeBench"
					:create-loading="createSiteAction.loading"
					@create="createSite"
				/>

				<!-- Deploy Log Tab -->
				<div v-if="tab.label === 'Deploy Log'" class="p-4">
					<div v-if="liveDeployLog || deployLogs.data?.length">
						<LogViewer
							:rawLog="liveDeployLog || deployLogs.data?.[0]?.message || ''"
						/>
					</div>
					<div v-else-if="deployLogs.loading" class="text-base text-ink-gray-5">
						Loading deploy logs...
					</div>
					<div
						v-else
						class="rounded-lg border border-outline-gray-1 bg-surface-white p-8 text-center"
					>
						<div class="text-sm text-ink-gray-5">
							No active deployment. Click "Deploy" to start.
						</div>
					</div>
				</div>

				<!-- Build Log Tab -->
				<div v-if="tab.label === 'Build Log'" class="p-4">
					<div v-if="liveBuildLog || buildLogs.data?.length">
						<LogViewer :rawLog="liveBuildLog || buildLogs.data?.[0]?.message || ''" />
					</div>
					<div v-else-if="buildLogs.loading" class="text-base text-ink-gray-5">
						Loading build log...
					</div>
					<div
						v-else
						class="rounded-lg border border-outline-gray-1 bg-surface-white p-8 text-center"
					>
						<div class="text-sm text-ink-gray-5">
							No build logs yet. Click "Build Image" to start.
						</div>
					</div>
				</div>
			</template>
		</Tabs>
	</div>

	<!-- Loading state -->
	<div v-else class="flex items-center justify-center p-12">
		<div class="text-base text-ink-gray-5">Loading lab details...</div>
	</div>

	<!-- Deploy Confirmation Dialog -->
	<Dialog v-model="showDeployConfirm">
		<template #body-title>
			<h3 class="text-lg font-semibold text-ink-gray-9">Deploy Lab</h3>
		</template>
		<template #body-content>
			<p class="text-sm text-ink-gray-6">
				This will create a container and set up a Frappe bench. Continue?
			</p>
		</template>
		<template #actions="{ close }">
			<div class="flex flex-row-reverse gap-2">
				<Button
					variant="solid"
					theme="green"
					:loading="deployAction.loading"
					@click="
						deployLab();
						close();
					"
					>Deploy</Button
				>
				<Button variant="outline" @click="close">Cancel</Button>
			</div>
		</template>
	</Dialog>

	<!-- Stop Confirmation Dialog -->
	<Dialog v-model="showStopConfirm">
		<template #body-title>
			<h3 class="text-lg font-semibold text-ink-gray-9">Stop Bench</h3>
		</template>
		<template #body-content>
			<p class="text-sm text-ink-gray-6">
				This will stop the running container. The bench will go offline until redeployed.
				Continue?
			</p>
		</template>
		<template #actions="{ close }">
			<div class="flex flex-row-reverse gap-2">
				<Button
					variant="solid"
					theme="red"
					:loading="benchAction.loading"
					@click="
						doBenchAction('stop');
						close();
					"
					>Stop</Button
				>
				<Button variant="outline" @click="close">Cancel</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import { useSocket } from "@/socket";
import {
	useDoc,
	useCall,
	useList,
	Badge,
	Button,
	Tabs,
	Dialog,
	ErrorMessage,
	toast,
} from "frappe-ui";
import LogViewer from "@/components/LogViewer.vue";
import ConnectionInfo from "@/components/lab/ConnectionInfo.vue";
import ResourceUsage from "@/components/lab/ResourceUsage.vue";
import SitesTab from "@/components/lab/SitesTab.vue";
import { userContext } from "@/data/userContext";

const route = useRoute();
const labId = route.params.labId;
const activeTab = ref(0);
const showNewSite = ref(false);
const showDeployConfirm = ref(false);
const showStopConfirm = ref(false);

const tabs = computed(() => {
	const base = [{ label: "Dashboard" }, { label: "Sites" }];
	if (lab.doc?.status === "Ready" || activeBench.value) {
		base.push({ label: "Deploy Log" });
	} else if (userContext.isAdmin) {
		base.push({ label: "Build Log" });
	}
	return base;
});

const sshUsername = computed(() => activeBench.value?.ssh_username || null);
const sshPassword = computed(() => activeBench.value?.ssh_password || null);
const adminPassword = computed(() => activeBench.value?.admin_password || null);
const codeServerUrl = computed(() => activeBench.value?.code_server_url || null);
const codeServerPassword = computed(() => activeBench.value?.code_server_password || null);
const benchIp = computed(
	() => activeBench.value?.wg_ip || activeBench.value?.container_ip || null
);
const sshCommand = computed(() => {
	const ip = benchIp.value;
	const user = sshUsername.value;
	if (!ip || !user) return null;
	return `ssh ${user}@${ip}`;
});
const siteUrl = computed(() => {
	const ip = benchIp.value;
	if (!ip) return null;
	return `${ip}:8000`;
});

const lab = useDoc({
	doctype: "Lab",
	name: labId,
});

const benches = useCall({
	url: "/api/v2/method/benchpress.api.get_benches",
	immediate: true,
});

const activeBench = computed(() => {
	if (!benches.data) return null;
	return benches.data.find((b) => b.lab === labId) || null;
});

const sites = useList({
	doctype: "Bench Site",
	fields: ["name", "site_name", "full_domain", "status"],
	filters: () => ({ bench: activeBench.value?.name || "" }),
	orderBy: "creation desc",
	immediate: false,
	refetch: false,
});

watch(
	() => activeBench.value?.name,
	(n) => n && sites.reload(),
	{ immediate: true }
);

const deployLogs = useCall({
	url: "/api/v2/method/benchpress.api.get_deploy_logs",
	immediate: false,
});

const buildLogs = useList({
	doctype: "Build Log",
	fields: ["name", "message", "log_type", "timestamp"],
	filters: { lab: labId },
	orderBy: "timestamp desc",
	limit: 20,
	immediate: true,
});

const liveDeployLog = ref("");
const deployComplete = ref(false);
let pollInterval = null;

// Fetch deploy logs when bench is available
function fetchDeployLogs() {
	if (!activeBench.value) return;
	deployLogs.submit({ bench_name: activeBench.value.name });
}

// Sync fetched logs into live display and detect completion
watch(
	() => deployLogs.data,
	(data) => {
		if (data?.length) {
			liveDeployLog.value = data[0].message || "";
			if (data[0].log_type === "success" && !deployComplete.value) {
				deployComplete.value = true;
				if (pollInterval) {
					clearInterval(pollInterval);
					pollInterval = null;
				}
				benches.reload();
			}
		}
	}
);

// Reload logs when the actual bench changes (watch name, not object ref)
watch(
	() => activeBench.value?.name,
	(name, oldName) => {
		if (name && name !== oldName) {
			deployComplete.value = false;
			if (activeTab.value === 2) {
				fetchDeployLogs();
			}
		}
	}
);

// Poll for new logs while deploying (only on Deploy Log tab)
watch(
	[() => activeBench.value?.status, activeTab],
	([status, tab]) => {
		if (pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
		}
		if (status === "Deploying" && tab === 2 && !deployComplete.value) {
			pollInterval = setInterval(fetchDeployLogs, 3000);
		}
	},
	{ immediate: true }
);

// Poll for build logs while building
let buildPollInterval = null;

watch(
	() => lab.doc?.status,
	(status) => {
		if (status === "Building") {
			buildPollInterval = setInterval(() => {
				buildLogs.reload();
			}, 3000);
		} else {
			if (buildPollInterval) {
				clearInterval(buildPollInterval);
				buildPollInterval = null;
			}
			if (status === "Ready" || status === "Error") {
				buildLogs.reload();
			}
		}
	},
	{ immediate: true }
);

// Also poll lab status while building to detect completion
let labPollInterval = null;

watch(
	() => lab.doc?.status,
	(status) => {
		if (status === "Building") {
			labPollInterval = setInterval(() => {
				lab.reload();
			}, 5000);
		} else if (labPollInterval) {
			clearInterval(labPollInterval);
			labPollInterval = null;
		}
	}
);

// Sync build logs into live display
watch(
	() => buildLogs.data,
	(data) => {
		if (data?.length) {
			liveBuildLog.value = data[0].message || "";
		}
	}
);

// Refetch when switching to log tabs (one-time fetch, not continuous)
watch(activeTab, (tab) => {
	if (tab === 2) {
		if (activeBench.value && !deployComplete.value) {
			fetchDeployLogs();
		} else if (!activeBench.value) {
			buildLogs.reload();
		}
	}
});

// Socket listeners for live logs
const socket = useSocket();
const liveBuildLog = ref("");

function onDeployLog(data) {
	if (activeBench.value && data.bench === activeBench.value.name) {
		liveDeployLog.value += data.log + "\n";
		if (data.type === "success" || data.type === "error") {
			benches.reload();
			deployLogs.reload();
		}
	}
}

function onBuildLog(data) {
	if (data.lab === labId) {
		liveBuildLog.value += data.log + "\n";
		// Reload lab status when build completes
		if (data.type === "success" || data.type === "error") {
			lab.reload();
			buildLogs.reload();
		}
	}
}

onMounted(() => {
	if (socket) {
		socket.on("bench_deploy_log", onDeployLog);
		socket.on("lab_build_log", onBuildLog);
	}
	// Initial fetch (only if on deploy log tab)
	if (activeBench.value && activeTab.value === 2) {
		fetchDeployLogs();
	}
});

onUnmounted(() => {
	if (socket) {
		socket.off("bench_deploy_log", onDeployLog);
		socket.off("lab_build_log", onBuildLog);
	}
	if (pollInterval) {
		clearInterval(pollInterval);
	}
	if (buildPollInterval) {
		clearInterval(buildPollInterval);
	}
	if (labPollInterval) {
		clearInterval(labPollInterval);
	}
});

const buildAction = useCall({
	url: "/api/v2/method/benchpress.api.build_lab_image",
	method: "POST",
	immediate: false,
	onSuccess() {
		lab.reload();
		buildLogs.reload();
	},
});

function buildLabImage() {
	liveBuildLog.value = "";
	buildAction.submit({ lab_name: labId });
}

const deployAction = useCall({
	url: "/api/v2/method/benchpress.api.create_bench",
	method: "POST",
	immediate: false,
	onSuccess() {
		liveDeployLog.value = "";
		deployComplete.value = false;
		benches.reload();
	},
});

function deployLab() {
	deployAction.submit({
		data: JSON.stringify({ lab: labId }),
	});
}

const benchAction = useCall({
	url: "/api/v2/method/benchpress.api.bench_action",
	method: "POST",
	immediate: false,
	onSuccess() {
		benches.reload();
	},
});

function openCodeServer() {
	const url = codeServerUrl.value;
	if (url) {
		window.open(url, "_blank");
	}
}

function doBenchAction(action) {
	if (!activeBench.value) return;
	benchAction.submit({
		bench_name: activeBench.value.name,
		action,
	});
}

const visibilityAction = useCall({
	url: "/api/v2/method/benchpress.api.set_bench_visibility",
	method: "POST",
	immediate: false,
	onSuccess() {
		liveDeployLog.value = "";
		deployComplete.value = false;
		benches.reload();
		toast.success("Updating bench visibility — this re-creates the container.");
	},
	onError(err) {
		toast.error(err?.message || "Failed to update visibility");
	},
});

function onVisibilityChange(value) {
	if (!activeBench.value) return;
	visibilityAction.submit({
		bench_name: activeBench.value.name,
		is_public: value ? 1 : 0,
	});
}

const createSiteAction = useCall({
	url: "/api/v2/method/benchpress.api.create_site",
	method: "POST",
	immediate: false,
	onSuccess() {
		showNewSite.value = false;
		sites.reload();
	},
});

function createSite({ siteName, apps }) {
	if (!siteName || !activeBench.value) return;
	createSiteAction.submit({
		data: JSON.stringify({
			site_name: siteName,
			bench: activeBench.value.name,
			apps: apps.map((name) => ({ name })),
		}),
	});
}
</script>
