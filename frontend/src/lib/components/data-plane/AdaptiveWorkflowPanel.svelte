<script lang="ts">
    import { onMount } from "svelte";

    import {
        ApiError,
        createAdaptiveProfile,
        createAdaptiveTrainingRun,
        fetchAdaptiveProfiles,
        fetchAdaptiveTrainingRuns,
    } from "../../api";
    import type {
        AdaptiveProfileRecord,
        AdaptiveTrainingRunRecord,
    } from "../../types";

    let profileForm = {
        id: "adaptive_shadow_v1",
        market: "TW",
        reward_definition_version: "reward_daily_active_return_v1",
        state_definition_version: "state_market_context_v1",
        rollout_control_version: "rollout_shadow_only_v1",
        notes: "",
        rollout_detail: { max_exposure: 0.2 },
    };
    let trainingForm = {
        adaptive_profile_id: "adaptive_shadow_v1",
        market: "TW",
        adaptive_mode: "shadow",
        reward_definition_version: "reward_daily_active_return_v1",
        state_definition_version: "state_market_context_v1",
        rollout_control_version: "rollout_shadow_only_v1",
    };
    let profiles: AdaptiveProfileRecord[] = [];
    let trainingRuns: AdaptiveTrainingRunRecord[] = [];
    let errorMessage: string | null = null;

    const refresh = async () => {
        try {
            [profiles, trainingRuns] = await Promise.all([
                fetchAdaptiveProfiles(),
                fetchAdaptiveTrainingRuns(),
            ]);
            errorMessage = null;
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to load adaptive workflow records.";
        }
    };

    const submitProfile = async () => {
        try {
            await createAdaptiveProfile(profileForm);
            trainingForm.adaptive_profile_id = profileForm.id;
            trainingForm.reward_definition_version =
                profileForm.reward_definition_version;
            trainingForm.state_definition_version =
                profileForm.state_definition_version;
            trainingForm.rollout_control_version =
                profileForm.rollout_control_version;
            await refresh();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to create adaptive profile.";
        }
    };

    const submitTraining = async () => {
        try {
            await createAdaptiveTrainingRun(trainingForm);
            await refresh();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to create adaptive training run.";
        }
    };

    onMount(() => {
        void refresh();
    });
</script>

<div class="surface">
    <div class="surface-header">
        <div>
            <p class="eyebrow">Research</p>
            <h3>Adaptive Workflow</h3>
        </div>
        <button type="button" onclick={refresh}>Refresh</button>
    </div>

    <div class="form-grid">
        <label
            ><span>Profile ID</span><input bind:value={profileForm.id} /></label
        >
        <label
            ><span>Adaptive Mode</span><select
                bind:value={trainingForm.adaptive_mode}
            >
                <option value="shadow">shadow</option>
                <option value="candidate">candidate</option>
            </select></label
        >
        <label
            ><span>Reward Version</span><input
                bind:value={profileForm.reward_definition_version}
            /></label
        >
        <label
            ><span>State Version</span><input
                bind:value={profileForm.state_definition_version}
            /></label
        >
        <label class="wide"
            ><span>Rollout Control</span><input
                bind:value={profileForm.rollout_control_version}
            /></label
        >
    </div>

    <div class="button-row">
        <button type="button" onclick={submitProfile}>Create Profile</button>
        <button type="button" onclick={submitTraining}
            >Create Training Run</button
        >
    </div>
    {#if errorMessage}<p class="muted">{errorMessage}</p>{/if}

    <div class="list">
        <div class="row">
            <strong>Profiles</strong><span>{profiles.length}</span>
        </div>
        <div class="row">
            <strong>Training Runs</strong><span>{trainingRuns.length}</span>
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
</style>
