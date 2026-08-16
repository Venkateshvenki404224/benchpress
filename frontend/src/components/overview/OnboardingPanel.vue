<template>
	<section
		class="mb-5 rounded-lg border border-outline-gray-1 bg-surface-white px-6 py-5"
		data-test="onboarding-panel"
	>
		<p class="text-2xs font-semibold uppercase tracking-[0.08em] text-ink-gray-4">
			Getting started
		</p>
		<h2 class="mt-2 text-2xl font-semibold tracking-[-0.02em] text-ink-gray-9">
			Create a Frappe environment, press deploy, get a working site and a VS Code window.
		</h2>
		<p class="mt-1.5 max-w-[640px] text-sm text-ink-gray-7">
			A Lab is the recipe — Frappe version, apps, resources. Deploying a Lab builds it into a
			container with its own database, site and browser IDE, reachable over your VPN.
		</p>

		<div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
			<article
				v-for="(step, index) in STEPS"
				:key="step.title"
				class="rounded-md border border-outline-gray-1 bg-surface-gray-1 px-3.5 py-3"
			>
				<div class="mb-1.5 flex items-center gap-2">
					<span
						class="grid size-[18px] flex-none place-items-center rounded-full bg-surface-gray-7 text-[10.5px] font-semibold text-ink-white"
					>
						{{ index + 1 }}
					</span>
					<span class="text-body font-semibold text-ink-gray-9">{{ step.title }}</span>
				</div>
				<p class="text-xs leading-relaxed text-ink-gray-6">{{ step.body }}</p>
			</article>
		</div>

		<div class="mt-4 flex flex-wrap gap-2">
			<Button
				variant="solid"
				data-test="onboarding-template"
				@click="$router.push('/labs/templates')"
			>
				Start from a template
			</Button>
			<Button variant="subtle" data-test="onboarding-vpn" @click="$router.push('/devices')">
				Set up VPN first
			</Button>
		</div>
	</section>
</template>

<script setup>
import { Button } from "frappe-ui";

const STEPS = [
	{
		title: "Pick a lab recipe",
		body: "A template, or your own list of apps, versions and resource limits.",
	},
	{
		title: "Deploy it",
		body: "BenchPress builds the image, creates the container and the site, then wires up SSH and VS Code.",
	},
	{
		title: "Connect over VPN",
		body: "Register your machine on WireGuard — that is what makes the site reachable.",
	},
];
</script>
