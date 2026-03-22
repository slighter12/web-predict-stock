<script lang="ts">
    export let label: string;
    export let value: string;
    export let tone: "neutral" | "positive" | "negative" = "neutral";
</script>

<article
    class="metric-card"
    class:tone-positive={tone === "positive"}
    class:tone-negative={tone === "negative"}
>
    <p>{label}</p>
    <strong>{value}</strong>
</article>

<style lang="scss">
    .metric-card {
        position: relative;
        padding: 1rem;
        min-height: 128px;
        border-radius: var(--radius-md);
        overflow: hidden;
    }

    .metric-card::after {
        content: "";
        position: absolute;
        inset: auto 1rem 1rem auto;
        width: 3.25rem;
        height: 3.25rem;
        border-radius: 50%;
        background: radial-gradient(
            circle,
            rgba(56, 189, 248, 0.16),
            transparent 72%
        );
        pointer-events: none;
    }

    p {
        margin: 0 0 0.65rem;
        color: var(--muted);
        font-size: 0.76rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.12em;
    }

    strong {
        font-size: clamp(1.55rem, 2vw, 2.2rem);
        line-height: 1.1;
    }

    .tone-positive strong {
        color: var(--accent-positive);
    }

    .tone-negative strong {
        color: var(--accent-negative);
    }
</style>
