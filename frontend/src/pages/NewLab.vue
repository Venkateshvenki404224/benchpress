<template>
	<div class="page-shell" data-test="new-lab">
		<BackLink to="/labs" label="Labs" />

		<div class="mb-3.5">
			<h1 class="text-title font-semibold text-ink-gray-9">New lab</h1>
			<p class="mt-0.5 max-w-[620px] text-body text-ink-gray-5">
				Define the recipe once. Everything below is baked into the image, so every bench
				deployed from this lab is identical.
			</p>
		</div>

		<ErrorMessage class="mb-3" :message="saveError" />

		<div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_296px]">
			<div class="flex min-w-0 flex-col gap-4">
				<SectionCard title="Identity">
					<div class="grid gap-4 sm:grid-cols-2">
						<FormControl
							label="Title"
							type="text"
							v-model="form.title"
							placeholder="Support Sandbox"
							data-test="lab-title"
						/>
						<div>
							<FormControl
								label="Lab ID"
								type="text"
								class="[&_input]:font-mono [&_input]:text-xs"
								:model-value="form.lab_id"
								readonly
								data-test="lab-id"
							/>
							<p class="mt-1.5 text-2xs text-ink-gray-5">
								Cannot change later — used in the container name and site domain.
							</p>
							<ErrorMessage class="mt-1" :message="labIdMessage" />
						</div>
					</div>

					<!-- The hook is on the wrapper: frappe-ui's Textarea binds `$attrs`
					     to the textarea *and* inherits them on its root div, so a
					     `data-test` passed to the control lands on two elements. -->
					<div class="mt-4" data-test="lab-description">
						<FormControl
							label="Description"
							type="textarea"
							v-model="form.description"
							placeholder="What this environment is for."
						/>
					</div>

					<div class="mt-4">
						<p class="mb-1.5 text-xs font-medium text-ink-gray-7">Frappe version</p>
						<TabButtons
							v-model="form.frappe_version"
							:buttons="versionButtons"
							data-test="frappe-version"
						/>
					</div>
				</SectionCard>

				<LabAppsTable
					:apps="form.apps"
					@add="addApp"
					@remove="removeApp"
					@update="updateApp"
				/>

				<SectionCard>
					<div class="mb-3.5 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
						<h2 class="text-sm font-semibold text-ink-gray-9">Resources and access</h2>
						<p class="text-meta text-ink-gray-5">Applied as container limits</p>
					</div>

					<InstanceSizePicker
						v-if="instanceSizes.length"
						class="mb-3.5"
						:sizes="instanceSizes"
						:priced="creditsPriced"
						v-model="form.instance_size"
					/>

					<div
						class="grid gap-3.5"
						style="grid-template-columns: repeat(auto-fit, minmax(150px, 1fr))"
					>
						<FormControl
							v-for="field in resourceFields"
							:key="field.key"
							:label="field.label"
							:type="field.type"
							v-model="form[field.key]"
							:description="field.description"
							:data-test="field.key"
						/>
					</div>
					<ErrorMessage class="mt-1.5" :message="cpuMessage" />

					<div
						class="mt-4 flex flex-wrap gap-x-8 gap-y-4 border-t border-outline-gray-1 pt-4"
					>
						<Switch
							v-model="codeServer"
							label="Code server"
							description="Browser VS Code on the bench"
							data-test="enable-code-server"
						/>
						<Switch
							v-model="ssh"
							label="SSH access"
							description="Adds an ssh user to the container"
							data-test="enable-ssh"
						/>
					</div>
				</SectionCard>
			</div>

			<NewLabSummary
				:lines="summaryLines"
				:saving="savingDraft"
				:building="building"
				@build="saveAndBuild"
				@draft="saveDraft"
			/>
		</div>
	</div>
</template>

