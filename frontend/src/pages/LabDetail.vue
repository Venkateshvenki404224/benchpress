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

							<!-- Copy alert -->
							<Teleport to="body">
								<Transition name="slide-in">
									<Alert
										v-if="copyAlert"
										title="Copied to clipboard"
										description="Connection info has been copied. You can paste it in your terminal."
										theme="green"
										class="fixed right-4 top-4 z-50 w-80 shadow-lg"
									/>
								</Transition>
							</Teleport>

							<!-- Connection Info -->
							<div
								v-if="activeBench && activeBench.status === 'Running'"
								class="rounded-lg border border-outline-gray-1 bg-surface-white p-5"
							>
								<h2 class="mb-3 text-base font-semibold text-ink-gray-9">
									Connection Information
								</h2>
								<p class="mb-5 text-sm leading-relaxed text-ink-gray-6">
									This server is accessible through
									<strong class="text-ink-gray-8">Code</strong> or
									<strong class="text-ink-gray-8">SSH</strong>. Code is
									accessible under VPN in one click and you do not have to SSH
									into your lab. Just ensure you are connected to VPN. To keep
									you secure, this password changes during every redeploy.
								</p>
								<div class="space-y-0 divide-y divide-outline-gray-1">
									<div class="flex items-center gap-4 py-3">
										<label
											class="w-36 shrink-0 text-sm font-medium text-ink-gray-9"
											>Public Access</label
										>
										<div class="flex flex-1 items-center gap-3">
											<Switch
												:modelValue="!!activeBench.is_public"
												:disabled="visibilityAction.loading"
												@update:modelValue="onVisibilityChange"
											/>
											<span class="text-sm text-ink-gray-6">{{
												activeBench.is_public
													? "Anyone with the link can open this bench"
													: "Visitors must sign in with the credentials below"
											}}</span>
										</div>
									</div>
									<div
										v-if="
											!activeBench.is_public && activeBench.public_username
										"
										class="flex items-center gap-4 py-3"
									>
										<label
											class="w-36 shrink-0 text-sm font-medium text-ink-gray-9"
											>Access Username</label
										>
										<div class="flex flex-1 items-center gap-2">
											<code
												class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8"
												>{{ activeBench.public_username }}</code
											>
											<Button
												icon="copy"
												appearance="minimal"
												size="sm"
												@click="copyText(activeBench.public_username)"
											/>
										</div>
									</div>
									<div
										v-if="
											!activeBench.is_public && activeBench.public_password
										"
										class="flex items-center gap-4 py-3"
									>
										<label
											class="w-36 shrink-0 text-sm font-medium text-ink-gray-9"
											>Access Password</label
										>
										<div class="flex flex-1 items-center gap-2">
											<code
												class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8"
												>{{
													activeBench.public_password
														? "••••••••••••"
														: "—"
												}}</code
											>
											<Button
												icon="copy"
												appearance="minimal"
												size="sm"
												@click="copyText(activeBench.public_password)"
											/>
										</div>
									</div>
									<div
										v-if="activeBench.public_url"
										class="flex items-center gap-4 py-3"
									>
										<label
											class="w-36 shrink-0 text-sm font-medium text-ink-gray-9"
											>Public URL</label
										>
										<div class="flex flex-1 items-center gap-2">
											<a
												:href="activeBench.public_url"
												target="_blank"
												class="flex-1 truncate rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-blue-3 hover:underline"
												>{{ activeBench.public_url }}</a
											>
											<Button
												icon="copy"
												appearance="minimal"
												size="sm"
												@click="copyText(activeBench.public_url)"
											/>
										</div>
									</div>
									<div class="flex items-center gap-4 py-3">
										<label
											class="w-36 shrink-0 text-sm font-medium text-ink-gray-9"
											>Device IP</label
										>
										<div class="flex flex-1 items-center gap-2">
											<code
												class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8"
												>{{ benchIp ?? "—" }}</code
											>
											<Button
												icon="copy"
												appearance="minimal"
												size="sm"
												@click="copyText(benchIp)"
											/>
										</div>
									</div>
									<div class="flex items-center gap-4 py-3">
										<label
											class="w-36 shrink-0 text-sm font-medium text-ink-gray-9"
											>SSH Command</label
										>
										<div class="flex flex-1 items-center gap-2">
											<code
												class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8"
												>{{ sshCommand ?? "—" }}</code
											>
											<Button
												icon="copy"
												appearance="minimal"
												size="sm"
												@click="copyText(sshCommand)"
											/>
										</div>
									</div>
									<div class="flex items-center gap-4 py-3">
										<label
											class="w-36 shrink-0 text-sm font-medium text-ink-gray-9"
											>Username</label
										>
										<div class="flex flex-1 items-center gap-2">
											<code
												class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8"
												>{{ sshUsername ?? "—" }}</code
											>
											<Button
												icon="copy"
												appearance="minimal"
												size="sm"
												@click="copyText(sshUsername)"
											/>
										</div>
									</div>
									<div class="flex items-center gap-4 py-3">
										<label
											class="w-36 shrink-0 text-sm font-medium text-ink-gray-9"
											>su Password</label
										>
										<div class="flex flex-1 items-center gap-2">
											<code
												class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8"
												>{{ sshPassword ? "••••••••••••" : "—" }}</code
											>
											<Button
												icon="copy"
												appearance="minimal"
												size="sm"
												@click="copyText(sshPassword)"
											/>
										</div>
									</div>
									<div class="flex items-center gap-4 py-3">
										<label
											class="w-36 shrink-0 text-sm font-medium text-ink-gray-9"
											>Admin Password</label
										>
										<div class="flex flex-1 items-center gap-2">
											<code
												class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8"
												>{{ adminPassword ? "••••••••••••" : "—" }}</code
											>
											<Button
												icon="copy"
												appearance="minimal"
												size="sm"
												@click="copyText(adminPassword)"
											/>
										</div>
									</div>
									<div class="flex items-center gap-4 py-3">
										<label
											class="w-36 shrink-0 text-sm font-medium text-ink-gray-9"
											>VS Port Forward</label
										>
										<div class="flex flex-1 items-center gap-2">
											<code
												class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8"
												>{{ siteUrl ?? "—" }}</code
											>
											<Button
												icon="copy"
												appearance="minimal"
												size="sm"
												@click="copyText(siteUrl)"
											/>
										</div>
									</div>
									<div
										v-if="lab.doc.enable_code_server && codeServerUrl"
										class="flex items-center gap-4 py-3"
									>
										<label
											class="w-36 shrink-0 text-sm font-medium text-ink-gray-9"
											>VS Code URL</label
										>
										<div class="flex flex-1 items-center gap-2">
											<code
												class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8"
												>{{ codeServerUrl }}</code
											>
											<Button
												icon="copy"
												appearance="minimal"
												size="sm"
												@click="copyText(codeServerUrl)"
											/>
										</div>
									</div>
									<div
										v-if="lab.doc.enable_code_server && codeServerPassword"
										class="flex items-center gap-4 py-3"
									>
										<label
											class="w-36 shrink-0 text-sm font-medium text-ink-gray-9"
											>VS Code Password</label
										>
										<div class="flex flex-1 items-center gap-2">
											<code
												class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8"
												>{{
													codeServerPassword ? "••••••••••••" : "—"
												}}</code
											>
											<Button
												icon="copy"
												appearance="minimal"
												size="sm"
												@click="copyText(codeServerPassword)"
											/>
										</div>
									</div>
								</div>
							</div>
						</div>

						<!-- Right column -->
						<div class="flex flex-col gap-6">
							<!-- Container Status -->
							<div
								v-if="activeBench"
								class="rounded-lg border border-outline-gray-1 bg-surface-white p-5"
							>
								<div class="mb-4 flex items-center justify-between">
									<h2 class="text-base font-semibold text-ink-gray-9">
										Container Status
									</h2>
									<div class="flex items-center gap-2">
										<Badge
											v-if="activeBench.health_status"
											:label="activeBench.health_status"
											:theme="healthColor(activeBench.health_status)"
										/>
										<Badge
											:label="activeBench.status"
											:theme="statusColor(activeBench.status)"
										/>
									</div>
								</div>
								<div class="grid grid-cols-2 gap-4">
									<div class="rounded-lg border border-outline-gray-1 p-4">
										<div class="text-xs text-ink-gray-5">CPU Usage</div>
										<div class="mt-1 text-lg font-semibold text-ink-gray-9">
											{{ activeBench.cpu_usage || 0 }}%
										</div>
										<div
											class="mt-2 h-2 w-full rounded-full bg-surface-gray-2"
										>
											<div
												class="h-2 rounded-full bg-surface-blue-2"
												:style="{
													width: `${Math.min(
														activeBench.cpu_usage || 0,
														100
													)}%`,
												}"
											/>
										</div>
									</div>
									<div class="rounded-lg border border-outline-gray-1 p-4">
										<div class="text-xs text-ink-gray-5">Memory Usage</div>
										<div class="mt-1 text-lg font-semibold text-ink-gray-9">
											{{ activeBench.memory_usage || 0 }}%
										</div>
										<div
											class="mt-2 h-2 w-full rounded-full bg-surface-gray-2"
										>
											<div
												class="h-2 rounded-full bg-surface-blue-2"
												:style="{
													width: `${Math.min(
														activeBench.memory_usage || 0,
														100
													)}%`,
												}"
											/>
										</div>
									</div>
								</div>
								<div
									v-if="activeBench.started_at"
									class="mt-3 text-xs text-ink-gray-5"
								>
									Started: {{ activeBench.started_at }}
								</div>
							</div>

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
				<div v-if="tab.label === 'Sites'" class="p-4">
					<div class="mb-4 flex items-center justify-between">
						<h2 class="text-base font-semibold text-ink-gray-9">Sites</h2>
						<Button
							appearance="primary"
							icon-left="plus"
							:disabled="!activeBench"
							@click="showNewSite = true"
							>New Site</Button
						>
					</div>

					<!-- Sites list -->
					<ListView
						v-if="sites.data?.length"
						:columns="siteColumns"
						:rows="sites.data"
						:options="{ selectable: false, showTooltip: true, resizeColumn: true }"
						row-key="name"
					/>
					<div
						v-else-if="!activeBench"
						class="rounded-lg border border-outline-gray-1 bg-surface-white p-8 text-center"
					>
						<div class="text-sm text-ink-gray-5">
							Deploy this lab first to create sites.
						</div>
					</div>
					<div
						v-else
						class="rounded-lg border border-outline-gray-1 bg-surface-white p-8 text-center"
					>
						<div class="text-sm text-ink-gray-5">
							No sites yet. Create your first site.
						</div>
					</div>

					<!-- New Site Dialog -->
					<Dialog
						:options="{ title: 'Create New Site', size: 'sm' }"
						v-model="showNewSite"
					>
						<template #body-content>
							<div class="space-y-4">
								<FormControl
									label="Site Name"
									v-model="newSiteName"
									type="text"
									placeholder="e.g. mysite"
									:required="true"
								/>
								<div v-if="lab.doc.apps?.length">
									<label class="mb-2 block text-xs font-medium text-ink-gray-6"
										>Apps to Install</label
									>
									<div class="flex flex-wrap gap-2">
										<label
											v-for="app in lab.doc.apps"
											:key="app.app_name"
											class="flex cursor-pointer items-center gap-2 rounded border border-outline-gray-1 px-3 py-2 text-sm"
											:class="
												selectedApps.includes(app.app_name)
													? 'border-outline-blue-2 bg-surface-blue-1'
													: ''
											"
										>
											<input
												type="checkbox"
												:value="app.app_name"
												v-model="selectedApps"
												class="accent-surface-blue-2"
											/>
											{{ app.app_label || app.app_name }}
										</label>
									</div>
								</div>
							</div>
						</template>
						<template #actions>
							<Button
								appearance="primary"
								class="w-full"
								:loading="createSiteAction.loading"
								@click="createSite"
								>Create Site</Button
							>
						</template>
					</Dialog>
				</div>

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
	createResource,
	createDocumentResource,
	createListResource,
	Badge,
	Button,
	Switch,
	Tabs,
	ListView,
	Dialog,
	FormControl,
	ErrorMessage,
	Alert,
	toast,
} from "frappe-ui";
import LogViewer from "@/components/LogViewer.vue";
import { userContext } from "@/data/userContext";

