<script lang="ts">
    import { QueryClientProvider } from "@tanstack/svelte-query";
    import type { QueryClient } from "@tanstack/svelte-query";

    import Dashboard from "./lib/components/Dashboard.svelte";

    export let queryClient: QueryClient;
</script>

<svelte:head>
    <title>Research Workbench V2</title>
    <meta
        name="description"
        content="Research-first workflow for baseline runs, capability expansion, and operational repair."
    />
</svelte:head>

<QueryClientProvider client={queryClient}>
    <main class="app-shell">
        <Dashboard />
    </main>
</QueryClientProvider>

<style lang="scss">
    .app-shell {
        position: relative;
        z-index: 1;
        width: min(calc(100% - 2rem), var(--max-shell));
        margin: 0 auto;
        padding: 1.6rem 0 3rem;
    }

    @media (max-width: 720px) {
        .app-shell {
            width: min(calc(100% - 1.4rem), var(--max-shell));
            padding-top: 1rem;
        }
    }
</style>
