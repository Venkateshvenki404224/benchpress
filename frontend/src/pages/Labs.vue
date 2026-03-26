<template>
  <div class="p-4">
    <div class="mb-4 flex items-center justify-between">
      <h1 class="text-xl font-semibold text-ink-gray-9">Labs</h1>
      <Button appearance="primary" icon-left="plus" @click="$router.push('/labs/new')">
        New Lab
      </Button>
    </div>

    <ListView
      v-if="labs.data?.length"
      :columns="columns"
      :rows="labs.data"
      :options="{
        getRowRoute: (row) => ({ name: 'LabDetail', params: { labId: row.name } }),
        showTooltip: true,
        resizeColumn: true,
        selectable: false,
      }"
      row-key="name"
    />
    <div v-else-if="labs.loading" class="text-base text-ink-gray-5">
      Loading...
    </div>
    <div v-else class="py-12 text-center text-base text-ink-gray-5">
      No labs found. Create your first lab to get started.
    </div>
  </div>
</template>

<script setup>
import { ListView, Button, createListResource } from 'frappe-ui'

const columns = [
  { label: 'Lab ID', key: 'lab_id', width: '180px' },
  { label: 'Title', key: 'title', width: '200px' },
  { label: 'Frappe Version', key: 'frappe_version', width: '150px' },
  { label: 'Status', key: 'status', width: '120px' },
  { label: 'Memory', key: 'memory_limit', width: '100px' },
  { label: 'CPU', key: 'cpu_cores', width: '80px' },
]

let labs = createListResource({
  doctype: 'Lab',
  fields: ['name', 'lab_id', 'title', 'frappe_version', 'status', 'memory_limit', 'cpu_cores'],
  orderBy: 'creation desc',
  start: 0,
  pageLength: 20,
  auto: true,
})
</script>