<script setup>
import BackLink from "@/components/BackLink.vue";
import SectionCard from "@/components/SectionCard.vue";
import InstanceSizePicker from "@/components/lab/InstanceSizePicker.vue";
import LabAppsTable from "@/components/lab/LabAppsTable.vue";
import NewLabSummary from "@/components/lab/NewLabSummary.vue";
import { openDeployRun } from "@/data/deployRun";
import { labsResource } from "@/data/labs";
import { buildSummary, completeApps, cpuCoresError, labIdError, slugify } from "@/utils/labForm";
import { ErrorMessage, FormControl, Switch, TabButtons, createResource, toast } from "frappe-ui";
import { computed, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

// The lab ID is derived, never typed: it is the Docker tag and the site domain,
// and `docker_manager.validate_lab_id` rejects anything outside its grammar. The
// form applies that grammar itself so a title that cannot become a valid ID is
// caught here rather than by a server throw after the user has filled the page.
//
// Memory and cores are the *first two* deliberately: an instance size sets both,
// so the picker replaces them whenever any size exists. They stay reachable for a
// site with no sizes at all, which is the only way to hand-type limits.
const SIZED_FIELDS = 2;
const RESOURCE_FIELDS = [
	{ key: "memory_limit", label: "Memory limit", type: "text" },
	{ key: "cpu_cores", label: "CPU cores", type: "number" },
	{ key: "iops_limit", label: "Max IOPS", type: "number", description: "0 = default (1000)" },
	{
		key: "bps_limit",
		label: "Max bytes/sec",
		type: "number",
		description: "0 = default (40 MiB/s)",
	},
	{
		key: "pids_limit",
		label: "Max processes",
		type: "number",
		description: "0 = default (500)",
	},
];

const router = useRouter();
const savingDraft = ref(false);
const building = ref(false);
const submitted = ref(false);

const form = reactive({
	lab_id: "",
	title: "",
	description: "",
	frappe_version: "version-16",
	instance_size: "",
	memory_limit: "512m",
	cpu_cores: 1,
	iops_limit: 0,
	bps_limit: 0,
	pids_limit: 0,
	// The design starts a new lab with the browser IDE on and SSH off: code
	// server is the way in that needs no key, and an ssh user is opt-in.
	enable_code_server: 1,
	enable_ssh: 0,
	apps: [],
});

// The version list, the sizes and the numeric defaults are all declared
// server-side; this reads them rather than restating them.
const options = createResource({
	url: "benchpress.api.get_lab_form_options",
	auto: true,
	onSuccess(data) {
		for (const [field, value] of Object.entries(data?.defaults ?? {})) {
			if (field !== "enable_ssh" && value !== null && value !== undefined) {
				form[field] = field.startsWith("enable_") ? Number(value) : value;
			}
		}
		form.instance_size = defaultSize(data?.instance_sizes)?.name ?? "";
	},
});

const instanceSizes = computed(() => options.data?.instance_sizes ?? []);
const creditsPriced = computed(() => options.data?.credits_enabled === true);

// A size owns memory and cores, so the two free-text fields disappear behind it.
const resourceFields = computed(() =>
	instanceSizes.value.length ? RESOURCE_FIELDS.slice(SIZED_FIELDS) : RESOURCE_FIELDS
);

const chosenSize = computed(() =>
	instanceSizes.value.find((size) => size.name === form.instance_size)
);

function defaultSize(sizes) {
	return (sizes ?? []).find((size) => size.is_default) ?? (sizes ?? [])[0];
}

// The only writer: the deploy reads the size itself, so nothing rewrites these at
// save time. The inserted document has to say what the user was shown.
watch(chosenSize, (size) => {
	if (!size) return;
	form.memory_limit = size.memory_limit;
	form.cpu_cores = size.cpu_cores;
});

const versionButtons = computed(() =>
	(options.data?.frappe_versions ?? [form.frappe_version]).map((version) => ({
		label: version,
		value: version,
	}))
);

watch(
	() => form.title,
	(title) => {
		form.lab_id = slugify(title);
	}
);

const codeServer = computed({
	get: () => Boolean(form.enable_code_server),
	set: (value) => {
		form.enable_code_server = value ? 1 : 0;
	},
});

const ssh = computed({
	get: () => Boolean(form.enable_ssh),
	set: (value) => {
		form.enable_ssh = value ? 1 : 0;
	},
});

const summaryLines = computed(() => buildSummary(form, chosenSize.value, creditsPriced.value));

// Validation appears once the user has tried to save, so an untouched form is
// not scolded, and stays live afterwards so a fix clears it as it is typed.
const labIdMessage = computed(() => (submitted.value ? labIdError(form.lab_id) : ""));
const cpuMessage = computed(() => (submitted.value ? cpuCoresError(form.cpu_cores) : ""));

const insertLab = createResource({ url: "frappe.client.insert" });
const deployAction = createResource({ url: "benchpress.api.launch_lab" });

const saveError = computed(() => insertLab.error || deployAction.error || "");

function addApp() {
	form.apps.push({ app_name: "", git_url: "", branch: "" });
}

function removeApp(index) {
	form.apps.splice(index, 1);
}

function updateApp({ index, field, value }) {
	form.apps[index][field] = value;
}

/** Every reason this form would be rejected, checked before the server sees it. */
function formErrors() {
	submitted.value = true;
	return [labIdError(form.lab_id), cpuCoresError(form.cpu_cores)].filter(Boolean);
}

/**
 * Insert the lab, or report why it could not be inserted.
 *
 * `createResource.submit` resolves with the last successful payload rather than
 * throwing, so the error is read off the resource — the previous version of this
 * page swallowed save failures in an empty `catch` and left the user on a form
 * that looked like it had worked.
 */
async function saveLab() {
	const errors = formErrors();
	if (errors.length) {
		toast.error(errors[0]);
		return null;
	}

	const lab = await insertLab.submit({ doc: { doctype: "Lab", ...labDoc() } });
	if (insertLab.error || !lab?.name) {
		toast.error(saveFailure(insertLab.error));
		return null;
	}
	labsResource.reload();
	return lab;
}

function labDoc() {
	return { ...form, status: "Draft", apps: completeApps(form.apps) };
}

/** What the server refused, in the sentence it used. */
function saveFailure(error) {
	const reason = error?.messages?.[0] || error?.message || error;
	return `Could not save the lab: ${reason}`;
}

/**
 * Why the deploy was refused, in the server's own words.
 *
 * A credit or cap refusal names the shortfall and the route out of it, so
 * repeating it verbatim is the whole point — a generic "could not be started"
 * would throw away the only actionable half of the message.
 */
function deployFailure(error) {
	const reason = error?.messages?.[0] || error?.message || "";
	return reason
		? `The lab was saved, but the deploy was refused: ${reason}`
		: "The lab was saved, but the build could not be started.";
}

async function saveDraft() {
	savingDraft.value = true;
	try {
		const lab = await saveLab();
		if (lab) {
			toast.success(`${lab.name} saved as a draft.`);
			router.push({ name: "LabDetail", params: { labId: lab.name } });
		}
	} finally {
		savingDraft.value = false;
	}
}

/**
 * Save, then deploy — the deploy pipeline builds the image as its second step,
 * so "Save and build image" is one run the phase-4 dialog can follow rather
 * than an image build the user is then left to deploy by hand.
 */
async function saveAndBuild() {
	building.value = true;
	try {
		const lab = await saveLab();
		if (!lab) return;

		const run = await deployAction.submit({ data: JSON.stringify({ lab: lab.name }) });
		if (deployAction.error || !run?.bench) {
			toast.error(deployFailure(deployAction.error));
			router.push({ name: "LabDetail", params: { labId: lab.name } });
			return;
		}
		openDeployRun({
			labId: lab.name,
			labTitle: run.lab_title,
			benchName: run.bench,
			willBuild: run.will_build,
		});
		router.push({ name: "LabDetail", params: { labId: lab.name } });
	} finally {
		building.value = false;
	}
}
</script>
