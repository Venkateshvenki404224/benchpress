<template>
  <div class="p-6" v-if="lab.data">
    <!-- Header -->
    <div class="mb-6 flex items-start justify-between">
      <div>
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-bold text-ink-gray-9">{{ lab.data.title }}</h1>
          <Badge :label="lab.data.status" :theme="statusColor(lab.data.status)" />
        </div>
        <div class="mt-2 flex items-center gap-2 text-sm text-ink-gray-5">
          <span>Lab ID:</span>
          <code class="rounded bg-surface-gray-2 px-1.5 py-0.5 font-mono text-xs text-ink-gray-7">{{ lab.data.lab_id }}</code>
        </div>
        <p v-if="lab.data.description" class="mt-3 max-w-xl text-sm text-ink-gray-6">
          {{ lab.data.description }}
        </p>
        <div class="mt-3 flex gap-3">
          <Badge :label="lab.data.frappe_version" theme="blue" variant="outline" />
          <Badge :label="`${lab.data.memory_limit} RAM`" theme="gray" variant="outline" />
          <Badge :label="`${lab.data.cpu_cores} CPU`" theme="gray" variant="outline" />
        </div>
      </div>
      <div class="flex gap-2">
        <!-- No instance: show Deploy -->
        <Button
          v-if="!activeBench"
          appearance="primary"
          size="lg"
          :loading="deployAction.loading"
          @click="deployLab"
        >Deploy</Button>
        <!-- Instance running: show Stop + Redeploy -->
        <Button
          v-if="activeBench && activeBench.status === 'Running'"
          size="lg"
          :loading="benchAction.loading"
          @click="doBenchAction('stop')"
        >Stop</Button>
        <Button
          v-if="activeBench && activeBench.status === 'Running'"
          appearance="primary"
          size="lg"
          :loading="redeployAction.loading"
          @click="doBenchAction('redeploy')"
        >Redeploy</Button>
        <!-- Instance stopped: show Deploy again -->
        <Button
          v-if="activeBench && activeBench.status === 'Stopped'"
          appearance="primary"
          size="lg"
          :loading="deployAction.loading"
          @click="deployLab"
        >Deploy</Button>
      </div>
    </div>

    <!-- Tabs -->
    <Tabs :tabs="tabs" v-model="activeTab">
      <template #tab-panel="{ tab }">
        <!-- Dashboard Tab -->
        <div v-if="tab.label === 'Dashboard'" class="p-4">
          <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <!-- Left column -->
            <div class="flex flex-col gap-6">
              <!-- Lab Information -->
              <div class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
                <div class="mb-3 flex items-center gap-2">
                  <h2 class="text-base font-semibold text-ink-gray-9">Lab Information</h2>
                  <span class="text-xs text-ink-gray-5">Readme</span>
                </div>
                <p v-if="lab.data.description" class="mb-4 text-sm text-ink-gray-6">
                  {{ lab.data.description }}
                </p>
                <p v-else class="mb-4 text-sm text-ink-gray-5">
                  This lab is not running, please deploy it to get the connection information.
                </p>
                <div v-if="lab.data.apps?.length" class="mt-4">
                  <h3 class="mb-2 text-sm font-medium text-ink-gray-7">Installed Apps</h3>
                  <div class="flex flex-wrap gap-2">
                    <Badge
                      v-for="app in lab.data.apps"
                      :key="app.app_name"
                      :label="app.app_label || app.app_name"
                      theme="blue"
                      variant="outline"
                    />
                  </div>
                </div>
              </div>

              <!-- Connection Info -->
              <div v-if="activeBench" class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
                <div class="mb-3 flex items-center gap-2">
                  <h2 class="text-base font-semibold text-ink-gray-9">Lab Information</h2>
                  <span class="text-xs text-ink-gray-5">Readme</span>
                </div>
                <p class="mb-5 text-sm leading-relaxed text-ink-gray-6">
                  This server is accessible through <strong class="text-ink-gray-8">Code</strong> or <strong class="text-ink-gray-8">SSH</strong>.
                  Code is accessible under VPN in one click and you do not have to SSH into your lab.
                  Just ensure you are connected to VPN. To keep you secure, this password changes during every redeploy.
                </p>
                <div class="space-y-0 divide-y divide-outline-gray-1">
                  <div class="flex items-center gap-4 py-3">
                    <label class="w-36 shrink-0 text-sm font-medium text-ink-gray-9">Device IP</label>
                    <div class="flex flex-1 items-center gap-2">
                      <code class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8">{{ activeBench.wg_ip || '—' }}</code>
                      <Button icon="copy" appearance="minimal" size="sm" @click="copyText(activeBench.wg_ip || '')" />
                    </div>
                  </div>
                  <div class="flex items-center gap-4 py-3">
                    <label class="w-36 shrink-0 text-sm font-medium text-ink-gray-9">SSH Command</label>
                    <div class="flex flex-1 items-center gap-2">
                      <code class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8">{{ sshCommand }}</code>
                      <Button icon="copy" appearance="minimal" size="sm" @click="copyText(sshCommand)" />
                    </div>
                  </div>
                  <div class="flex items-center gap-4 py-3">
                    <label class="w-36 shrink-0 text-sm font-medium text-ink-gray-9">Username</label>
                    <div class="flex flex-1 items-center gap-2">
                      <code class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8">{{ sshUsername }}</code>
                      <Button icon="copy" appearance="minimal" size="sm" @click="copyText(sshUsername)" />
                    </div>
                  </div>
                  <div class="flex items-center gap-4 py-3">
                    <label class="w-36 shrink-0 text-sm font-medium text-ink-gray-9">su Password</label>
                    <div class="flex flex-1 items-center gap-2">
                      <code class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8">{{ showPassword ? sshPassword : '••••••••••••' }}</code>
                      <Button :icon="showPassword ? 'eye-off' : 'eye'" appearance="minimal" size="sm" @click="showPassword = !showPassword" />
                      <Button icon="copy" appearance="minimal" size="sm" @click="copyText(sshPassword)" />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Right column -->
            <div class="flex flex-col gap-6">
              <!-- Container Status -->
              <div v-if="activeBench" class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
                <div class="mb-4 flex items-center justify-between">
                  <h2 class="text-base font-semibold text-ink-gray-9">Container Status</h2>
                  <Badge :label="activeBench.status" :theme="statusColor(activeBench.status)" />
                </div>
                <div class="grid grid-cols-2 gap-4">
                  <div class="rounded-lg border border-outline-gray-1 p-4">
                    <div class="text-xs text-ink-gray-5">CPU Usage</div>
                    <div class="mt-1 text-lg font-semibold text-ink-gray-9">{{ activeBench.cpu_usage || 0 }}%</div>
                    <div class="mt-2 h-2 w-full rounded-full bg-surface-gray-2">
                      <div class="h-2 rounded-full bg-surface-blue-2" :style="{ width: `${Math.min(activeBench.cpu_usage || 0, 100)}%` }" />
                    </div>
                  </div>
                  <div class="rounded-lg border border-outline-gray-1 p-4">
                    <div class="text-xs text-ink-gray-5">Memory Usage</div>
                    <div class="mt-1 text-lg font-semibold text-ink-gray-9">{{ activeBench.memory_usage || 0 }}%</div>
                    <div class="mt-2 h-2 w-full rounded-full bg-surface-gray-2">
                      <div class="h-2 rounded-full bg-surface-blue-2" :style="{ width: `${Math.min(activeBench.memory_usage || 0, 100)}%` }" />
                    </div>
                  </div>
                </div>
                <div v-if="activeBench.started_at" class="mt-3 text-xs text-ink-gray-5">
                  Started: {{ activeBench.started_at }}
                </div>
              </div>


              <!-- No deployment yet -->
              <div v-if="!activeBench && !benches.loading" class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
                <div class="py-6 text-center">
                  <div class="text-sm text-ink-gray-5">No active deployment</div>
                  <p class="mt-1 text-xs text-ink-gray-4">Click "Deploy" to create a new bench instance from this lab.</p>
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
            >New Site</Button>
          </div>

          <!-- Sites list -->
          <ListView
            v-if="sites.data?.length"
            :columns="siteColumns"
            :rows="sites.data"
            :options="{ selectable: false, showTooltip: true, resizeColumn: true }"
            row-key="name"
          />
          <div v-else-if="!activeBench" class="rounded-lg border border-outline-gray-1 bg-surface-white p-8 text-center">
            <div class="text-sm text-ink-gray-5">Deploy this lab first to create sites.</div>
          </div>
          <div v-else class="rounded-lg border border-outline-gray-1 bg-surface-white p-8 text-center">
            <div class="text-sm text-ink-gray-5">No sites yet. Create your first site.</div>
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
                <div v-if="lab.data.apps?.length">
                  <label class="mb-2 block text-xs font-medium text-ink-gray-6">Apps to Install</label>
                  <div class="flex flex-wrap gap-2">
                    <label
                      v-for="app in lab.data.apps"
                      :key="app.app_name"
                      class="flex cursor-pointer items-center gap-2 rounded border border-outline-gray-1 px-3 py-2 text-sm"
                      :class="selectedApps.includes(app.app_name) ? 'border-outline-blue-2 bg-surface-blue-1' : ''"
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
              >Create Site</Button>
            </template>
          </Dialog>
        </div>
      </template>
    </Tabs>
  </div>

  <!-- Loading state -->
  <div v-else class="flex items-center justify-center p-12">
    <div class="text-base text-ink-gray-5">Loading lab details...</div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { createResource, Badge, Button, Tabs, ListView, Dialog, FormControl } from 'frappe-ui'

