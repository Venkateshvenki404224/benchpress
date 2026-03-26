<template>
  <div class="space-y-2 rounded-lg bg-gray-950 p-3">
    <LogStep
      v-for="(step, idx) in steps"
      :key="idx"
      :title="step.title"
      :output="step.output"
      :status="step.status"
      :duration="step.duration"
      :defaultOpen="step.defaultOpen"
    />
    <div v-if="!steps.length" class="py-8 text-center text-sm text-gray-500">
      No log output yet.
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import LogStep from './LogStep.vue'

const props = defineProps({
  /** Raw log text (for build logs — single message field) */
  rawLog: { type: String, default: '' },
  /** Structured log entries (for deploy logs — array of {message, log_type, timestamp}) */
  entries: { type: Array, default: () => [] },
  /** 'build' or 'deploy' */
  mode: { type: String, default: 'build' },
})

const steps = computed(() => {
  if (props.mode === 'build') {
    return parseBuildLog(props.rawLog)
  }
  return parseDeployLog(props.entries)
})

function parseBuildLog(raw) {
  if (!raw) return []

  const lines = raw.split('\n')
  const steps = []
  let current = null

  for (const line of lines) {
    const stepMatch = line.match(/^Step (\d+\/\d+)\s*:\s*(.*)/)
    const headerMatch = line.match(/^===\s*(.*)/)

    if (stepMatch) {
      // New Docker build step
      if (current) steps.push(current)
      current = {
        title: `Step ${stepMatch[1]} : ${stepMatch[2]}`,
        output: '',
        status: 'running',
        defaultOpen: false,
      }
    } else if (headerMatch) {
      const text = headerMatch[1].trim()
      if (current) steps.push(current)

      if (text.toLowerCase().includes('build complete') || text.toLowerCase().includes('build successful')) {
        current = { title: text, output: '', status: 'success', defaultOpen: false }
      } else if (text.toLowerCase().includes('build failed') || text.toLowerCase().includes('error')) {
        current = { title: text, output: '', status: 'error', defaultOpen: true }
      } else {
        current = { title: text, output: '', status: 'running', defaultOpen: false }
      }
    } else if (current) {
      current.output += (current.output ? '\n' : '') + line
    } else {
      // Lines before any step — create an init step
      if (!steps.length || steps[steps.length - 1]?.title !== 'Initialization') {
        current = { title: 'Initialization', output: line, status: 'running', defaultOpen: true }
      } else {
        current = steps.pop()
        current.output += '\n' + line
      }
    }
  }

  if (current) steps.push(current)

  // Mark step statuses
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i]
    if (s.status === 'error') continue
    if (s.output.match(/ERROR|error|FAILED|failed/)) {
      s.status = 'error'
      s.defaultOpen = true
    } else if (i < steps.length - 1) {
      // Completed steps (not the last one)
      if (s.status === 'running') s.status = 'success'
    }
  }

  // Last step: open by default
  if (steps.length) {
    steps[steps.length - 1].defaultOpen = true
  }

  return steps
}

function parseDeployLog(entries) {
  if (!entries?.length) return []

  const phases = []
  let current = null

  for (const entry of entries) {
    const msg = entry.message || ''
    const type = entry.log_type || 'info'

    // Detect phase boundaries (messages ending with "...")
    const isPhaseStart = msg.endsWith('...') || msg.startsWith('Starting') || msg.startsWith('Creating') || msg.startsWith('Configuring')

    if (isPhaseStart) {
      if (current) phases.push(current)
      current = {
        title: msg,
        output: '',
        status: type === 'error' ? 'error' : 'running',
        defaultOpen: type === 'error',
      }
    } else if (current) {
      current.output += (current.output ? '\n' : '') + msg
      if (type === 'success') current.status = 'success'
      if (type === 'error') {
        current.status = 'error'
        current.defaultOpen = true
      }
    } else {
      current = {
        title: msg.slice(0, 80) || 'Deploy',
        output: msg,
        status: type === 'error' ? 'error' : type === 'success' ? 'success' : 'running',
        defaultOpen: type === 'error',
      }
    }
  }

  if (current) phases.push(current)

  // Finalize statuses
  for (let i = 0; i < phases.length - 1; i++) {
    if (phases[i].status === 'running') phases[i].status = 'success'
  }

  if (phases.length) {
    phases[phases.length - 1].defaultOpen = true
  }

  return phases
}
</script>
