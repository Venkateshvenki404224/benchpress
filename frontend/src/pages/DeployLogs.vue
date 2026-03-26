<template>
  <div class="p-4">
    <h1 class="mb-4 text-xl font-semibold text-ink-gray-9">Deploy Logs</h1>

    <!-- Bench selector -->
    <div v-if="benches.data?.length" class="mb-4 flex flex-wrap gap-2">
      <Button
        v-for="bench in benches.data"
        :key="bench.name"
        :appearance="selectedBench === bench.name ? 'primary' : 'subtle'"
        size="sm"
        @click="selectBench(bench.name)"
      >{{ bench.bench_name || bench.name }}</Button>
    </div>

    <!-- Logs for selected bench -->
    <div v-if="selectedBench && deployLogs.data">
      <LogViewer :entries="deployLogs.data" mode="deploy" />
    </div>

    <div v-else-if="!benches.data?.length && !benches.loading" class="py-12 text-center text-base text-ink-gray-5">
      No bench instances found. Deploy a lab first.
    </div>

    <div v-else-if="!selectedBench" class="py-12 text-center text-base text-ink-gray-5">
      Select a bench instance above to view its deploy logs.
    </div>

    <div v-else-if="deployLogs.loading" class="text-base text-ink-gray-5">Loading...</div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { createResource, Button } from 'frappe-ui'
import LogViewer from '@/components/LogViewer.vue'

const selectedBench = ref(null)

const benches = createResource({
  url: 'benchpress.api.get_benches',
  auto: true,
  onSuccess(data) {
    if (data?.length && !selectedBench.value) {
      selectedBench.value = data[0].name
    }
  },
})

const deployLogs = createResource({
  url: 'benchpress.api.get_deploy_logs',
  params: { bench_name: '' },
})

function selectBench(name) {
  selectedBench.value = name
}

watch(selectedBench, (name) => {
  if (name) {
    deployLogs.update({ params: { bench_name: name } })
    deployLogs.reload()
  }
})
</script>
