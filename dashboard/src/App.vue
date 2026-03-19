<template>
  <div class="min-h-screen bg-bp-bg">
    <nav class="glass-nav" v-if="$auth.isLoggedIn">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-14">
        <div class="flex items-center gap-6">
          <router-link to="/" class="text-lg font-bold gradient-text">BenchPress</router-link>
          <div class="flex gap-1">
            <router-link to="/" class="nav-link" :class="{ 'nav-link-active': $route.path === '/' }">Labs</router-link>
            <router-link to="/benches" class="nav-link" :class="{ 'nav-link-active': $route.path === '/benches' }">Benches</router-link>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <span class="text-bp-muted text-sm">{{ $auth.user }}</span>
          <button @click="$auth.logout()" class="text-bp-dim hover:text-bp-text text-sm transition-colors">Logout</button>
        </div>
      </div>
    </nav>
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <router-view />
    </main>
  </div>
</template>

<script>
export default {
  inject: ['$auth'],
};
</script>

<style>
.nav-link {
  @apply px-3 py-1.5 rounded-md text-sm text-bp-muted hover:text-bp-text hover:bg-white/5 transition-all;
}
.nav-link-active {
  @apply text-bp-text bg-white/5;
}
</style>