const route = useRoute();
const labId = route.params.labId;
const activeTab = ref(0);
const showNewSite = ref(false);
const showDeployConfirm = ref(false);
const showStopConfirm = ref(false);
const newSiteName = ref("");
const selectedApps = ref([]);

const tabs = computed(() => {
	const base = [{ label: "Dashboard" }, { label: "Sites" }];
	if (lab.doc?.status === "Ready" || activeBench.value) {
		base.push({ label: "Deploy Log" });
	} else if (userContext.isAdmin) {
		base.push({ label: "Build Log" });
	}
	return base;
});

const siteColumns = [
	{ label: "Site Name", key: "site_name", width: "200px" },
	{ label: "Domain", key: "full_domain", width: "250px" },
	{ label: "Status", key: "status", width: "120px" },
];

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

const lab = createDocumentResource({
	doctype: "Lab",
	name: labId,
});

const benches = createResource({
	url: "benchpress.api.get_benches",
	auto: true,
});

const activeBench = computed(() => {
	if (!benches.data) return null;
	return benches.data.find((b) => b.lab === labId) || null;
});

const sites = createListResource({
	doctype: "Bench Site",
	fields: ["name", "site_name", "full_domain", "status"],
	filters: computed(() => ({ bench: activeBench.value?.name || "" })),
	orderBy: "creation desc",
	auto: computed(() => !!activeBench.value),
});

