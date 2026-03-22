<script lang="ts">
    export let id: string | undefined = undefined;
    export let eyebrow = "";
    export let title = "";
    export let description = "";
</script>

<section class="workspace" {id}>
    <div class="workspace-header">
        <div class="workspace-header__copy">
            <p class="eyebrow">{eyebrow}</p>
            <h2>{title}</h2>
            {#if description}
                <p class="workspace-description">{description}</p>
            {/if}
        </div>
        <div class="workspace-header__actions">
            <slot name="actions" />
        </div>
    </div>
    <div class="workspace-body">
        <slot />
    </div>
</section>

<style lang="scss">
    .workspace {
        padding: 1.45rem;
        border-radius: var(--radius-xl);
        position: relative;
        display: grid;
        gap: 1.15rem;
        overflow: hidden;
    }

    .workspace::before {
        content: "";
        position: absolute;
        inset: 0 auto auto 0;
        width: 100%;
        height: 1px;
        background: linear-gradient(
            90deg,
            rgba(125, 211, 252, 0.58),
            transparent 44%
        );
        opacity: 0.45;
    }

    .workspace-header {
        position: relative;
        z-index: 1;
    }

    .workspace-header__copy {
        display: grid;
        gap: 0.45rem;
        max-width: 62ch;
    }

    .workspace-header__actions {
        display: flex;
        align-items: flex-start;
        justify-content: flex-end;
    }

    .workspace-description {
        margin: 0;
        color: var(--text-secondary);
        font-size: 0.96rem;
    }

    .workspace-body {
        position: relative;
        z-index: 1;
    }

    h2 {
        margin: 0;
        font-size: clamp(1.45rem, 2.8vw, 2.2rem);
        letter-spacing: -0.04em;
        line-height: 1.04;
    }

    @media (max-width: 720px) {
        .workspace {
            padding: 1rem;
            border-radius: var(--radius-lg);
        }
    }
</style>
