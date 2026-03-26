<template>
  <div class="flex h-screen">
    <Sidebar
      :header="sidebarConfig.header"
      :sections="sidebarConfig.sections"
    />
    <div class="flex-1 overflow-auto bg-surface-white">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { Sidebar } from 'frappe-ui'
import { reactive } from 'vue'
import { session } from '@/data/session'

import ServerIcon from '~icons/lucide/server'
import GlobeIcon from '~icons/lucide/globe'
import FlaskConicalIcon from '~icons/lucide/flask-conical'
import ScrollTextIcon from '~icons/lucide/scroll-text'
import HammerIcon from '~icons/lucide/hammer'
import SettingsIcon from '~icons/lucide/settings'
import LayoutDashboardIcon from '~icons/lucide/layout-dashboard'
import MoonIcon from '~icons/lucide/moon'
import LogOutIcon from '~icons/lucide/log-out'

function switchToDesk() {
  window.location.href = '/app'
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme')
  document.documentElement.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark')
}

function logout() {
  session.logout.submit()
}

const sidebarConfig = reactive({
  header: {
    title: 'Benchpress',
    subtitle: session.user || '',
    menuItems: [
      { label: 'Switch to Desk', icon: LayoutDashboardIcon, onClick: switchToDesk },
      { label: 'Toggle Theme', icon: MoonIcon, onClick: toggleTheme },
      { label: 'Logout', icon: LogOutIcon, onClick: logout },
    ],
  },
  sections: [
    {
      label: '',
      items: [
        { label: 'Bench Instances', icon: ServerIcon, to: '/bench-instances' },
        { label: 'Bench Sites', icon: GlobeIcon, to: '/bench-sites' },
        { label: 'Labs', icon: FlaskConicalIcon, to: '/labs' },
      ],
    },
    {
      label: 'Logs',
      collapsible: true,
      items: [
        { label: 'Deploy Logs', icon: ScrollTextIcon, to: '/deploy-logs' },
        { label: 'Build Logs', icon: HammerIcon, to: '/build-logs' },
      ],
    },
    {
      label: '',
      items: [
        { label: 'Settings', icon: SettingsIcon, to: '/settings' },
      ],
    },
  ],
})
</script>
