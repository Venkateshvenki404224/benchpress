<template>
  <div class="p-6">
    <Dialog
      :options="{ title: 'Benchpress Settings', size: 'xl' }"
      v-model="showDialog"
    >
      <template #body-content>
        <div v-if="settings.data" class="space-y-6">
          <!-- Docker Configuration -->
          <div>
            <h3 class="mb-3 text-sm font-semibold text-ink-gray-8">Docker Configuration</h3>
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
            <h3 class="mb-3 text-sm font-semibold text-ink-gray-8">WireGuard Configuration</h3>
            <div class="grid grid-cols-2 gap-4">
              <FormControl
                label="WG Server IP"
                v-model="form.wg_server_ip"
                type="text"
              />
              <FormControl
                label="WG Subnet"
                v-model="form.wg_subnet"
                type="text"
              />
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
            <h3 class="mb-3 text-sm font-semibold text-ink-gray-8">Container Resource Limits</h3>
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
        <div v-else class="py-8 text-center text-sm text-ink-gray-5">Loading settings...</div>
      </template>
      <template #actions>
        <div class="flex w-full justify-end gap-2">
          <Button @click="showDialog = false">Cancel</Button>
          <Button appearance="primary" :loading="saveAction.loading" @click="saveSettings">Save</Button>
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { createResource, Dialog, FormControl, Button } from 'frappe-ui'

const router = useRouter()
const showDialog = ref(true)

const form = reactive({
  base_domain: '',
  default_image: '',
  traefik_network: '',
  docker_socket: '',
  wg_server_ip: '',
  wg_subnet: '',
  wg_server_port: '',
  wg_server_endpoint: '',
  wg_server_public_key: '',
  container_memory_limit: '',
  container_cpu_quota: '',
})

const settings = createResource({
  url: 'benchpress.api.get_settings',
  auto: true,
  onSuccess(data) {
    Object.assign(form, {
      base_domain: data.base_domain || '',
      default_image: data.default_image || '',
      traefik_network: data.traefik_network || '',
      docker_socket: data.docker_socket || '',
      wg_server_ip: data.wg_server_ip || '',
      wg_subnet: data.wg_subnet || '',
      wg_server_port: data.wg_server_port || '',
      wg_server_endpoint: data.wg_server_endpoint || '',
      wg_server_public_key: data.wg_server_public_key || '',
      container_memory_limit: data.container_memory_limit || '',
      container_cpu_quota: data.container_cpu_quota || '',
    })
  },
})

const saveAction = createResource({
  url: 'frappe.client.save',
  onSuccess() {
    showDialog.value = false
  },
})

function saveSettings() {
  saveAction.submit({
    doc: JSON.stringify({
      doctype: 'BenchPress Settings',
      name: 'BenchPress Settings',
      ...form,
    }),
  })
}

watch(showDialog, (val) => {
  if (!val) {
    router.back()
  }
})
</script>