const route = useRoute()
const labId = route.params.labId
const showPassword = ref(false)
const activeTab = ref(0)
const showNewSite = ref(false)
const newSiteName = ref('')
const selectedApps = ref([])

const tabs = [
  { label: 'Dashboard' },
  { label: 'Sites' },
]

const siteColumns = [
  { label: 'Site Name', key: 'site_name', width: '200px' },
  { label: 'Domain', key: 'full_domain', width: '250px' },
  { label: 'Status', key: 'status', width: '120px' },
]

const sshUsername = computed(() => activeBench.value ? 'frappe' : '')
const sshPassword = computed(() => activeBench.value?.admin_password || 'admin')
const sshCommand = computed(() => {
  const ip = activeBench.value?.wg_ip || activeBench.value?.name || 'localhost'
  return `ssh frappe@${ip}`
})

const lab = createResource({
  url: 'benchpress.api.get_lab',
  params: { name: labId },
  auto: true,
})

const benches = createResource({
  url: 'benchpress.api.get_benches',
  auto: true,
})

const activeBench = computed(() => {
  if (!benches.data) return null
  return benches.data.find(b => b.lab === labId) || null
})

const sites = createResource({
  url: 'benchpress.api.get_sites',
  params: { bench_name: computed(() => activeBench.value?.name || '') },
  auto: computed(() => !!activeBench.value),
})

