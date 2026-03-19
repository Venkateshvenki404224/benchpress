<template>
  <div class="animate-fade-up" v-if="bench">
    <router-link to="/dashboard/benches" class="text-bp-muted hover:text-bp-text text-sm mb-6 inline-flex items-center gap-1">
      ← Back to Benches
    </router-link>

    <!-- Header -->
    <div class="flex items-center justify-between mb-8">
      <div class="flex items-center gap-3">
        <StatusDot :status="bench.status?.toLowerCase() || 'stopped'" />
        <div>
          <h1 class="text-2xl font-bold text-bp-text">{{ bench.bench_name || bench.name }}</h1>
          <div class="flex items-center gap-3 text-sm text-bp-dim mt-1">
            <span class="px-1.5 py-0.5 rounded bg-white/5">{{ bench.frappe_version || 'v15' }}</span>
            <span v-if="bench.lab">Lab: {{ bench.lab }}</span>
          </div>
        </div>
      </div>
      <div class="flex gap-2">
        <button v-if="bench.status === 'Stopped'" @click="benchAction('start')" class="btn-primary">Start</button>
        <button v-if="bench.status === 'Running'" @click="benchAction('restart')" class="btn-secondary">Restart</button>
        <button v-if="bench.status === 'Running'" @click="benchAction('stop')" class="btn-secondary">Stop</button>
      </div>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
      <GlassCard class="!p-4">
        <p class="text-bp-dim text-xs mb-2">CPU Usage</p>
        <StatBar label="" :value="bench.cpu_usage || 0" />
      </GlassCard>
      <GlassCard class="!p-4">
        <p class="text-bp-dim text-xs mb-2">Memory</p>
        <StatBar label="" :value="bench.memory_usage || 0" color="cyan" />
      </GlassCard>
      <GlassCard class="!p-4">
        <p class="text-bp-dim text-xs mb-2">WireGuard IP</p>
        <p class="text-bp-text font-mono text-sm">{{ bench.wg_ip || 'Not configured' }}</p>
      </GlassCard>
      <GlassCard class="!p-4">
        <p class="text-bp-dim text-xs mb-2">Status</p>
        <p class="text-bp-text text-sm font-medium">{{ bench.status }}</p>
      </GlassCard>
    </div>

    <!-- VPN Config -->
    <GlassCard v-if="bench.wg_config" class="mb-6">
      <h3 class="text-bp-text font-medium mb-3">VPN Access</h3>
      <div class="bg-black/30 rounded-lg p-3 font-mono text-xs text-bp-muted mb-3 break-all whitespace-pre-wrap">
        ssh frappe@{{ bench.wg_ip }}
      </div>
      <div class="flex gap-2">
        <button @click="downloadVPN" class="btn-primary text-xs">Download .conf</button>
        <button @click="copyVPN" class="btn-secondary text-xs">Copy Config</button>
      </div>
    </GlassCard>

    <!-- Danger Zone -->
    <GlassCard class="!border-bp-red/20">
      <h3 class="text-bp-red font-medium mb-3">Danger Zone</h3>
      <p class="text-bp-muted text-sm mb-3">Permanently delete this bench and all its data.</p>
      <button @click="deleteBench" class="btn-danger text-xs">Delete Bench</button>
    </GlassCard>
  </div>
  <div v-else class="text-bp-muted text-center py-12">Loading bench...</div>
</template>

<script setup>
import { ref, inject, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import GlassCard from '@/components/GlassCard.vue';
import StatusDot from '@/components/StatusDot.vue';
import StatBar from '@/components/StatBar.vue';

const $call = inject('$call');
const route = useRoute();
const router = useRouter();
const bench = ref(null);

async function fetchBench() {
  try {
    bench.value = await $call('benchpress.api.get_bench', { bench_name: route.params.id });
  } catch (e) {
    console.error('Failed to fetch bench:', e);
  }
}

async function benchAction(action) {
  try {
    await $call('benchpress.api.bench_action', { bench_name: bench.value.name, action });
    await fetchBench();
  } catch (e) {
    console.error(`Action ${action} failed:`, e);
  }
}

function downloadVPN() {
  const blob = new Blob([bench.value.wg_config], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${bench.value.bench_name || bench.value.name}.conf`;
  a.click();
  URL.revokeObjectURL(url);
}

function copyVPN() {
  navigator.clipboard.writeText(bench.value.wg_config);
}

async function deleteBench() {
  if (!confirm('Are you sure? This will permanently delete the bench and all its data.')) return;
  try {
    await $call('benchpress.api.bench_action', { bench_name: bench.value.name, action: 'delete' });
    router.push('/dashboard/benches');
  } catch (e) {
    console.error('Delete failed:', e);
  }
}

onMounted(fetchBench);
</script>
