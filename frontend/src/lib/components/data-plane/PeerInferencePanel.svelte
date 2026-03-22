<script lang="ts">
    import { onMount } from "svelte";

    import {
        ApiError,
        createClusterSnapshot,
        createPeerFeatureRun,
        fetchClusterSnapshots,
        fetchPeerFeatureRuns,
    } from "../../api";
    import type {
        ClusterSnapshotRecord,
        PeerFeatureRunRecord,
    } from "../../types";

    let snapshotForm = {
        market: "TW",
        trading_date: "2024-12-31",
        snapshot_version: "peer_cluster_kmeans_v1",
        cluster_count: 3,
    };
    let peerForm = {
        snapshot_id: 0,
        peer_policy_version: "cluster_nearest_neighbors_v1",
        symbol_limit: 5,
    };
    let snapshots: ClusterSnapshotRecord[] = [];
    let peerRuns: PeerFeatureRunRecord[] = [];
    let errorMessage: string | null = null;

    const refresh = async () => {
        try {
            [snapshots, peerRuns] = await Promise.all([
                fetchClusterSnapshots(),
                fetchPeerFeatureRuns(),
            ]);
            if (!peerForm.snapshot_id && snapshots[0]) {
                peerForm.snapshot_id = snapshots[0].id;
            }
            errorMessage = null;
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to load peer inference data.";
        }
    };

    const submitSnapshot = async () => {
        try {
            const created = await createClusterSnapshot(snapshotForm);
            peerForm.snapshot_id = created.id;
            await refresh();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to create cluster snapshot.";
        }
    };

    const submitPeerRun = async () => {
        try {
            await createPeerFeatureRun(peerForm);
            await refresh();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to create peer feature run.";
        }
    };

    onMount(() => {
        void refresh();
    });
</script>

<div class="surface">
    <div class="surface-header">
        <div>
            <p class="eyebrow">Data Plane</p>
            <h3>Clustering And Peer Inference</h3>
        </div>
        <button type="button" onclick={refresh}>Refresh</button>
    </div>

    <div class="form-grid">
        <label
            ><span>Trading Date</span><input
                type="date"
                bind:value={snapshotForm.trading_date}
            /></label
        >
        <label
            ><span>Cluster Count</span><input
                type="number"
                min="1"
                bind:value={snapshotForm.cluster_count}
            /></label
        >
        <label class="wide"
            ><span>Snapshot ID</span><input
                type="number"
                min="0"
                bind:value={peerForm.snapshot_id}
            /></label
        >
    </div>

    <div class="button-row">
        <button type="button" onclick={submitSnapshot}>Create Snapshot</button>
        <button
            type="button"
            onclick={submitPeerRun}
            disabled={!peerForm.snapshot_id}>Create Peer Run</button
        >
    </div>
    {#if errorMessage}<p class="muted">{errorMessage}</p>{/if}

    <div class="list">
        <div class="row">
            <strong>Snapshots</strong><span>{snapshots.length}</span>
        </div>
        <div class="row">
            <strong>Peer Runs</strong><span>{peerRuns.length}</span>
        </div>
    </div>
</div>

<style>
    .surface,
    .form-grid,
    .list {
        display: grid;
        gap: 0.9rem;
    }
    .surface {
        padding: 1.1rem;
        border-radius: 22px;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(15, 23, 42, 0.62);
    }
    .surface-header,
    .row,
    .button-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
    }
    .eyebrow {
        margin: 0 0 0.3rem;
        color: var(--muted);
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
    }
    h3 {
        margin: 0;
    }
    .form-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .wide {
        grid-column: 1 / -1;
    }
    label {
        display: grid;
        gap: 0.35rem;
    }
    span,
    .muted {
        color: var(--muted);
    }
    input,
    button {
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 14px;
        padding: 0.8rem 0.9rem;
        background: rgba(2, 6, 23, 0.72);
        color: var(--text);
    }
    .row {
        padding: 0.75rem 0.9rem;
        border-radius: 14px;
        background: rgba(15, 23, 42, 0.72);
    }
</style>
