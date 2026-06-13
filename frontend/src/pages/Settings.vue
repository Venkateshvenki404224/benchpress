<template>
	<div class="p-6">
		<Dialog :options="{ title: 'Benchpress Settings', size: 'xl' }" v-model="showDialog">
			<template #body-content>
				<div v-if="settings.doc" class="space-y-6">
					<!-- Docker Configuration -->
					<div>
						<h3 class="mb-3 text-sm font-semibold text-ink-gray-8">
							Docker Configuration
						</h3>
						<div class="grid grid-cols-2 gap-4">
							<FormControl
								label="Base Domain"
								v-model="form.base_domain"
								type="text"
							/>
							<FormControl
								label="Default Image"
								v-model="form.default_image"
								type="text"
							/>
							<FormControl
								label="Traefik Network"
								v-model="form.traefik_network"
								type="text"
							/>
							<FormControl
								label="Docker Socket"
								v-model="form.docker_socket"
								type="text"
							/>
						</div>
					</div>

					<!-- WireGuard Configuration -->
					<div>
						<h3 class="mb-3 text-sm font-semibold text-ink-gray-8">
							WireGuard Configuration
						</h3>
						<div class="grid grid-cols-2 gap-4">
							<FormControl
								label="WG Server IP"
								v-model="form.wg_server_ip"
								type="text"
							/>
							<FormControl label="WG Subnet" v-model="form.wg_subnet" type="text" />
							<FormControl
								label="WG Server Port"
								v-model="form.wg_server_port"
								type="text"
							/>
							<FormControl
								label="WG Server Endpoint"
								v-model="form.wg_server_endpoint"
								type="text"
							/>
							<FormControl
								label="WG Server Public Key"
								v-model="form.wg_server_public_key"
								type="text"
							/>
						</div>
					</div>

					<!-- Resource Limits -->
					<div>
						<h3 class="mb-3 text-sm font-semibold text-ink-gray-8">
							Container Resource Limits
						</h3>
						<div class="grid grid-cols-2 gap-4">
							<FormControl
								label="Memory Limit"
								v-model="form.container_memory_limit"
								type="text"
								description="e.g. 512m, 1g, 2g"
							/>
							<FormControl
								label="CPU Quota"
								v-model="form.container_cpu_quota"
								type="text"
								description="Microseconds (100000 = 1 core)"
							/>
						</div>
					</div>
				</div>
				<div v-else class="py-8 text-center text-sm text-ink-gray-5">
					Loading settings...
				</div>
			</template>
			<template #actions>
				<div class="w-full space-y-2">
					<ErrorMessage :message="settings.setValue.error" />
					<div class="flex justify-end gap-2">
						<Button variant="ghost" @click="showDialog = false">Cancel</Button>
						<Button
							variant="solid"
							theme="gray"
							:loading="settings.setValue.loading"
							@click="saveSettings"
							>Save</Button
						>
					</div>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { ref, reactive, watch } from "vue";
import { useRouter } from "vue-router";
import { useDoc, Dialog, FormControl, Button, ErrorMessage } from "frappe-ui";

const router = useRouter();
const showDialog = ref(true);

const form = reactive({
	base_domain: "",
	default_image: "",
	traefik_network: "",
	docker_socket: "",
	wg_server_ip: "",
	wg_subnet: "",
	wg_server_port: "",
	wg_server_endpoint: "",
	wg_server_public_key: "",
	container_memory_limit: "",
	container_cpu_quota: "",
});

function fillForm(doc) {
	Object.assign(form, {
		base_domain: doc.base_domain || "",
		default_image: doc.default_image || "",
		traefik_network: doc.traefik_network || "",
		docker_socket: doc.docker_socket || "",
		wg_server_ip: doc.wg_server_ip || "",
		wg_subnet: doc.wg_subnet || "",
		wg_server_port: doc.wg_server_port || "",
		wg_server_endpoint: doc.wg_server_endpoint || "",
		wg_server_public_key: doc.wg_server_public_key || "",
		container_memory_limit: doc.container_memory_limit || "",
		container_cpu_quota: doc.container_cpu_quota || "",
	});
}

const settings = useDoc({
	doctype: "BenchPress Settings",
	name: "BenchPress Settings",
});

settings.onSuccess(fillForm);
if (settings.doc) fillForm(settings.doc);

async function saveSettings() {
	const saved = await settings.setValue.submit({ ...form });
	if (saved) {
		showDialog.value = false;
	}
}

watch(showDialog, (val) => {
	if (!val) {
		router.push("/labs");
	}
});
</script>
