<template>
  <div class="p-4">
    <h1 class="mb-4 text-xl font-semibold text-ink-gray-9">Build Logs</h1>

    <div v-if="buildLogs.data?.length" class="space-y-4">
      <div
        v-for="log in buildLogs.data"
        :key="log.name"
        class="rounded-lg border border-outline-gray-1 bg-surface-white"
      >
        <!-- Log header -->
        <div
          class="flex cursor-pointer items-center justify-between px-4 py-3"
          @click="toggleLog(log.name)"
        >
          <div class="flex items-center gap-3">
            <Badge
              :label="log.log_type"
              :theme="log.log_type === 'error' ? 'red' : log.log_type === 'success' ? 'green' : 'gray'"
            />
            <span class="text-sm font-medium text-ink-gray-8">{{ log.lab || log.name }}</span>
          </div>
          <span class="text-xs text-ink-gray-5">{{ log.timestamp }}</span>
        </div>

        <!-- Expanded log viewer -->
        <div v-if="expandedLog === log.name" class="border-t border-outline-gray-1">
          <LogViewer :rawLog="log.message" mode="build" />
        </div>
      </div>
    </div>

    <div v-else-if="buildLogs.loading" class="text-base text-ink-gray-5">Loading...</div>
    <div v-else class="py-12 text-center text-base text-ink-gray-5">No build logs found.</div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { createListResource, Badge } from 'frappe-ui'
import LogViewer from '@/components/LogViewer.vue'

const expandedLog = ref(null)

function toggleLog(name) {
  expandedLog.value = expandedLog.value === name ? null : name
}

let buildLogs = createListResource({
  doctype: 'Build Log',
  fields: ['name', 'lab', 'message', 'log_type', 'timestamp'],
  orderBy: 'timestamp desc',
  start: 0,
  pageLength: 20,
  auto: true,
})
</script>