const deployAction = createResource({
  url: 'benchpress.api.create_bench',
  onSuccess() {
    benches.reload()
  },
})

function deployLab() {
  deployAction.submit({
    data: JSON.stringify({ lab: labId }),
  })
}

const benchAction = createResource({
  url: 'benchpress.api.bench_action',
  onSuccess() {
    benches.reload()
  },
})

function doBenchAction(action) {
  if (!activeBench.value) return
  if (action === 'redeploy') {
    redeployAction.submit({
      dt: 'Bench Instance',
      dn: activeBench.value.name,
      method: 'enqueue_redeploy',
    })
    return
  }
  benchAction.submit({
    bench_name: activeBench.value.name,
    action,
  })
}

const redeployAction = createResource({
  url: 'frappe.client.run_doc_method',
  onSuccess() {
    benches.reload()
  },
})

const createSiteAction = createResource({
  url: 'benchpress.api.create_site',
  onSuccess() {
    showNewSite.value = false
    newSiteName.value = ''
    selectedApps.value = []
    sites.reload()
  },
})

function createSite() {
  if (!newSiteName.value || !activeBench.value) return
  createSiteAction.submit({
    data: JSON.stringify({
      site_name: newSiteName.value,
      bench: activeBench.value.name,
      apps: selectedApps.value.map(name => ({ name })),
    }),
  })
}

function copyText(text) {
  navigator.clipboard.writeText(text)
}

function statusColor(status) {
  const map = {
    Draft: 'gray',
    Building: 'orange',
    Ready: 'green',
    Running: 'green',
    Deploying: 'orange',
    Stopped: 'red',
    Error: 'red',
    Active: 'green',
    Creating: 'orange',
    Inactive: 'gray',
  }
  return map[status] || 'gray'
}
</script>