const deployLogs = createResource({
	url: "benchpress.api.get_deploy_logs",
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

const buildLogs = createListResource({
	doctype: "Build Log",
	fields: ["name", "message", "log_type", "timestamp"],
	filters: { lab: labId },
	orderBy: "timestamp desc",
	pageLength: 20,
	auto: true,
});

const buildAction = createResource({
	url: "benchpress.api.build_lab_image",
	onSuccess() {
		lab.reload();
		buildLogs.reload();
	},
});

function buildLabImage() {
	liveBuildLog.value = "";
	buildAction.submit({ lab_name: labId });
}

const deployAction = createResource({
	url: "benchpress.api.create_bench",
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

const benchAction = createResource({
	url: "benchpress.api.bench_action",
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

const visibilityAction = createResource({
	url: "benchpress.api.set_bench_visibility",
	onSuccess() {
		liveDeployLog.value = "";
		deployComplete.value = false;
		benches.reload();
		toast.success("Updating bench visibility — this re-creates the container.");
	},
	onError(err) {
		toast.error(err?.messages?.[0] || "Failed to update visibility");
	},
});

function onVisibilityChange(value) {
	if (!activeBench.value) return;
	visibilityAction.submit({
		bench_name: activeBench.value.name,
		is_public: value ? 1 : 0,
	});
}

const createSiteAction = createResource({
	url: "benchpress.api.create_site",
	onSuccess() {
		showNewSite.value = false;
		newSiteName.value = "";
		selectedApps.value = [];
		sites.reload();
	},
});

function createSite() {
	if (!newSiteName.value || !activeBench.value) return;
	createSiteAction.submit({
		data: JSON.stringify({
			site_name: newSiteName.value,
			bench: activeBench.value.name,
			apps: selectedApps.value.map((name) => ({ name })),
		}),
	});
}

const copyAlert = ref("");

function copyText(text) {
	navigator.clipboard.writeText(text);
	copyAlert.value = "Copied to clipboard!";
	setTimeout(() => {
		copyAlert.value = "";
	}, 2000);
}

function statusColor(status) {
	const map = {
		Draft: "gray",
		Building: "orange",
		Ready: "green",
		Running: "green",
		Deploying: "orange",
		Stopped: "red",
		Error: "red",
		Active: "green",
		Creating: "orange",
		Inactive: "gray",
	};
	return map[status] || "gray";
}

function healthColor(health) {
	const map = { Healthy: "green", Unhealthy: "red", Unknown: "gray" };
	return map[health] || "gray";
}
</script>

<style scoped>
.slide-in-enter-active {
	transition: all 0.3s ease-out;
}
.slide-in-leave-active {
	transition: all 0.2s ease-in;
}
.slide-in-enter-from {
	transform: translateX(100%);
	opacity: 0;
}
.slide-in-leave-to {
	transform: translateX(100%);
	opacity: 0;
}
</style>
