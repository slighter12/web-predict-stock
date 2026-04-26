<script lang="ts">
    import { onMount } from "svelte";

    import {
        ApiError,
        createKillSwitch,
        createLiveOrder,
        createSimulationOrder,
        fetchKillSwitchEvents,
        fetchLiveOrders,
        fetchSimulationReadbacks,
    } from "../../../api/legacy";
    import type {
        ExecutionOrderRecord,
        KillSwitchRecord,
    } from "../../../../types";

    let simulationForm = {
        market: "TW",
        symbol: "2330",
        side: "buy",
        quantity: 100,
        requested_price: 100,
        simulation_profile_id: "simulation_internal_default_v1",
    };
    let liveForm = {
        market: "TW",
        symbol: "2330",
        side: "buy",
        quantity: 100,
        requested_price: 100,
        live_control_profile_id: "live_stub_default_v1",
        manual_confirmed: false,
    };
    let killSwitchForm = {
        scope_type: "global",
        market: "TW",
        is_enabled: false,
        reason: "",
    };
    let simulationOrders: ExecutionOrderRecord[] = [];
    let liveOrders: ExecutionOrderRecord[] = [];
    let killSwitchEvents: KillSwitchRecord[] = [];
    let errorMessage: string | null = null;

    const refresh = async () => {
        try {
            [simulationOrders, liveOrders, killSwitchEvents] =
                await Promise.all([
                    fetchSimulationReadbacks(),
                    fetchLiveOrders(),
                    fetchKillSwitchEvents(),
                ]);
            errorMessage = null;
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to load execution controls.";
        }
    };

    const submitSimulation = async () => {
        try {
            await createSimulationOrder(simulationForm);
            await refresh();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to create simulation order.";
        }
    };

    const submitLive = async () => {
        try {
            await createLiveOrder(liveForm);
            await refresh();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to create live stub order.";
        }
    };

    const submitKillSwitch = async () => {
        try {
            await createKillSwitch(killSwitchForm);
            await refresh();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to update kill switch.";
        }
    };

    onMount(() => {
        void refresh();
    });
</script>

<div class="surface">
    <div class="surface-header">
        <div>
            <p class="eyebrow">Execution</p>
            <h3>Simulation And Live Controls</h3>
        </div>
        <button type="button" onclick={refresh}>Refresh</button>
    </div>

    <div class="form-grid">
        <label
            ><span>Symbol</span><input
                bind:value={simulationForm.symbol}
            /></label
        >
        <label
            ><span>Simulation Qty</span><input
                type="number"
                min="1"
                bind:value={simulationForm.quantity}
            /></label
        >
        <label
            ><span>Live Qty</span><input
                type="number"
                min="1"
                bind:value={liveForm.quantity}
            /></label
        >
        <label
            ><span>Manual Confirmed</span><input
                type="checkbox"
                bind:checked={liveForm.manual_confirmed}
            /></label
        >
        <label
            ><span>Kill Switch Enabled</span><input
                type="checkbox"
                bind:checked={killSwitchForm.is_enabled}
            /></label
        >
        <label
            ><span>Kill Switch Reason</span><input
                bind:value={killSwitchForm.reason}
            /></label
        >
    </div>

    <div class="button-row">
        <button type="button" onclick={submitSimulation}
            >Submit Simulation</button
        >
        <button type="button" onclick={submitLive}>Submit Live Stub</button>
        <button type="button" onclick={submitKillSwitch}>
            {killSwitchForm.is_enabled ? "Enable" : "Disable"} Kill Switch
        </button>
    </div>
    {#if errorMessage}<p class="muted">{errorMessage}</p>{/if}

    <div class="list">
        <div class="row">
            <strong>Simulation Orders</strong><span
                >{simulationOrders.length}</span
            >
        </div>
        <div class="row">
            <strong>Live Orders</strong><span>{liveOrders.length}</span>
        </div>
        <div class="row">
            <strong>Kill Switch Events</strong><span
                >{killSwitchEvents.length}</span
            >
        </div>
    </div>
</div>

<style lang="scss">
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
