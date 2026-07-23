<script lang="ts">
    import type { OpinionArtifact, OpinionRow } from "../../types";

    export let opinion: OpinionArtifact;

    const formatNumber = (value: number) => value.toFixed(4);
    const stateLabels: Record<OpinionArtifact["state"], string> = {
        viable: "Reviewable model output",
        "no-opinion": "No reviewable model output",
        "do-not-adopt": "Do not use",
    };
    const groups: Array<[string, keyof Pick<OpinionArtifact, "buy_candidates" | "watch" | "sell_or_avoid">]> = [
        ["Positive model candidates", "buy_candidates"],
        ["Watch or conflict", "watch"],
        ["Negative model candidates", "sell_or_avoid"],
    ];
</script>

<section class="surface opinion-surface">
    <div class="surface-header">
        <div>
            <p class="eyebrow">Model Output Review</p>
            <h3>Regression ranking with direction confirmation</h3>
        </div>
        <strong>{stateLabels[opinion.state]}</strong>
    </div>
    <p>{opinion.state_reason}</p>
    <p class="muted">
        As of {opinion.opinion_as_of ?? "N/A"}. Artifact completeness means the
        output is reviewable; it does not establish out-of-sample predictive
        skill or investment viability.
    </p>

    {#if opinion.state === "viable"}
        <div class="opinion-groups">
            {#each groups as [label, key]}
                <div>
                    <h4>{label}</h4>
                    {#if opinion[key].length}
                        <div class="table-wrap">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Symbol</th>
                                        <th>Predicted return</th>
                                        <th>Up probability</th>
                                        <th>Confirmation</th>
                                        <th>Review context</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {#each opinion[key] as row (row.symbol)}
                                        {@const opinionRow = row as OpinionRow}
                                        <tr>
                                            <td>{opinionRow.symbol}</td>
                                            <td>{formatNumber(opinionRow.model_score)}</td>
                                            <td>{formatNumber(opinionRow.up_probability)}</td>
                                            <td>{opinionRow.confirmation_state}</td>
                                            <td class="review-cell">
                                                <details>
                                                    <summary>Evidence &amp; risk</summary>
                                                    <div class="review-context">
                                                        <p><strong>Evidence:</strong> {opinionRow.evidence_reason}</p>
                                                        <p><strong>Risk:</strong> {opinionRow.risk_or_warning}</p>
                                                        <p><strong>Invalidation:</strong> {opinionRow.invalidation_note}</p>
                                                        <ul>
                                                            {#each opinionRow.source_artifact_references as reference}
                                                                <li>
                                                                    {reference.artifact}.{reference.field}
                                                                    {#if reference.symbol} · {reference.symbol}{/if}
                                                                    {#if reference.date} · {reference.date}{/if}
                                                                </li>
                                                            {/each}
                                                        </ul>
                                                    </div>
                                                </details>
                                            </td>
                                        </tr>
                                    {/each}
                                </tbody>
                            </table>
                        </div>
                    {:else}
                        <p class="muted">No symbols in this group.</p>
                    {/if}
                </div>
            {/each}
        </div>
    {:else if opinion.evidence_limitations.length}
        <ul>
            {#each opinion.evidence_limitations as limitation}
                <li>{limitation}</li>
            {/each}
        </ul>
    {/if}
</section>

<style lang="scss">
    .opinion-surface,
    .opinion-groups {
        display: grid;
        gap: var(--space-4);
    }

    .surface {
        padding: 1.1rem;
        border-radius: 22px;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(15, 23, 42, 0.62);
    }

    .surface-header {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: center;
    }

    .eyebrow {
        margin: 0 0 0.3rem;
        color: var(--muted);
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
    }

    h3,
    h4,
    p {
        margin: 0;
    }

    .muted {
        color: var(--muted);
    }

    .table-wrap {
        overflow-x: auto;
    }

    table {
        width: 100%;
        border-collapse: collapse;
    }

    th,
    td {
        text-align: left;
        padding: 0.7rem 0.5rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.12);
        white-space: nowrap;
    }

    .review-cell {
        min-width: 20rem;
        white-space: normal;
    }

    .review-cell summary {
        cursor: pointer;
    }

    .review-context {
        display: grid;
        gap: 0.5rem;
        margin-top: 0.6rem;
    }

    .review-context p,
    .review-context ul {
        margin: 0;
    }
</style>
