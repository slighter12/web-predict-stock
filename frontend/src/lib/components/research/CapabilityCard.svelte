<script lang="ts">
    import type {
        CapabilityReadinessState,
        ResearchCapabilityDefinition,
    } from "../../types";

    export let capability: ResearchCapabilityDefinition;
    export let readiness: CapabilityReadinessState;
    export let isEnabled = false;
    export let isToggleDisabled = false;
    export let titleSuffix = "";

    const statusLabels = {
        available: "Available",
        setup_required: "Setup Required",
        gated: "Gated",
        not_implemented: "Not Implemented",
    } as const;

    const toneClass = (status: CapabilityReadinessState["status"]) =>
        status === "available"
            ? "capability-card__status--available"
            : status === "setup_required"
              ? "capability-card__status--setup"
              : "capability-card__status--gated";
</script>

<article
    class:capability-card={true}
    class:capability-card--enabled={isEnabled}
>
    <div class="capability-card__header">
        <div>
            <p class="eyebrow">{capability.stage.replace(/_/g, " ")}</p>
            <h4>{capability.label}{titleSuffix}</h4>
        </div>
        <span class={`capability-card__status ${toneClass(readiness.status)}`}>
            {statusLabels[readiness.status]}
        </span>
    </div>

    <p class="capability-card__summary">{capability.summary}</p>
    <p class="capability-card__detail">{readiness.summary}</p>

    <div class="capability-card__footer">
        <label class="toggle">
            <input
                type="checkbox"
                checked={isEnabled}
                disabled={isToggleDisabled}
                on:change
            />
            <span
                >{isEnabled
                    ? "Included in this workflow"
                    : "Enable capability"}</span
            >
        </label>
        {#if capability.gateRefs.length}
            <span class="capability-card__gate">
                {capability.gateRefs.join(" / ")}
            </span>
        {/if}
    </div>

    <slot />
</article>

<style lang="scss">
    .capability-card {
        display: grid;
        gap: 0.8rem;
        padding: 1rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(7, 20, 34, 0.88);
    }

    .capability-card--enabled {
        border-color: rgba(56, 189, 248, 0.32);
        background: linear-gradient(
            180deg,
            rgba(10, 33, 52, 0.94),
            rgba(7, 20, 34, 0.9)
        );
    }

    .capability-card__header,
    .capability-card__footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.8rem;
    }

    h4,
    p {
        margin: 0;
    }

    .capability-card__summary {
        color: var(--text);
    }

    .capability-card__detail,
    .capability-card__gate {
        color: var(--muted);
        font-size: 0.88rem;
    }

    .capability-card__status {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 2rem;
        padding: 0.25rem 0.7rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .capability-card__status--available {
        background: rgba(16, 185, 129, 0.14);
        color: #86efac;
    }

    .capability-card__status--setup {
        background: rgba(251, 191, 36, 0.12);
        color: #fcd34d;
    }

    .capability-card__status--gated {
        background: rgba(248, 113, 113, 0.12);
        color: #fda4af;
    }

    @media (max-width: 720px) {
        .capability-card__header,
        .capability-card__footer {
            align-items: flex-start;
            flex-direction: column;
        }
    }
</style>
