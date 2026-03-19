<script lang="ts">
    export let eyebrow = "";
    export let title = "";
</script>

<section class="workspace">
    <div class="workspace-header">
        <div>
            <p class="eyebrow">{eyebrow}</p>
            <h2>{title}</h2>
        </div>
        <slot name="actions" />
    </div>
    <slot />
</section>

<style>
    .workspace {
        padding: 1.4rem;
        border-radius: 24px;
        border: 1px solid rgba(148, 163, 184, 0.14);
        background: rgba(15, 23, 42, 0.56);
        display: grid;
        gap: 1rem;
    }

    .workspace-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
    }

    .eyebrow {
        margin: 0 0 0.25rem;
        color: var(--muted);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
    }

    h2 {
        margin: 0;
    }
</style>
