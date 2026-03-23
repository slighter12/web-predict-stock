<script lang="ts">
    import { QueryClientProvider } from "@tanstack/svelte-query";
    import type { QueryClient } from "@tanstack/svelte-query";

    import Dashboard from "./lib/components/Dashboard.svelte";

    export let queryClient: QueryClient;
</script>

<svelte:head>
    <title>Prediction Studio</title>
    <meta
        name="description"
        content="Visual prediction workflows with maintenance tools for replay and repair."
    />
</svelte:head>

<QueryClientProvider client={queryClient}>
    <main class="app-shell">
        <section class="hero">
            <div class="hero__copy">
                <p class="hero__eyebrow">Prediction Workflow Platform</p>
                <h1>
                    Build the prediction flow first. Repair data only when it
                    needs intervention.
                </h1>
                <p class="hero__summary">
                    Prediction Studio turns feature selection, model choice,
                    validation, and result review into one continuous workflow.
                    Maintenance keeps replay and repair tools available without
                    becoming the main entry point.
                </p>
            </div>

            <div class="hero__meta">
                <div class="hero-card">
                    <span class="hero-card__label">Primary Flow</span>
                    <strong>Prediction Studio</strong>
                    <p>
                        Data, feature, model, validation, and results on one
                        surface.
                    </p>
                </div>
                <div class="hero-card hero-card--muted">
                    <span class="hero-card__label">Secondary Flow</span>
                    <strong>Maintenance</strong>
                    <p>
                        Replay, repair, event correction, and execution
                        diagnostics.
                    </p>
                </div>
            </div>
        </section>

        <Dashboard />
    </main>
</QueryClientProvider>

<style lang="scss">
    .app-shell {
        position: relative;
        z-index: 1;
        width: min(calc(100% - 2.5rem), var(--max-shell));
        margin: 0 auto;
        padding: 2rem 0 3.5rem;
        display: grid;
        gap: 1.6rem;
    }

    .hero {
        position: relative;
        display: grid;
        grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.95fr);
        gap: 1.2rem;
        padding: 1.45rem;
        border-radius: var(--radius-xl);
        border: 1px solid rgba(125, 211, 252, 0.16);
        background:
            linear-gradient(
                135deg,
                rgba(10, 25, 40, 0.92),
                rgba(4, 12, 22, 0.88)
            ),
            var(--surface-raised);
        box-shadow: var(--shadow-panel);
        overflow: hidden;
    }

    .hero::after {
        content: "";
        position: absolute;
        inset: auto -20% -45% 35%;
        height: 60%;
        border-radius: 999px;
        background: radial-gradient(
            circle,
            rgba(245, 158, 11, 0.18),
            transparent 70%
        );
        filter: blur(30px);
        pointer-events: none;
    }

    .hero__copy,
    .hero__meta {
        position: relative;
        z-index: 1;
    }

    .hero__copy {
        display: grid;
        gap: 0.85rem;
        align-content: start;
        min-width: 0;
    }

    .hero__eyebrow {
        margin: 0;
        color: var(--accent-primary);
        font-size: 0.74rem;
        font-weight: 600;
        letter-spacing: 0.2em;
        text-transform: uppercase;
    }

    h1 {
        margin: 0;
        max-width: 14ch;
        font-size: clamp(2.7rem, 5vw, 5.2rem);
        line-height: 0.92;
        letter-spacing: -0.05em;
    }

    .hero__summary {
        margin: 0;
        max-width: 62ch;
        color: var(--text-secondary);
        font-size: 1rem;
    }

    .hero__meta {
        display: grid;
        gap: 1rem;
        align-content: stretch;
    }

    .hero-card {
        display: grid;
        gap: 0.55rem;
        align-content: start;
        padding: 1.1rem 1.15rem;
        min-height: 9rem;
        border-radius: var(--radius-lg);
        border: 1px solid rgba(125, 211, 252, 0.12);
        background: linear-gradient(
            180deg,
            rgba(12, 28, 44, 0.96),
            rgba(5, 13, 22, 0.88)
        );
    }

    .hero-card--muted {
        border-color: rgba(148, 163, 184, 0.16);
        background: linear-gradient(
            180deg,
            rgba(12, 18, 30, 0.96),
            rgba(5, 13, 22, 0.88)
        );
    }

    .hero-card__label {
        color: var(--muted);
        font-size: 0.72rem;
        letter-spacing: 0.16em;
        text-transform: uppercase;
    }

    .hero-card strong {
        font-size: 1.1rem;
        line-height: 1.2;
    }

    .hero-card p {
        margin: 0;
        color: var(--text-secondary);
    }

    @media (max-width: 980px) {
        .hero {
            grid-template-columns: 1fr;
        }

        h1 {
            max-width: none;
        }
    }

    @media (max-width: 720px) {
        .app-shell {
            width: min(calc(100% - 1.4rem), var(--max-shell));
            padding-top: 1rem;
        }

        .hero {
            padding: 1.1rem;
            border-radius: var(--radius-lg);
        }

        h1 {
            font-size: clamp(2.4rem, 14vw, 3.4rem);
        }
    }
</style>
