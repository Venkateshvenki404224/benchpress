<template>
  <div class="p-6" v-if="lab.data">
    <!-- Header -->
    <div class="mb-6 flex items-start justify-between">
      <div>
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-bold text-ink-gray-9">{{ lab.data.title }}</h1>
          <Badge :label="lab.data.status" :theme="statusColor(lab.data.status)" />
        </div>
        <div class="mt-1 flex items-center gap-2 text-sm text-ink-gray-5">
          <span>Lab ID:</span>
          <code class="rounded bg-surface-gray-2 px-1.5 py-0.5 font-mono text-xs text-ink-gray-7">{{ lab.data.lab_id }}</code>
        </div>
        <p v-if="lab.data.description" class="mt-2 max-w-xl text-sm text-ink-gray-6">
          {{ lab.data.description }}
        </p>
        <div class="mt-2 flex gap-2">
          <Badge :label="lab.data.frappe_version" theme="blue" variant="outline" />
          <Badge :label="`${lab.data.memory_limit} RAM`" theme="gray" variant="outline" />
          <Badge :label="`${lab.data.cpu_cores} CPU`" theme="gray" variant="outline" />
        </div>
      </div>
      <Button
        appearance="primary"
        size="lg"
        :loading="deployAction.loading"
        @click="deployLab"
      >
        Deploy
      </Button>
    </div>

    <!-- Two-column grid -->
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

          <!-- Apps list -->
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

        <!-- Connection Info (shown when bench exists) -->
        <div v-if="activeBench" class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
          <h2 class="mb-4 text-base font-semibold text-ink-gray-9">Connection Details</h2>
          <div class="space-y-3">
            <div v-if="activeBench.wg_ip">
              <label class="text-xs font-medium text-ink-gray-5">IP Address</label>
              <div class="mt-1 flex items-center gap-2">
                <code class="flex-1 rounded bg-surface-gray-2 px-3 py-2 font-mono text-sm text-ink-gray-8">{{ activeBench.wg_ip }}</code>
                <Button icon="copy" appearance="minimal" size="sm" @click="copyText(activeBench.wg_ip)" />
              </div>
            </div>
            <div v-if="activeBench.wg_ip">
              <label class="text-xs font-medium text-ink-gray-5">SSH Command</label>
              <div class="mt-1 flex items-center gap-2">
                <code class="flex-1 rounded bg-surface-gray-2 px-3 py-2 font-mono text-sm text-ink-gray-8">ssh frappe@{{ activeBench.wg_ip }}</code>
                <Button icon="copy" appearance="minimal" size="sm" @click="copyText(`ssh frappe@${activeBench.wg_ip}`)" />
              </div>
            </div>
            <div v-if="activeBench.site_name">
              <label class="text-xs font-medium text-ink-gray-5">Site URL</label>
              <div class="mt-1 flex items-center gap-2">
                <code class="flex-1 rounded bg-surface-gray-2 px-3 py-2 font-mono text-sm text-ink-gray-8">http://{{ activeBench.site_name }}:8000</code>
                <Button icon="copy" appearance="minimal" size="sm" @click="copyText(`http://${activeBench.site_name}:8000`)" />
              </div>
            </div>
            <div v-if="activeBench.admin_password">
              <label class="text-xs font-medium text-ink-gray-5">Admin Password</label>
              <div class="mt-1 flex items-center gap-2">
                <code class="flex-1 rounded bg-surface-gray-2 px-3 py-2 font-mono text-sm text-ink-gray-8">{{ showPassword ? activeBench.admin_password : '••••••••••••' }}</code>
                <Button :icon="showPassword ? 'eye-off' : 'eye'" appearance="minimal" size="sm" @click="showPassword = !showPassword" />
                <Button icon="copy" appearance="minimal" size="sm" @click="copyText(activeBench.admin_password)" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right column -->
      <div class="flex flex-col gap-6">
        <!-- Container Status (shown when bench exists) -->
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

        <!-- Bench Actions (shown when bench exists) -->
        <div v-if="activeBench" class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
          <h2 class="mb-4 text-base font-semibold text-ink-gray-9">Actions</h2>
          <div class="flex flex-wrap gap-2">
            <Button
              v-if="activeBench.status === 'Stopped'"
              appearance="primary"
              icon-left="play"
              :loading="benchAction.loading"
              @click="doBenchAction('start')"
            >Start</Button>
            <Button
              v-if="activeBench.status === 'Running'"
              appearance="subtle"
              icon-left="square"
              :loading="benchAction.loading"
              @click="doBenchAction('stop')"
            >Stop</Button>
            <Button
              v-if="activeBench.status === 'Running'"
              appearance="subtle"
              icon-left="refresh-cw"
              :loading="benchAction.loading"
              @click="doBenchAction('restart')"
            >Restart</Button>
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

  <!-- Loading state -->
  <div v-else class="flex items-center justify-center p-12">
    <div class="text-base text-ink-gray-5">Loading lab details...</div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { createResource, Badge, Button } from 'frappe-ui'

const route = useRoute()
const labId = route.params.labId
const showPassword = ref(false)

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
  benchAction.submit({
    bench_name: activeBench.value.name,
    action,
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
  }
  return map[status] || 'gray'
}
</script>
