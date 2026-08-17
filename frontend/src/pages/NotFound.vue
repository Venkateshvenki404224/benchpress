<template>
	<div class="mx-auto max-w-[1180px] px-6 pb-10 pt-6" data-test="not-found">
		<SectionCard>
			<EmptyState message="That page does not exist. It may have been renamed or removed.">
				<template #action>
					<Button variant="solid" @click="$router.push('/')">Back to Overview</Button>
				</template>
			</EmptyState>
		</SectionCard>
	</div>
</template>

<script setup>
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import { Button } from "frappe-ui";
</script>
