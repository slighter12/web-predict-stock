<script lang="ts">
    import { onMount } from "svelte";

    import {
        ApiError,
        createRecoveryDrill,
        createRecoveryDrillSchedule,
        fetchRecoveryDrills,
        fetchRecoveryDrillSchedules,
    } from "../../api";
    import type {
        RecoveryDrillRecord,
        RecoveryDrillScheduleRecord,
    } from "../../types";
    import {
        createDefaultRecoveryDrillScheduleForm,
        toOptionalNumber,
    } from "../../state/dataPlaneForms";

    let form = {
        rawPayloadId: "",
        benchmarkProfileId: "local_manual_v1",
        notes: "",
    };
    let scheduleForm = createDefaultRecoveryDrillScheduleForm();
    let records: RecoveryDrillRecord[] = [];
    let schedules: RecoveryDrillScheduleRecord[] = [];
    let latestRecord: RecoveryDrillRecord | null = null;
    let latestSchedule: RecoveryDrillScheduleRecord | null = null;
    let drillError: string | null = null;
    let scheduleError: string | null = null;

    const refresh = async () => {
        try {
            records = await fetchRecoveryDrills();
            schedules = await fetchRecoveryDrillSchedules();
            drillError = null;
            scheduleError = null;
        } catch (error) {
            const msg =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to load recovery drill data.";
            drillError = msg;
            scheduleError = msg;
        }
    };

    const submit = async () => {
        const rawPayloadInput = form.rawPayloadId.trim();
        const rawPayloadId = toOptionalNumber(rawPayloadInput);
        if (
            rawPayloadInput &&
            (!Number.isInteger(rawPayloadId) || rawPayloadId < 1)
        ) {
            latestRecord = null;
            drillError =
                "Raw Payload ID must be a positive integer when provided.";
            return;
        }

        try {
            latestRecord = await createRecoveryDrill({
                raw_payload_id: rawPayloadId,
                benchmark_profile_id:
                    form.benchmarkProfileId.trim() || undefined,
                notes: form.notes.trim() || undefined,
            });
            drillError = null;
            await refresh();
        } catch (error) {
            drillError =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to create recovery drill.";
        }
    };

    const submitSchedule = async () => {
        if (
            !Number.isInteger(scheduleForm.day_of_month) ||
            scheduleForm.day_of_month < 1 ||
            scheduleForm.day_of_month > 31
        ) {
            latestSchedule = null;
            scheduleError = "Schedule day must be an integer between 1 and 31.";
            return;
        }

        try {
            latestSchedule = await createRecoveryDrillSchedule({
                market: scheduleForm.market,
                symbol: scheduleForm.symbol?.trim() || undefined,
                cadence: "monthly",
                day_of_month: scheduleForm.day_of_month,
                timezone: scheduleForm.timezone?.trim() || "Asia/Taipei",
                benchmark_profile_id: scheduleForm.benchmark_profile_id.trim(),
                notes: scheduleForm.notes?.trim() || undefined,
            });
            scheduleError = null;
            await refresh();
        } catch (error) {
            latestSchedule = null;
            scheduleError =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to create recovery drill schedule.";
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
            <h3>Recovery Drills</h3>
        </div>
        <button type="button" onclick={refresh}>Refresh</button>
    </div>

    <div class="form-grid">
        <label
            ><span>Raw Payload ID</span><input
                bind:value={form.rawPayloadId}
                placeholder="latest successful if blank"
            /></label
        >
        <label
            ><span>Benchmark Profile</span><input
                bind:value={form.benchmarkProfileId}
            /></label
        >
        <label class="wide"
            ><span>Notes</span><input bind:value={form.notes} /></label
        >
    </div>

    <button type="button" onclick={submit}>Create Recovery Drill</button>
    {#if drillError}<p class="muted">{drillError}</p>{/if}
    {#if latestRecord}<pre>{JSON.stringify(latestRecord, null, 2)}</pre>{/if}

    {#if records.length}
        <div class="list">
            {#each records as record}
                <div class="row">
                    <strong>#{record.id}</strong>
                    <span>
                        {record.trigger_mode} / {record.status} / raw_payload_id={record.raw_payload_id ??
                            "none"} / slot={record.scheduled_for_date ??
                            "manual"} / delta={record.completed_trading_day_delta ??
                            "n/a"}
                    </span>
                </div>
            {/each}
        </div>
    {/if}

    <div class="schedule-block">
        <div class="surface-header">
            <div>
                <p class="eyebrow">Scheduled Recovery</p>
                <h4>Monthly Schedules</h4>
            </div>
        </div>

        <div class="form-grid">
            <label
                ><span>Market</span><select bind:value={scheduleForm.market}>
                    <option value="TW">TW</option>
                    <option value="US">US</option>
                </select></label
            >
            <label
                ><span>Symbol</span><input
                    bind:value={scheduleForm.symbol}
                    placeholder="blank = market latest"
                /></label
            >
            <label
                ><span>Day of Month</span><input
                    type="number"
                    bind:value={scheduleForm.day_of_month}
                    min="1"
                    max="31"
                /></label
            >
            <label
                ><span>Timezone</span><input
                    bind:value={scheduleForm.timezone}
                /></label
            >
            <label
                ><span>Benchmark Profile</span><input
                    bind:value={scheduleForm.benchmark_profile_id}
                /></label
            >
            <label class="wide"
                ><span>Notes</span><input
                    bind:value={scheduleForm.notes}
                /></label
            >
        </div>

        <button type="button" onclick={submitSchedule}
            >Create Monthly Schedule</button
        >
        {#if scheduleError}<p class="muted">{scheduleError}</p>{/if}
        {#if latestSchedule}<pre>{JSON.stringify(
                    latestSchedule,
                    null,
                    2,
                )}</pre>{/if}

        {#if schedules.length}
            <div class="list">
                {#each schedules.filter((schedule) => schedule.is_active) as schedule}
                    <div class="row">
                        <strong>#{schedule.id}</strong>
                        <span>
                            {schedule.market}:{schedule.symbol ?? "*"} / day {schedule.day_of_month}
                            / {schedule.timezone} / {schedule.benchmark_profile_id}
                        </span>
                    </div>
                {/each}
            </div>
        {/if}
    </div>
</div>

<style lang="scss">
    .surface,
    .form-grid,
    .list,
    .schedule-block {
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
    .row {
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
    h4 {
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
    select,
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
    pre {
        margin: 0;
        padding: 0.9rem;
        border-radius: 14px;
        background: rgba(15, 23, 42, 0.72);
        white-space: pre-wrap;
        word-break: break-word;
        font-family: var(--mono);
        font-size: 0.78rem;
    }
    @media (max-width: 720px) {
        .form-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
