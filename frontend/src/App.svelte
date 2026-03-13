<script lang="ts">
  import { QueryClientProvider } from "@tanstack/svelte-query";
  import type { QueryClient } from "@tanstack/svelte-query";

  import Dashboard from "./lib/components/Dashboard.svelte";

  export let queryClient: QueryClient;
</script>

<svelte:head>
  <title>Quant Research Dashboard</title>
  <meta
    name="description"
    content="Single-screen research dashboard for configuring and reviewing quantitative backtests."
  />
</svelte:head>

<QueryClientProvider client={queryClient}>
  <main>
    <header>
      <p>Personal Quantitative Research Platform</p>
      <h1>Signal Lab</h1>
    </header>
    <Dashboard />
  </main>
</QueryClientProvider>

<style>
  main {
    max-width: 1480px;
    margin: 0 auto;
    padding: 2rem 1.25rem 3rem;
  }

  header {
    margin-bottom: 1.2rem;
  }

  p {
    margin: 0 0 0.35rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.18em;
    font-size: 0.76rem;
  }

  h1 {
    margin: 0;
    font-size: clamp(2.2rem, 5vw, 4.6rem);
    line-height: 0.95;
  }
</style>
