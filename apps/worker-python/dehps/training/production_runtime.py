from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from dehps.training.models import TrainingRoundRequest
from dehps.training.runtime import *  # noqa: F403
from dehps.training.runtime_advisors import (
    RuntimeAdvisorOrchestrator,
    RuntimeAdvisorSettings,
)
from dehps.training.runtime_round_executor import (
    RuntimeRoundOutcome,
    RuntimeRoundRequest,
    RuntimeTrainingState,
)
from dehps.training.round_observability import RoundStageTracker
from dehps.training.persistence_policy import (
    apply_observability_only_database_guard,
    training_persistence_policy,
)


@dataclass(frozen=True)
class ProductionRuntimeRoundExecutor:
    """Run the established production round body exactly once."""

    def execute(
        self,
        request: RuntimeRoundRequest,
        state: RuntimeTrainingState,
    ) -> RuntimeRoundOutcome:
        as_of_issue_value = state.values["as_of_issue_value"]
        best_config = state.values["best_config"]
        best_summary = state.values["best_summary"]
        conn = state.values["conn"]
        deadline = state.values["deadline"]
        dynamic_kdj_best_policy = state.values["dynamic_kdj_best_policy"]
        dynamic_kdj_best_training_summary = state.values["dynamic_kdj_best_training_summary"]
        enable_neural_kdj_advisor = state.values["enable_neural_kdj_advisor"]
        enable_ridge_kdj_advisor = state.values["enable_ridge_kdj_advisor"]
        enable_target_weight_inversion_advisor = state.values["enable_target_weight_inversion_advisor"]
        enable_weight_kdj_advisor = state.values["enable_weight_kdj_advisor"]
        eval_window = state.values["eval_window"]
        guard_continuity_info = state.values["guard_continuity_info"]
        guard_history = state.values["guard_history"]
        leaderboard = state.values["leaderboard"]
        max_configs_per_round = state.values["max_configs_per_round"]
        max_rounds = state.values["max_rounds"]
        observability_only = state.values["observability_only"]
        navigation_records = state.values["navigation_records"]
        near_dynamic_kdj_best_policy = state.values["near_dynamic_kdj_best_policy"]
        near_dynamic_kdj_best_training_summary = state.values["near_dynamic_kdj_best_training_summary"]
        near_dynamic_kdj_latest_policy = state.values["near_dynamic_kdj_latest_policy"]
        near_dynamic_kdj_seal_reason = state.values["near_dynamic_kdj_seal_reason"]
        near_dynamic_kdj_sealed = state.values["near_dynamic_kdj_sealed"]
        near_dynamic_kdj_stagnation_rounds = state.values["near_dynamic_kdj_stagnation_rounds"]
        near_miss_inversion_configs = state.values["near_miss_inversion_configs"]
        near_miss_inversion_latest = state.values["near_miss_inversion_latest"]
        neural_kdj_budget_share = state.values["neural_kdj_budget_share"]
        neural_kdj_epochs = state.values["neural_kdj_epochs"]
        neural_kdj_hidden_units = state.values["neural_kdj_hidden_units"]
        neural_kdj_min_confidence = state.values["neural_kdj_min_confidence"]
        neural_kdj_params = state.values["neural_kdj_params"]
        neural_kdj_seed = state.values["neural_kdj_seed"]
        neural_kdj_thresholds = state.values["neural_kdj_thresholds"]
        pool = state.values["pool"]
        prior_leaderboard = state.values["prior_leaderboard"]
        probability_focus_config = state.values["probability_focus_config"]
        probability_focus_hash = state.values["probability_focus_hash"]
        probability_focus_remaining = state.values["probability_focus_remaining"]
        probability_focus_score = state.values["probability_focus_score"]
        probability_focus_source = state.values["probability_focus_source"]
        progress_interval = state.values["progress_interval"]
        publish_progress = state.values["publish_progress"]
        round_stage_tracker = state.values["round_stage_tracker"]
        ranked_universe = state.values["ranked_universe"]
        report_path = state.values["report_path"]
        resolved_event_url = state.values["resolved_event_url"]
        ridge_kdj_alpha = state.values["ridge_kdj_alpha"]
        ridge_kdj_budget_share = state.values["ridge_kdj_budget_share"]
        ridge_kdj_min_confidence = state.values["ridge_kdj_min_confidence"]
        ridge_kdj_min_train_rows = state.values["ridge_kdj_min_train_rows"]
        ridge_kdj_min_validation_rows = state.values["ridge_kdj_min_validation_rows"]
        ridge_kdj_params = state.values["ridge_kdj_params"]
        ridge_kdj_thresholds = state.values["ridge_kdj_thresholds"]
        round_index = state.values["round_index"]
        rounds = state.values["rounds"]
        run_id = state.values["run_id"]
        search_base_config = state.values["search_base_config"]
        sequential_null_ledger = state.values["sequential_null_ledger"]
        status = state.values["status"]
        status_path = state.values["status_path"]
        strategy_memory_prior_diagnostics = state.values["strategy_memory_prior_diagnostics"]
        target_weight_inversion_budget_share = state.values["target_weight_inversion_budget_share"]
        target_weight_inversion_configs = state.values["target_weight_inversion_configs"]
        target_weight_inversion_latest = state.values["target_weight_inversion_latest"]
        target_weight_inversion_max_candidates = state.values["target_weight_inversion_max_candidates"]
        target_weight_inversion_max_deltas_per_target = state.values["target_weight_inversion_max_deltas_per_target"]
        target_weight_inversion_max_targets = state.values["target_weight_inversion_max_targets"]
        top_n = state.values["top_n"]
        train_mode = state.values["train_mode"]
        train_window = state.values["train_window"]
        training_history = state.values["training_history"]
        weight_kdj_budget_share = state.values["weight_kdj_budget_share"]
        weight_kdj_limit = state.values["weight_kdj_limit"]
        weight_kdj_min_abs_offset = state.values["weight_kdj_min_abs_offset"]
        weight_kdj_min_objective_delta = state.values["weight_kdj_min_objective_delta"]
        weight_kdj_neutral_band = state.values["weight_kdj_neutral_band"]
        weight_kdj_run_id = state.values["weight_kdj_run_id"]
        weight_kdj_slope_window = state.values["weight_kdj_slope_window"]
        weight_kdj_thresholds = state.values["weight_kdj_thresholds"]
        worker_count = state.values["worker_count"]
        write_status_json = state.values["write_status_json"]
        if request.round_index != round_index + 1:
            raise RuntimeError(
                f"runtime round sequence mismatch: expected={round_index + 1} "
                f"actual={request.round_index}"
            )
        round_stage_tracker.transition(
            "candidate_generation",
            round_index=round_index + 1,
            active_workers=1,
        )
        guard_rounds = active_supervisor_guard_rounds(guard_history, rounds)
        stagnation_rounds = active_supervisor_stagnation_round_count(
            int(guard_continuity_info.get("stagnation_rounds") or 0),
            rounds,
        )
        phase, step, phase_stage = phase_for_round(round_index, stagnation_rounds=stagnation_rounds)
        min_search_base_distance = search_base_min_distance_for_phase(phase_stage)
        rank_homogeneity = rank_homogeneity_guardrail(
            guard_rounds,
            stagnation_rounds=stagnation_rounds,
        )
        rank_signature_cooldown_hashes = tuple(rank_homogeneity.get("signatures") or ()) if rank_homogeneity["active"] else ()
        stagnation_restart_budget = (
            min(max_configs_per_round, max(3, max_configs_per_round // 5))
            if rank_homogeneity["active"]
            else 0
        )
        stagnation_restart_position = stagnation_restart_catalog_position(
            rank_homogeneity,
            budget=stagnation_restart_budget,
        )
        rank_homogeneity = {
            **rank_homogeneity,
            "restart_batch_index": stagnation_restart_position["batch_index"],
            "restart_catalog_offset": stagnation_restart_position["catalog_offset"],
        }
        near_miss_inversion_budget = (
            min(len(near_miss_inversion_configs), max(2, max_configs_per_round // 7))
            if enable_target_weight_inversion_advisor and stagnation_rounds >= NEAR_MISS_INVERSION_STAGNATION_THRESHOLD
            else 0
        )
        probability_focus_configs = (
            (probability_focus_config,)
            if probability_focus_config is not None and probability_focus_remaining > 0
            else ()
        )
        probability_focus_budget = len(probability_focus_configs)
        historical_summaries = merge_leaderboard(leaderboard, prior_leaderboard, limit=32)
        low_coverage_fields = low_coverage_fields_from_summaries(historical_summaries)
        elite_configs = tuple(FrequencyRankerConfig(**summary["config"]) for summary in leaderboard[:4])
        control_configs = control_experiment_configs(best_config)
        target_weight_inversion_guardrail = target_weight_inversion_budget_guardrail(
            target_weight_inversion_budget_share if enable_target_weight_inversion_advisor else 0.0,
            latest=target_weight_inversion_latest,
            stagnation_rounds=stagnation_rounds,
        )
        budgets = candidate_budget(
            max_configs_per_round,
            recency_canary_budget_share=DEFAULT_RECENCY_CANARY_BUDGET_SHARE,
            weight_kdj_budget_share=weight_kdj_budget_share if enable_weight_kdj_advisor else 0.0,
            ridge_kdj_budget_share=ridge_kdj_budget_share if enable_ridge_kdj_advisor else 0.0,
            neural_kdj_budget_share=neural_kdj_budget_share if enable_neural_kdj_advisor else 0.0,
            target_weight_inversion_budget_share=target_weight_inversion_guardrail["effective_share"],
            target_weight_inversion_available=len(target_weight_inversion_configs),
            target_weight_inversion_max_candidates=target_weight_inversion_max_candidates,
        )
        weight_kdj_budget = budgets.get("weight_kdj", 0)
        ridge_kdj_budget = budgets.get("ridge_kdj", 0)
        neural_kdj_budget = budgets.get("neural_kdj", 0)
        recency_canary_budget = budgets.get("recency_canary", 0)
        target_weight_inversion_budget = budgets.get("target_weight_inversion", 0)
        budgets["near_miss_inversion"] = near_miss_inversion_budget
        budgets["probability_focus"] = probability_focus_budget
        normal_config_budget = (
            max_configs_per_round
            - weight_kdj_budget
            - ridge_kdj_budget
            - neural_kdj_budget
            - recency_canary_budget
            - target_weight_inversion_budget
            - near_miss_inversion_budget
            - stagnation_restart_budget
            - probability_focus_budget
        )
        normal_config_budget = max(1, normal_config_budget)
        normal_candidate_pool = tuple(
            generate_configs(
                search_base_config,
                phase=phase,
                step=step,
                max_configs=max_configs_per_round,
                elite_configs=elite_configs,
                historical_summaries=historical_summaries,
                low_coverage_fields=low_coverage_fields,
                stagnation_rounds=stagnation_rounds,
                round_index=round_index + 1,
            )
        )
        configs = normal_candidate_pool[:normal_config_budget]
        normal_configs = configs
        historical_restart_hashes = historical_candidate_source_hashes(
            [*reversed(rounds), *navigation_records],
            source="stagnation_restart",
        )
        historical_restart_hash_set = set(historical_restart_hashes)
        baseline_stagnation_restart_configs = stagnation_restart_candidate_configs(
            search_base_config,
            max_configs=stagnation_restart_budget,
            round_index=round_index + 1,
            stagnation_rounds=stagnation_rounds,
            catalog_offset=stagnation_restart_position["catalog_offset"],
        )
        baseline_restart_hashes = bounded_unique_config_hashes(
            baseline_stagnation_restart_configs,
            limit=len(baseline_stagnation_restart_configs) or 1,
        )
        reused_restart_hashes = tuple(
            hash_value
            for hash_value in baseline_restart_hashes
            if hash_value in historical_restart_hash_set
        )
        stagnation_restart_configs = (
            stagnation_restart_candidate_configs(
                search_base_config,
                max_configs=stagnation_restart_budget,
                round_index=round_index + 1,
                stagnation_rounds=stagnation_rounds,
                catalog_offset=stagnation_restart_position["catalog_offset"],
                excluded_config_hashes=historical_restart_hashes,
            )
            if reused_restart_hashes
            else baseline_stagnation_restart_configs
        )
        generated_restart_hashes = bounded_unique_config_hashes(
            stagnation_restart_configs,
            limit=len(stagnation_restart_configs) or 1,
        )
        generated_restart_hash_set = set(generated_restart_hashes)
        restart_candidate_novelty = {
            "history_hash_count": len(historical_restart_hashes),
            "baseline_candidate_count": len(baseline_restart_hashes),
            "baseline_reused_count": len(reused_restart_hashes),
            "baseline_reused_hashes": list(reused_restart_hashes),
            "generated_candidate_count": len(generated_restart_hashes),
            "generated_reused_count": sum(
                hash_value in historical_restart_hash_set
                for hash_value in generated_restart_hashes
            ),
            "replacement_count": len(
                generated_restart_hash_set - set(baseline_restart_hashes)
            ),
            "novelty_enforced": bool(reused_restart_hashes),
        }
        rank_homogeneity = {
            **rank_homogeneity,
            "restart_candidate_novelty": restart_candidate_novelty,
        }
        recency_canary_configs = recency_canary_candidate_configs(
            search_base_config,
            step=step,
            max_configs=recency_canary_budget,
        )
        kdj_signals: list[dict] = []
        weight_kdj_signals: list[dict] = []
        if enable_weight_kdj_advisor or enable_ridge_kdj_advisor or enable_neural_kdj_advisor:
            with get_connection() as conn:
                kdj_signals = load_recent_training_weight_signals(
                    conn,
                    signal_run_id=weight_kdj_run_id,
                    as_of_issue=as_of_issue_value,
                    train_mode=train_mode,
                    train_window=train_window,
                    top_n=top_n,
                    limit=weight_kdj_limit,
                )
        advisor_outcome = RuntimeAdvisorOrchestrator().propose(
            base_config=search_base_config,
            signals=kdj_signals,
            budgets=budgets,
            target_weight_inversion_configs=target_weight_inversion_configs,
            settings=RuntimeAdvisorSettings(
                enable_weight_kdj=enable_weight_kdj_advisor,
                enable_ridge_kdj=enable_ridge_kdj_advisor,
                enable_neural_kdj=enable_neural_kdj_advisor,
                enable_target_weight_inversion=enable_target_weight_inversion_advisor,
                weight_min_objective_delta=weight_kdj_min_objective_delta,
                weight_min_abs_offset=weight_kdj_min_abs_offset,
                weight_slope_window=weight_kdj_slope_window,
                weight_neutral_band=weight_kdj_neutral_band,
                ridge_step=DEFAULT_RIDGE_KDJ_STEP,
                ridge_alpha=ridge_kdj_alpha,
                ridge_min_confidence=ridge_kdj_min_confidence,
                ridge_min_train_rows=ridge_kdj_min_train_rows,
                ridge_min_validation_rows=ridge_kdj_min_validation_rows,
                neural_step=DEFAULT_NEURAL_KDJ_STEP,
                neural_seed=neural_kdj_seed,
                neural_hidden_units=neural_kdj_hidden_units,
                neural_epochs=neural_kdj_epochs,
                neural_min_confidence=neural_kdj_min_confidence,
            ),
        )
        advisor_candidates = advisor_outcome.candidates
        advisor_configs_by_source = advisor_outcome.configs_by_source
        weight_kdj_signals = kdj_signals if enable_weight_kdj_advisor else []
        ridge_kdj_signals = kdj_signals if enable_ridge_kdj_advisor else []
        neural_kdj_signals = kdj_signals if enable_neural_kdj_advisor else []
        weight_kdj_advice = advisor_outcome.weight_advice
        ridge_kdj_advice = advisor_outcome.ridge_advice
        neural_kdj_advice = advisor_outcome.neural_advice
        weight_kdj_configs = advisor_configs_by_source["weight_kdj"]
        ridge_kdj_configs = advisor_configs_by_source["ridge_kdj"]
        neural_kdj_configs = advisor_configs_by_source["neural_kdj"]
        target_weight_inversion_configs = advisor_configs_by_source[
            "target_weight_inversion"
        ]
        composition = CandidateSourceComposer(
            merge_reserved=merge_reserved_candidate_configs,
            refill=refill_candidate_configs,
            config_hash=config_hash,
        ).compose(
            normal_pool=normal_candidate_pool,
            normal_budget=normal_config_budget,
            reserved_sources=(
                ReservedCandidateSource(
                    "recency_canary",
                    recency_canary_configs,
                    recency_canary_budget,
                    max_configs_per_round
                    - weight_kdj_budget
                    - ridge_kdj_budget
                    - neural_kdj_budget
                    - target_weight_inversion_budget,
                ),
                ReservedCandidateSource(
                    "weight_kdj",
                    weight_kdj_configs,
                    weight_kdj_budget,
                    max_configs_per_round
                    - ridge_kdj_budget
                    - neural_kdj_budget
                    - target_weight_inversion_budget,
                ),
                ReservedCandidateSource(
                    "ridge_kdj",
                    ridge_kdj_configs,
                    ridge_kdj_budget,
                    max_configs_per_round
                    - neural_kdj_budget
                    - target_weight_inversion_budget,
                ),
                ReservedCandidateSource(
                    "neural_kdj",
                    neural_kdj_configs,
                    neural_kdj_budget,
                    max_configs_per_round - target_weight_inversion_budget,
                ),
                ReservedCandidateSource(
                    "target_weight_inversion",
                    target_weight_inversion_configs,
                    target_weight_inversion_budget,
                    max_configs_per_round
                    - near_miss_inversion_budget
                    - stagnation_restart_budget,
                    include_when_zero_budget=enable_target_weight_inversion_advisor,
                ),
                ReservedCandidateSource(
                    "near_miss_inversion",
                    near_miss_inversion_configs,
                    near_miss_inversion_budget,
                    max_configs_per_round - stagnation_restart_budget,
                ),
                ReservedCandidateSource(
                    "stagnation_restart",
                    stagnation_restart_configs,
                    stagnation_restart_budget,
                    max_configs_per_round,
                ),
                ReservedCandidateSource(
                    "probability_focus",
                    probability_focus_configs,
                    probability_focus_budget,
                    max_configs_per_round,
                ),
            ),
            max_configs=max_configs_per_round,
        )
        configs = composition.configs
        source_configs = dict(composition.source_configs)
        normal_configs = source_configs["normal"]
        generated_config_count = len(configs)
        keep_configs = (
            search_base_config,
            best_config,
            *elite_configs[:4],
            *probability_focus_configs,
            *(config for _label, config in control_configs),
        )
        diagnostic_sources = diagnostic_source_configs(
            source_configs,
            search_base_config=search_base_config,
            best_config=best_config,
            elite_configs=elite_configs[:4],
            probability_focus_configs=probability_focus_configs,
            control_configs=control_configs,
        )
        validation_window = frozen_validation_window(eval_window)
        prefilter_start_index = max(train_window, len(training_history) - eval_window)
        prefilter_end_index = len(training_history) - validation_window
        prefilter_target_total = len(range(prefilter_start_index, prefilter_end_index, 4))
        round_stage_tracker.transition(
            "prefilter",
            round_index=round_index + 1,
            active_workers=min(worker_count, max(1, eval_window)),
            generated_config_count=generated_config_count,
            selected_config_count=None,
            target_completed=0,
            target_total=prefilter_target_total,
        )
        refined_configs, prefilter_info = prefilter_configs(
            history=training_history,
            ranked_universe=ranked_universe,
            configs=configs,
            keep_configs=keep_configs,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            workers=worker_count,
            pool=pool,
            round_index=round_index + 1,
            diversity_quota=max(2, max_configs_per_round // 10),
            frozen_validation_window_value=validation_window,
        )
        prefilter_info["stagnation_rounds"] = stagnation_rounds
        prefilter_info["guard_continuity"] = {
            **guard_continuity_info,
            "effective_stagnation_rounds": stagnation_rounds,
            "current_run_round_count": len(rounds),
        }
        prefilter_info["phase_stage"] = phase_stage
        prefilter_info["search_base_min_distance"] = min_search_base_distance
        prefilter_info["search_base_start"] = {
            "config_hash": config_hash(search_base_config),
            "config": config_dict(search_base_config),
        }
        prefilter_info["low_coverage_fields"] = list(low_coverage_fields)
        prefilter_info["candidate_budget"] = budgets
        prefilter_info["advisor_registry"] = {
            "protocol": "training_advisor_registry_v1",
            "candidate_count": len(advisor_candidates),
            "sources": {
                key: {
                    "protocol_version": next(
                        (
                            candidate.protocol_version
                            for candidate in advisor_candidates
                            if candidate.source_key == key
                        ),
                        "",
                    ),
                    "candidate_count": len(configs_for_source),
                    "candidate_hashes": [config_hash(config) for config in configs_for_source],
                }
                for key, configs_for_source in advisor_configs_by_source.items()
                if configs_for_source
            },
        }
        prefilter_info["candidate_budget"]["stagnation_restart"] = stagnation_restart_budget
        prefilter_info["stagnation_restart_catalog_offset"] = stagnation_restart_position["catalog_offset"]
        prefilter_info["rank_homogeneity_guardrail"] = rank_homogeneity
        prefilter_info["target_weight_inversion_budget_guardrail"] = target_weight_inversion_guardrail
        prefilter_info["source_survival"] = candidate_source_survival(
            source_configs,
            refined_configs=refined_configs,
        )
        advisor_info = weight_kdj_advisor_metadata(
            weight_kdj_signals,
            weight_kdj_configs,
            budget=weight_kdj_budget,
            thresholds=weight_kdj_thresholds,
            advice=weight_kdj_advice,
        )
        ridge_advisor_info = ridge_kdj_advisor_metadata(
            ridge_kdj_signals,
            ridge_kdj_configs,
            enabled=enable_ridge_kdj_advisor,
            budget=ridge_kdj_budget,
            params=ridge_kdj_params,
            thresholds=ridge_kdj_thresholds,
            advice=ridge_kdj_advice,
        )
        neural_advisor_info = neural_kdj_advisor_metadata(
            neural_kdj_signals,
            neural_kdj_configs,
            enabled=enable_neural_kdj_advisor,
            budget=neural_kdj_budget,
            params=neural_kdj_params,
            thresholds=neural_kdj_thresholds,
            advice=neural_kdj_advice,
        )
        prefilter_info["weight_kdj_advisor"] = advisor_info
        prefilter_info["ridge_kdj_advisor"] = ridge_advisor_info
        prefilter_info["neural_kdj_advisor"] = neural_advisor_info
        prefilter_info["target_weight_inversion_advisor"] = target_weight_inversion_latest or target_weight_inversion_advisor_metadata(
            enabled=enable_target_weight_inversion_advisor,
            budget=target_weight_inversion_budget,
            configs=target_weight_inversion_configs[:target_weight_inversion_budget],
            max_targets=target_weight_inversion_max_targets,
            max_deltas_per_target=target_weight_inversion_max_deltas_per_target,
        )
        status["weight_kdj_advisor"]["latest"] = advisor_info
        status["ridge_kdj_advisor"]["latest"] = ridge_advisor_info
        status["neural_kdj_advisor"]["latest"] = neural_advisor_info
        status["target_weight_inversion_advisor"]["latest"] = prefilter_info["target_weight_inversion_advisor"]
        status["prefilter"]["latest"] = prefilter_info
        log(
            f"round={round_index + 1} phase={phase} step={step} "
            f"configs={generated_config_count}->{len(refined_configs)} "
            f"stagnation={stagnation_rounds} "
            f"prefilter_targets={prefilter_info['target_count']} "
            f"prefilter_workers={prefilter_info.get('target_worker_count', 1)} "
            f"prefilter_elapsed={prefilter_info['elapsed_seconds']}s "
            f"search_base={config_dict(search_base_config)}"
        )
        round_stage_tracker.transition(
            "main_evaluation",
            round_index=round_index + 1,
            active_workers=min(worker_count, max(1, eval_window)),
            generated_config_count=generated_config_count,
            selected_config_count=len(refined_configs),
            target_completed=0,
            target_total=eval_window,
        )

        def publish_round_evaluation_progress(progress: dict) -> None:
            round_stage_tracker.update_target_progress(
                completed=int(progress.get("target_index") or 0),
                total=int(progress.get("target_total") or 0),
                publish=False,
            )
            publish_progress(progress)

        summaries = evaluate_configs(
            history=training_history,
            ranked_universe=ranked_universe,
            configs=refined_configs,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            workers=worker_count,
            pool=pool,
            progress_interval=progress_interval,
            round_index=round_index + 1,
            progress_callback=publish_round_evaluation_progress,
            frozen_validation_window_value=validation_window,
        )
        round_stage_tracker.transition(
            "post_evaluation_diagnostics",
            round_index=round_index + 1,
            active_workers=1,
            generated_config_count=generated_config_count,
            selected_config_count=len(refined_configs),
            target_completed=eval_window,
            target_total=eval_window,
        )
        normalized = RuntimeEvaluationNormalizer(
            attach_candidate_source_metadata=attach_candidate_source_metadata,
            attach_baseline_overlap=attach_baseline_overlap,
            sort_key=sort_key,
            control_experiment_summaries=control_experiment_summaries,
            prefilter_holdout_isolation_audit=prefilter_holdout_isolation_audit,
            frozen_validation_promotion_gate=frozen_validation_promotion_gate,
            quarantine_historical_frozen_promotion=quarantine_historical_frozen_promotion,
        ).normalize(
            summaries=summaries,
            diagnostic_sources=diagnostic_sources,
            advisor_candidates=advisor_candidates,
            control_configs=control_configs,
            universe_size=len(ranked_universe),
            prefilter_target_issues=prefilter_info.get("target_issues") or (),
            prior_best_summary=best_summary,
        )
        summaries = normalized.summaries
        control_summaries = normalized.control_summaries
        round_best = normalized.round_best
        prior_best_summary = normalized.prior_best_summary
        promotion_gate = normalized.promotion_gate
        improved = normalized.improved
        raw_improved = normalized.raw_improved
        prefilter_isolation = normalized.prefilter_isolation
        evaluation_split = normalized.evaluation_split
        eval_slice_overfit = eval_slice_overfit_guardrail(
            summaries=summaries,
            source_configs=diagnostic_sources,
            round_best=round_best,
            prior_best_summary=prior_best_summary,
            rank_homogeneity=rank_homogeneity,
            promotion_gate=promotion_gate,
            stagnation_rounds=stagnation_rounds,
        )
        round_best_search_gate = stale_round_best_search_base_gate(
            stagnation_rounds=stagnation_rounds,
            rank_homogeneity=rank_homogeneity,
            promotion_gate=promotion_gate,
            eval_slice_overfit=eval_slice_overfit,
            frozen_promotion_only=True,
        )
        require_frozen_primary_navigation = bool(
            round_best_search_gate.get("require_frozen_primary_challenger")
        )
        exploration_champion, exploration_champion_info = select_stagnation_exploration_champion(
            summaries=summaries,
            source_configs=source_configs,
            round_best=round_best,
            stagnation_rounds=stagnation_rounds,
        )
        restart_champion, restart_champion_info = select_rank_homogeneity_restart_champion(
            summaries=summaries,
            source_configs=source_configs,
            round_best=round_best,
            prior_best_summary=prior_best_summary,
            rank_homogeneity=rank_homogeneity,
        )
        experimental_navigation_candidate, experimental_navigation_info = select_experimental_navigation_candidate(
            exploration_champion=exploration_champion,
            exploration_champion_info=exploration_champion_info,
            restart_champion=restart_champion,
            restart_champion_info=restart_champion_info,
        )
        probability_champion, probability_champion_info = select_probability_calibration_champion(
            summaries=summaries,
            source_configs=source_configs,
            round_best=round_best,
            prior_best_summary=prior_best_summary,
            stagnation_rounds=stagnation_rounds,
            force_primary_gate=bool(eval_slice_overfit["force_primary_gate"]),
            frozen_promotion_only=True,
        )
        source_frontier_champion, source_frontier_champion_info = select_source_frontier_champion(
            summaries=summaries,
            source_configs=source_configs,
            round_best=round_best,
            prior_best_summary=prior_best_summary,
            stagnation_rounds=stagnation_rounds,
        )
        evaluated_probability_focus_summary = None
        if probability_focus_hash:
            for summary in summaries:
                if summary_config_hash(summary) == probability_focus_hash:
                    evaluated_probability_focus_summary = summary
                    break
        probability_focus_had_state = bool(
            probability_focus_hash or probability_focus_config is not None or probability_focus_remaining > 0
        )
        probability_focus_info = {
            "active": False,
            "hold_rounds": PROBABILITY_FOCUS_HOLD_ROUNDS,
            "remaining_rounds": max(0, probability_focus_remaining),
            "source": probability_focus_source,
            "config_hash": probability_focus_hash,
            "score": list(probability_focus_score) if probability_focus_score else None,
            "refreshed": False,
            "reason": "inactive",
        }
        probability_focus_decision_summary = None
        if improved:
            probability_focus_config = None
            probability_focus_hash = ""
            probability_focus_source = ""
            probability_focus_score = ()
            probability_focus_remaining = 0
            probability_focus_info["reason"] = "cleared_on_new_best" if probability_focus_had_state else "inactive"
        elif probability_champion is not None:
            champion_config = summary_config(probability_champion)
            champion_hash = summary_config_hash(probability_champion) or ""
            champion_score = probability_calibration_score(probability_champion)
            should_refresh_focus = should_refresh_probability_focus(
                champion_config=champion_config,
                champion_hash=champion_hash,
                champion_score=champion_score,
                probability_focus_hash=probability_focus_hash,
                probability_focus_score=probability_focus_score,
            )
            if should_refresh_focus and champion_config is not None:
                probability_focus_config = champion_config
                probability_focus_hash = champion_hash
                probability_focus_source = str(probability_champion_info.get("source") or "")
                probability_focus_score = champion_score
                probability_focus_remaining = PROBABILITY_FOCUS_HOLD_ROUNDS
                probability_focus_decision_summary = probability_champion
                probability_focus_info.update(
                    {
                        "active": True,
                        "remaining_rounds": probability_focus_remaining,
                        "source": probability_focus_source,
                        "config_hash": probability_focus_hash,
                        "score": list(probability_focus_score),
                        "refreshed": True,
                        "reason": "refreshed_from_probability_champion",
                    }
                )
            elif probability_focus_config is not None and probability_focus_remaining > 0:
                probability_focus_remaining = max(0, probability_focus_remaining - 1)
                probability_focus_decision_summary = evaluated_probability_focus_summary
                probability_focus_info.update(
                    {
                        "active": evaluated_probability_focus_summary is not None and probability_focus_remaining > 0,
                        "remaining_rounds": probability_focus_remaining,
                        "source": probability_focus_source,
                        "config_hash": probability_focus_hash,
                        "score": list(probability_focus_score) if probability_focus_score else None,
                        "reason": "kept_stronger_existing_focus",
                    }
                )
        elif probability_focus_config is not None and probability_focus_remaining > 0:
            probability_focus_remaining = max(0, probability_focus_remaining - 1)
            probability_focus_decision_summary = evaluated_probability_focus_summary
            probability_focus_info.update(
                {
                    "active": evaluated_probability_focus_summary is not None and probability_focus_remaining > 0,
                    "remaining_rounds": probability_focus_remaining,
                    "source": probability_focus_source,
                    "config_hash": probability_focus_hash,
                    "score": list(probability_focus_score) if probability_focus_score else None,
                    "reason": "held_previous_probability_focus",
                }
            )
        if probability_focus_remaining <= 0 and probability_focus_had_state:
            probability_focus_reason = probability_focus_info.get("reason")
            probability_focus_decision_summary = None
            probability_focus_config = None
            probability_focus_hash = ""
            probability_focus_source = ""
            probability_focus_score = ()
            probability_focus_remaining = 0
            probability_focus_info.update(
                {
                    "active": False,
                    "remaining_rounds": 0,
                    "source": "",
                    "config_hash": "",
                    "score": None,
                    "reason": "cleared_on_new_best"
                    if probability_focus_reason == "cleared_on_new_best"
                    else "expired",
                }
            )
        decision_round_best, decision_round_best_info = select_decision_round_best(
            round_best=round_best,
            prior_best_summary=prior_best_summary,
            improved=improved,
            probability_focus_decision_summary=probability_focus_decision_summary,
            probability_champion=probability_champion,
            source_frontier_champion=None,
            restart_champion=restart_champion,
            exploration_champion=exploration_champion,
            require_frozen_primary_lift=require_frozen_primary_navigation,
        )
        decision_round_best_info["selection_uses_frozen_validation"] = False
        decision_round_best_info["selection_basis"] = "search_slice_only"
        inversion_anchor, challenger_summary, inversion_anchor_info = select_target_weight_inversion_anchor(
            summaries=summaries,
            prior_best_summary=prior_best_summary,
            round_best=decision_round_best,
            improved=improved,
            require_frozen_primary_lift=require_frozen_primary_navigation,
            frozen_primary_lift_baseline=prior_best_summary,
        )
        prefilter_info["frozen_validation_window"] = validation_window
        prefilter_info["holdout_isolation"] = {
            "protocol": HOLDOUT_ISOLATION_PROTOCOL,
            "total_window": evaluation_split.get("total_window"),
            "search_window": evaluation_split.get("search_window"),
            "frozen_window": evaluation_split.get("frozen_window"),
            "issue_overlap_count": evaluation_split.get("issue_overlap_count"),
            "search_uses_frozen_validation": bool(
                prefilter_isolation["prefilter_uses_frozen_validation"]
            ),
            "prefilter_isolation_status": prefilter_isolation["status"],
            "prefilter_target_count": prefilter_isolation["prefilter_target_count"],
            "prefilter_search_issue_overlap_count": prefilter_isolation[
                "prefilter_search_issue_overlap_count"
            ],
            "prefilter_frozen_issue_overlap_count": prefilter_isolation[
                "prefilter_frozen_issue_overlap_count"
            ],
            "prefilter_frozen_issue_overlap": prefilter_isolation[
                "prefilter_frozen_issue_overlap"
            ],
            "prefilter_outside_split_issue_count": prefilter_isolation[
                "prefilter_outside_split_issue_count"
            ],
            "prefilter_uses_frozen_validation": prefilter_isolation[
                "prefilter_uses_frozen_validation"
            ],
            "frozen_validation_role": "promotion_only",
            "source_frontier_used_for_navigation": False,
            "historical_holdout_quarantined": bool(
                promotion_gate.get("historical_holdout_quarantined")
            ),
            "promotion_holdout_status": promotion_gate.get("promotion_holdout_status"),
            "forward_unseen_evidence_required": True,
        }
        prefilter_info["control_experiments"] = control_summaries
        prefilter_info["promotion_gate"] = promotion_gate
        prefilter_info["eval_slice_overfit_guardrail"] = eval_slice_overfit
        prefilter_info["stale_round_best_search_base_gate"] = round_best_search_gate
        prefilter_info["raw_improved"] = raw_improved
        prefilter_info["round_best_rank_movement_vs_incumbent"] = target_rank_movement(round_best, prior_best_summary)
        prefilter_info["round_best_rank_signature_hash"] = rank_signature_hash(round_best)
        prefilter_info["round_best_probability_calibration"] = round_best.get("probability_calibration")
        prefilter_info["exploration_champion"] = exploration_champion_info
        prefilter_info["rank_homogeneity_restart_champion"] = restart_champion_info
        prefilter_info["experimental_navigation_candidate"] = experimental_navigation_info
        prefilter_info["probability_calibration_champion"] = probability_champion_info
        prefilter_info["probability_focus"] = probability_focus_info
        prefilter_info["decision_round_best"] = decision_round_best_info
        status["probability_focus"]["latest"] = probability_focus_info
        prefilter_info["source_survival"] = candidate_source_survival(
            source_configs,
            refined_configs=refined_configs,
            full_eval_top_results=summaries[: min(5, len(summaries))],
            round_best=round_best,
        )
        prefilter_info["source_frontier"] = source_frontier_diagnostics(
            summaries=summaries,
            source_configs=source_configs,
            prior_best_summary=prior_best_summary,
            round_best=round_best,
        )
        prefilter_info["source_frontier_champion"] = source_frontier_champion_info
        self_diagnostics = training_round_self_diagnostics(
            round_best=round_best,
            source_configs=source_configs,
            refined_configs=refined_configs,
            summaries=summaries,
            rank_homogeneity=rank_homogeneity,
            promotion_gate=promotion_gate,
            eval_slice_overfit=eval_slice_overfit,
            target_weight_inversion_guardrail=target_weight_inversion_guardrail,
            advisor_info=advisor_info,
            ridge_advisor_info=ridge_advisor_info,
            neural_advisor_info=neural_advisor_info,
            universe_size=len(ranked_universe),
            sequential_null_ledger=sequential_null_ledger,
            completed_round_diagnostics=recent_round_self_diagnostics(
                rounds,
                limit=len(rounds),
            ),
            completed_round_count=len(rounds),
        )
        prefilter_info["self_diagnostics"] = self_diagnostics
        round_sequential_null_ledger = self_diagnostics["signal_vs_noise"].get(
            "sequential_family"
        )
        prefilter_info["sequential_null_ledger"] = round_sequential_null_ledger
        status["sequential_null_ledger"] = round_sequential_null_ledger
        status["self_diagnostics"] = self_diagnostics
        prefilter_info["round_best_replays_incumbent"] = inversion_anchor_info["round_best_replays_incumbent"]
        prefilter_info["challenger_best"] = strip_target_results(challenger_summary) if challenger_summary else None
        prefilter_info["challenger_probability_calibration"] = (
            challenger_summary.get("probability_calibration")
            if isinstance(challenger_summary, dict)
            else None
        )
        prefilter_info["target_weight_inversion_anchor"] = inversion_anchor_info
        inversion_rows: list[dict] = []
        inversion_aggregate: dict = {}
        round_stage_tracker.transition(
            "target_weight_inversion",
            round_index=round_index + 1,
            active_workers=(
                min(worker_count, max(1, target_weight_inversion_max_targets))
                if enable_target_weight_inversion_advisor
                else 0
            ),
            generated_config_count=generated_config_count,
            selected_config_count=len(refined_configs),
            target_completed=0,
            target_total=target_weight_inversion_max_targets,
            details={
                "enabled": enable_target_weight_inversion_advisor,
                "max_candidates": target_weight_inversion_max_candidates,
                "max_deltas_per_target": target_weight_inversion_max_deltas_per_target,
            },
        )
        if enable_target_weight_inversion_advisor:
            inversion_rows, inversion_aggregate, target_weight_inversion_configs, target_weight_inversion_latest = target_weight_inversion_advisor(
                history=training_history,
                ranked_universe=ranked_universe,
                best_summary=inversion_anchor,
                train_window=train_window,
                train_mode=train_mode,
                top_n=top_n,
                max_candidates=target_weight_inversion_max_candidates,
                max_targets=target_weight_inversion_max_targets,
                max_deltas_per_target=target_weight_inversion_max_deltas_per_target,
                budget=max(0, target_weight_inversion_max_candidates),
                control_experiments=control_summaries,
                frozen_validation_window_value=validation_window,
                workers=worker_count,
                progress_callback=lambda completed, total: round_stage_tracker.update_target_progress(
                    completed=completed,
                    total=total,
                    publish=(completed == 1 or completed == total or completed % 10 == 0),
                ),
            )
        else:
            target_weight_inversion_configs = ()
            target_weight_inversion_latest = target_weight_inversion_advisor_metadata(
                enabled=False,
                budget=0,
                max_targets=target_weight_inversion_max_targets,
                max_deltas_per_target=target_weight_inversion_max_deltas_per_target,
                workers=worker_count,
            )
        target_weight_inversion_latest = {
            **target_weight_inversion_latest,
            "anchor": inversion_anchor_info,
            "signal_scope": "search_slice",
            "expected_cutoff_issue": (
                ((round_best.get("evaluation_split") or {}).get("search_issues") or [""])[-1]
                if isinstance(round_best.get("evaluation_split"), dict)
                else ""
            ),
            "history_latest_issue": as_of_issue_value,
        }
        prefilter_info["target_weight_inversion_advisor"] = target_weight_inversion_latest
        status["target_weight_inversion_advisor"]["latest"] = target_weight_inversion_latest
        round_stage_tracker.transition(
            "near_miss_inversion",
            round_index=round_index + 1,
            active_workers=1,
            generated_config_count=generated_config_count,
            selected_config_count=len(refined_configs),
        )
        near_miss_inversion_configs, near_miss_inversion_latest = near_miss_inversion_advisor(
            history=training_history,
            ranked_universe=ranked_universe,
            best_summary=decision_round_best,
            train_window=train_window,
            train_mode=train_mode,
            enabled=enable_target_weight_inversion_advisor
            and stagnation_rounds >= NEAR_MISS_INVERSION_STAGNATION_THRESHOLD,
            max_configs=max(0, target_weight_inversion_max_candidates),
            max_delta_candidates=target_weight_inversion_max_deltas_per_target,
        )
        prefilter_info["near_miss_inversion_advisor"] = near_miss_inversion_latest
        status["near_miss_inversion_advisor"]["latest"] = near_miss_inversion_latest
        leaderboard = merge_leaderboard(leaderboard, summaries[: min(8, len(summaries))])
        fallback_search_base_config, fallback_search_base_info = select_next_search_base(
            current_base=search_base_config,
            summaries=summaries,
            round_best=decision_round_best,
            improved=improved,
            exploration_navigation_candidate=experimental_navigation_candidate,
            exploration_navigation_source=str(experimental_navigation_info.get("source") or ""),
            exploration_navigation_reason=str(experimental_navigation_info.get("reason") or ""),
            recent_search_base_hashes=recent_search_base_hashes(rounds, search_base_config),
            excluded_rank_signature_hashes=rank_signature_cooldown_hashes,
            min_config_distance=min_search_base_distance,
            allow_unpromoted_round_best=bool(round_best_search_gate["allow_unpromoted_round_best"]),
            round_best_skip_reason=str(round_best_search_gate["reason"]),
            require_frozen_primary_lift=require_frozen_primary_navigation,
            frozen_primary_lift_baseline=prior_best_summary,
            frozen_promotion_only=True,
        )
        next_search_base_config = fallback_search_base_config
        search_base_info = fallback_search_base_info
        if probability_focus_info["active"] and probability_focus_decision_summary is not None:
            focus_recent_search_base_hashes = (
                recent_search_base_hashes(rounds, search_base_config)
                if rank_homogeneity["active"]
                else ()
            )
            focus_search_base_config, focus_search_base_info = select_probability_focus_search_base(
                current_base=search_base_config,
                focus_summary=probability_focus_decision_summary,
                focus_info=probability_focus_info,
                excluded_rank_signature_hashes=rank_signature_cooldown_hashes,
                recent_search_base_hashes=focus_recent_search_base_hashes,
                min_config_distance=min_search_base_distance if rank_homogeneity["active"] else 0.0,
                require_frozen_primary_lift=require_frozen_primary_navigation,
                frozen_primary_lift_baseline=prior_best_summary,
            )
            if focus_search_base_config is not None:
                next_search_base_config = focus_search_base_config
                search_base_info = merge_experimental_navigation_arbitration(
                    focus_search_base_info,
                    fallback_search_base_info,
                )
        search_base_info["phase"] = phase
        search_base_info["phase_stage"] = phase_stage
        search_base_info["step"] = step
        search_base_info["selection_uses_frozen_validation"] = False
        search_base_info["selection_basis"] = "search_slice_only"
        prefilter_info["search_base"] = search_base_info
        log(
            f"round={round_index + 1} target_weight_inversion_anchor="
            f"{inversion_anchor_info['source']} "
            f"config_hash={inversion_anchor_info.get('config_hash', '')} "
            f"round_best_replays_incumbent={inversion_anchor_info['round_best_replays_incumbent']}"
        )
        if rank_homogeneity["active"]:
            log(
                f"round={round_index + 1} rank_homogeneity_restart="
                f"unique={rank_homogeneity['unique_signature_count']}/{rank_homogeneity['observed']} "
                f"budget={stagnation_restart_budget} "
                f"batch={stagnation_restart_position['batch_index']} "
                f"catalog_offset={stagnation_restart_position['catalog_offset']}"
            )
            if restart_candidate_novelty["baseline_reused_count"]:
                log(
                    f"round={round_index + 1} restart_candidate_novelty="
                    f"filtered={restart_candidate_novelty['baseline_reused_count']} "
                    f"replacements={restart_candidate_novelty['replacement_count']} "
                    f"history_hashes={restart_candidate_novelty['history_hash_count']} "
                    f"generated_reused={restart_candidate_novelty['generated_reused_count']}"
                )
        if eval_slice_overfit["active"]:
            log(
                f"round={round_index + 1} eval_slice_overfit_guardrail="
                f"{eval_slice_overfit['reason']} "
                f"eval_primary={eval_slice_overfit['round_best_eval_primary_score']} "
                f"frozen_primary={eval_slice_overfit['round_best_frozen_primary_score']} "
                f"suspicious={eval_slice_overfit['suspicious_candidate_count']}"
            )
        log(
            f"round={round_index + 1} self_diagnostics="
            f"{self_diagnostics['synthesis']['status']} "
            f"action={self_diagnostics['synthesis']['action']} "
            f"weight={self_diagnostics['weight_trust']['status']} "
            f"space={self_diagnostics['candidate_space']['status']} "
            f"signal={self_diagnostics['signal_vs_noise']['status']}"
        )
        if exploration_champion_info["active"]:
            log(
                f"round={round_index + 1} exploration_champion="
                f"{exploration_champion_info['source']} "
                f"top_rank={exploration_champion_info['top_rank']} "
                f"config_hash={exploration_champion_info['config_hash']}"
            )
        if restart_champion_info["active"]:
            log(
                f"round={round_index + 1} rank_homogeneity_restart_champion="
                f"rank={restart_champion_info['full_eval_rank']} "
                f"changed_targets={restart_champion_info['changed_target_count']} "
                f"config_hash={restart_champion_info['config_hash']}"
            )
        if probability_champion_info["active"]:
            log(
                f"round={round_index + 1} probability_calibration_champion="
                f"{probability_champion_info['source']} "
                f"rank={probability_champion_info['full_eval_rank']} "
                f"changed_targets={probability_champion_info['changed_target_count']} "
                f"config_hash={probability_champion_info['config_hash']}"
            )
        if source_frontier_champion_info["active"]:
            log(
                f"round={round_index + 1} source_frontier_champion="
                f"{source_frontier_champion_info['source']} "
                f"rank={source_frontier_champion_info['full_eval_rank']} "
                f"changed_targets={source_frontier_champion_info['changed_target_count']} "
                f"config_hash={source_frontier_champion_info['config_hash']}"
            )
        if probability_focus_info["active"]:
            log(
                f"round={round_index + 1} probability_focus="
                f"{probability_focus_info['reason']} "
                f"source={probability_focus_info['source']} "
                f"remaining={probability_focus_info['remaining_rounds']} "
                f"config_hash={probability_focus_info['config_hash']}"
            )
        if near_miss_inversion_latest["candidate_count"]:
            band_summary = ",".join(
                f"{band['cutoff']}:{band['target_count']}"
                for band in near_miss_inversion_latest["bands"]
            )
            log(
                f"round={round_index + 1} near_miss_inversion="
                f"candidates={near_miss_inversion_latest['candidate_count']} "
                f"bands={band_summary}"
            )
        log(
            f"round={round_index + 1} search_base_next="
            f"{search_base_info['source']} "
            f"changed={search_base_info['changed']} "
            f"config_hash={search_base_info['config_hash']}"
        )
        if improved:
            best_summary = round_best
            best_config = FrequencyRankerConfig(**round_best["config"])
            log(f"round={round_index + 1} retained_new_best={round_best}")
        else:
            log(f"round={round_index + 1} no_improvement best_top10000={best_summary['top_10000_hits'] if best_summary else 'n/a'}")
        search_base_config = next_search_base_config
        search_training_history = (
            training_history[:-validation_window]
            if validation_window > 0
            else training_history
        )
        search_eval_window = max(1, eval_window - validation_window)
        dynamic_training_payload: dict = {
            "status": "skipped",
            "reason": "not_started",
            "protocol": DYNAMIC_KDJ_TRAINING_PROTOCOL_VERSION,
        }
        dynamic_training_selected: dict = {}
        dynamic_line_payload: dict | None = None
        dynamic_training_base_summary = (
            decision_round_best
            if isinstance(decision_round_best, dict) and isinstance(decision_round_best.get("config"), dict)
            else round_best
        )
        round_stage_tracker.transition(
            "dynamic_kdj_training",
            round_index=round_index + 1,
            active_workers=min(worker_count, max(1, search_eval_window)),
            target_completed=0,
            target_total=search_eval_window,
        )
        try:
            dynamic_training_signals = kdj_signals
            if not dynamic_training_signals:
                with get_connection() as conn:
                    dynamic_training_signals = load_recent_training_weight_signals(
                        conn,
                        signal_run_id=weight_kdj_run_id,
                        as_of_issue=as_of_issue_value,
                        train_mode=train_mode,
                        train_window=train_window,
                        top_n=top_n,
                        limit=weight_kdj_limit,
                    )
            dynamic_training_payload = dynamic_kdj_strength_sweep_training_summary(
                history=search_training_history,
                base_config=FrequencyRankerConfig(**dynamic_training_base_summary["config"]),
                signals=dynamic_training_signals,
                ranked_universe=ranked_universe,
                train_mode=train_mode,
                train_window=train_window,
                eval_window=search_eval_window,
                top_n=top_n,
                workers=worker_count,
            )
            dynamic_training_selected = (
                dynamic_training_payload.get("selected_summary")
                if isinstance(dynamic_training_payload.get("selected_summary"), dict)
                else {}
            )
            dynamic_policy = dynamic_policy_from_training_payload(
                run_id=run_id,
                round_index=round_index + 1,
                base_summary=dynamic_training_base_summary,
                training_payload=dynamic_training_payload,
            )
            if (
                dynamic_kdj_best_training_summary is None
                or regression_training_sort_key(dynamic_training_selected)
                > regression_training_sort_key(dynamic_kdj_best_training_summary)
            ):
                dynamic_kdj_best_training_summary = dynamic_training_selected
                dynamic_kdj_best_policy = dynamic_policy
            dynamic_line_payload = training_line_round_payload(
                run_id=run_id,
                round_index=round_index + 1,
                line_key=DYNAMIC_KDJ_LINE_KEY,
                line_label=DYNAMIC_KDJ_LINE_LABEL,
                line_kind="dynamic_kdj_training",
                policy_key=str(dynamic_policy.get("policy_key") or ""),
                policy_params={
                    "offset_scale": dynamic_policy.get("offset_scale"),
                    "anchor_offset_scale": dynamic_policy.get("anchor_offset_scale"),
                    "min_offset_scale": dynamic_policy.get("min_offset_scale"),
                    "max_offset_scale": dynamic_policy.get("max_offset_scale"),
                    "strength_mode": dynamic_policy.get("strength_mode"),
                    "selection_method": dynamic_policy.get("selection_method"),
                    "base_config_hash": dynamic_policy.get("base_config_hash"),
                },
                summary=dynamic_training_selected,
                status=status,
                training_payload=dynamic_training_payload,
            )
            status["dynamic_kdj_training"]["latest"] = strip_target_results(dynamic_line_payload)
            if dynamic_kdj_best_policy is not None:
                status["dynamic_kdj_training"]["best"] = {
                    "policy_key": dynamic_kdj_best_policy.get("policy_key"),
                    "offset_scale": dynamic_kdj_best_policy.get("offset_scale"),
                    "anchor_offset_scale": dynamic_kdj_best_policy.get("anchor_offset_scale"),
                    "min_offset_scale": dynamic_kdj_best_policy.get("min_offset_scale"),
                    "max_offset_scale": dynamic_kdj_best_policy.get("max_offset_scale"),
                    "strength_mode": dynamic_kdj_best_policy.get("strength_mode"),
                    "source_round_index": dynamic_kdj_best_policy.get("source_round_index"),
                    "summary": dynamic_kdj_best_training_summary,
                }
            prefilter_info["dynamic_kdj_training"] = {
                "status": dynamic_training_payload.get("status"),
                "selected_strength": dynamic_training_payload.get("selected_strength"),
                "selected_strength_policy": dynamic_training_payload.get("selected_strength_policy"),
                "selected_summary": dynamic_training_selected,
                "rows": dynamic_training_payload.get("rows"),
                "best_policy_key": dynamic_kdj_best_policy.get("policy_key") if dynamic_kdj_best_policy else None,
                "evaluation_split": {
                    "protocol": HOLDOUT_ISOLATION_PROTOCOL,
                    "search_window": search_eval_window,
                    "frozen_window": validation_window,
                    "frozen_validation_used": False,
                },
            }
            log(
                f"round={round_index + 1} dynamic_kdj_training="
                f"strength={dynamic_training_payload.get('selected_strength')} "
                f"mode={dynamic_training_payload.get('strength_mode')} "
                f"eff={dynamic_training_selected.get('effective_offset_scale_median')} "
                f"top100={dynamic_training_selected.get('top_100_hits')} "
                f"top1000={dynamic_training_selected.get('top_1000_hits')} "
                f"top10000={dynamic_training_selected.get('top_10000_hits')} "
                f"red5_top10000={(dynamic_training_selected.get('red5') or {}).get('top_10000_hits') if isinstance(dynamic_training_selected.get('red5'), dict) else None}"
                f" workers={dynamic_training_payload.get('target_worker_count')}"
                f" elapsed={dynamic_training_payload.get('elapsed_seconds')}s"
            )
        except Exception as exc:  # pragma: no cover - dynamic line training must not stop static training.
            dynamic_training_payload = {
                "status": "failed",
                "error": str(exc),
                "protocol": DYNAMIC_KDJ_TRAINING_PROTOCOL_VERSION,
            }
            status["dynamic_kdj_training"]["latest"] = dynamic_training_payload
            prefilter_info["dynamic_kdj_training"] = dynamic_training_payload
            log(f"dynamic_kdj_training_warning round={round_index + 1} error={exc}")

        near_dynamic_line_payload: dict | None = None
        near_dynamic_training_payload: dict = {
            "status": "skipped",
            "reason": "not_started",
            "protocol": NEAR_DYNAMIC_KDJ_TRAINING_PROTOCOL_VERSION,
            "line_key": NEAR_DYNAMIC_KDJ_LINE_KEY,
        }
        near_dynamic_training_selected: dict = {}
        round_stage_tracker.transition(
            "near_dynamic_kdj_training",
            round_index=round_index + 1,
            active_workers=min(worker_count, NEAR_DYNAMIC_KDJ_EVAL_WINDOW),
            target_completed=0,
            target_total=NEAR_DYNAMIC_KDJ_EVAL_WINDOW,
        )
        try:
            near_dynamic_training_signals = kdj_signals
            if not near_dynamic_training_signals:
                with get_connection() as conn:
                    near_dynamic_training_signals = load_recent_training_weight_signals(
                        conn,
                        signal_run_id=weight_kdj_run_id,
                        as_of_issue=as_of_issue_value,
                        train_mode=train_mode,
                        train_window=train_window,
                        top_n=top_n,
                        limit=weight_kdj_limit,
                    )
            near_dynamic_training_payload = dynamic_kdj_strength_sweep_training_summary(
                history=training_history,
                base_config=FrequencyRankerConfig(**dynamic_training_base_summary["config"]),
                signals=near_dynamic_training_signals,
                ranked_universe=ranked_universe,
                train_mode=NEAR_DYNAMIC_KDJ_TRAIN_MODE,
                train_window=train_window,
                eval_window=NEAR_DYNAMIC_KDJ_EVAL_WINDOW,
                top_n=top_n,
                workers=worker_count,
                line_key=NEAR_DYNAMIC_KDJ_LINE_KEY,
                protocol=NEAR_DYNAMIC_KDJ_TRAINING_PROTOCOL_VERSION,
                source="near_dynamic_kdj_strength_sweep",
            )
            near_dynamic_training_selected = (
                near_dynamic_training_payload.get("selected_summary")
                if isinstance(near_dynamic_training_payload.get("selected_summary"), dict)
                else {}
            )
            near_dynamic_policy = dynamic_policy_from_training_payload(
                run_id=run_id,
                round_index=round_index + 1,
                base_summary=dynamic_training_base_summary,
                training_payload=near_dynamic_training_payload,
                line_key=NEAR_DYNAMIC_KDJ_LINE_KEY,
                protocol=NEAR_DYNAMIC_KDJ_TRAINING_PROTOCOL_VERSION,
            )
            near_improved = (
                near_dynamic_kdj_best_training_summary is None
                or regression_training_sort_key(near_dynamic_training_selected)
                > regression_training_sort_key(near_dynamic_kdj_best_training_summary)
            )
            if near_improved:
                near_dynamic_kdj_best_training_summary = near_dynamic_training_selected
                near_dynamic_kdj_best_policy = near_dynamic_policy
                near_dynamic_kdj_stagnation_rounds = 0
            else:
                near_dynamic_kdj_stagnation_rounds += 1
            near_dynamic_kdj_sealed = False
            near_dynamic_kdj_seal_reason = ""
            near_dynamic_kdj_latest_policy = near_dynamic_policy

            if near_dynamic_policy is not None:
                near_dynamic_line_payload = training_line_round_payload(
                    run_id=run_id,
                    round_index=round_index + 1,
                    line_key=NEAR_DYNAMIC_KDJ_LINE_KEY,
                    line_label=NEAR_DYNAMIC_KDJ_LINE_LABEL,
                    line_kind="dynamic_kdj_near_training",
                    policy_key=str(near_dynamic_policy.get("policy_key") or ""),
                    policy_params={
                        "offset_scale": near_dynamic_policy.get("offset_scale"),
                        "anchor_offset_scale": near_dynamic_policy.get("anchor_offset_scale"),
                        "min_offset_scale": near_dynamic_policy.get("min_offset_scale"),
                        "max_offset_scale": near_dynamic_policy.get("max_offset_scale"),
                        "strength_mode": near_dynamic_policy.get("strength_mode"),
                        "selection_method": near_dynamic_policy.get("selection_method"),
                        "base_config_hash": near_dynamic_policy.get("base_config_hash"),
                        "near_eval_window": NEAR_DYNAMIC_KDJ_EVAL_WINDOW,
                        "train_mode": NEAR_DYNAMIC_KDJ_TRAIN_MODE,
                        "train_window": train_window,
                        "sealed": near_dynamic_kdj_sealed,
                        "seal_reason": near_dynamic_kdj_seal_reason,
                        "stagnation_rounds": near_dynamic_kdj_stagnation_rounds,
                    },
                    summary=near_dynamic_training_selected,
                    status=status,
                    training_payload=near_dynamic_training_payload,
                    train_mode_override=NEAR_DYNAMIC_KDJ_TRAIN_MODE,
                )
            status["near_dynamic_kdj_training"]["latest"] = (
                strip_target_results(near_dynamic_line_payload)
                if near_dynamic_line_payload is not None
                else near_dynamic_training_payload
            )
            if near_dynamic_kdj_best_policy is not None:
                status["near_dynamic_kdj_training"]["best"] = {
                    "policy_key": near_dynamic_kdj_best_policy.get("policy_key"),
                    "offset_scale": near_dynamic_kdj_best_policy.get("offset_scale"),
                    "anchor_offset_scale": near_dynamic_kdj_best_policy.get("anchor_offset_scale"),
                    "min_offset_scale": near_dynamic_kdj_best_policy.get("min_offset_scale"),
                    "max_offset_scale": near_dynamic_kdj_best_policy.get("max_offset_scale"),
                    "strength_mode": near_dynamic_kdj_best_policy.get("strength_mode"),
                    "source_round_index": near_dynamic_kdj_best_policy.get("source_round_index"),
                    "sealed": near_dynamic_kdj_sealed,
                    "sealed_round_index": near_dynamic_kdj_best_policy.get("sealed_round_index"),
                    "stagnation_rounds": near_dynamic_kdj_stagnation_rounds,
                    "summary": near_dynamic_kdj_best_training_summary,
                }
            status["near_dynamic_kdj_training"]["sealed"] = near_dynamic_kdj_sealed
            status["near_dynamic_kdj_training"]["stagnation_rounds"] = near_dynamic_kdj_stagnation_rounds
            prefilter_info["near_dynamic_kdj_training"] = {
                "status": near_dynamic_training_payload.get("status"),
                "selected_strength": near_dynamic_training_payload.get("selected_strength"),
                "selected_strength_policy": near_dynamic_training_payload.get("selected_strength_policy"),
                "selected_summary": near_dynamic_training_selected,
                "rows": near_dynamic_training_payload.get("rows"),
                "sealed": near_dynamic_kdj_sealed,
                "stagnation_rounds": near_dynamic_kdj_stagnation_rounds,
                "train_mode": NEAR_DYNAMIC_KDJ_TRAIN_MODE,
                "best_policy_key": near_dynamic_kdj_best_policy.get("policy_key")
                if near_dynamic_kdj_best_policy
                else None,
            }
            log(
                f"round={round_index + 1} near_dynamic_kdj_training="
                f"status={near_dynamic_training_payload.get('status')} "
                f"strength={near_dynamic_training_payload.get('selected_strength')} "
                f"train_mode={NEAR_DYNAMIC_KDJ_TRAIN_MODE} "
                f"sealed={near_dynamic_kdj_sealed} "
                f"stagnation={near_dynamic_kdj_stagnation_rounds} "
                f"top100={near_dynamic_training_selected.get('top_100_hits')} "
                f"top1000={near_dynamic_training_selected.get('top_1000_hits')} "
                f"top10000={near_dynamic_training_selected.get('top_10000_hits')} "
                f"workers={near_dynamic_training_payload.get('target_worker_count')} "
                f"elapsed={near_dynamic_training_payload.get('elapsed_seconds')}s"
            )
        except Exception as exc:  # pragma: no cover - near line training must not stop static training.
            near_dynamic_training_payload = {
                "status": "failed",
                "error": str(exc),
                "protocol": NEAR_DYNAMIC_KDJ_TRAINING_PROTOCOL_VERSION,
                "line_key": NEAR_DYNAMIC_KDJ_LINE_KEY,
            }
            status["near_dynamic_kdj_training"]["latest"] = near_dynamic_training_payload
            prefilter_info["near_dynamic_kdj_training"] = near_dynamic_training_payload
            log(f"near_dynamic_kdj_training_warning round={round_index + 1} error={exc}")

        round_stage_tracker.transition(
            "round_postprocessing",
            round_index=round_index + 1,
            active_workers=1,
        )
        strategy_memory = build_specialist_strategy_memory(
            current_diagnostic=self_diagnostics,
            recent_diagnostics=(
                strategy_memory_prior_diagnostics
                + recent_round_self_diagnostics(rounds)
            ),
            round_index=round_index + 1,
            near_dynamic_training=status.get("near_dynamic_kdj_training"),
            dynamic_training=status.get("dynamic_kdj_training"),
        )
        prefilter_info["strategy_memory"] = strategy_memory
        status["strategy_memory"] = strategy_memory
        selected_experiment = strategy_memory["selected_experiment"]
        log(
            f"round={round_index + 1} strategy_memory="
            f"{selected_experiment['key']} "
            f"action={selected_experiment['action']} "
            f"failures={','.join(strategy_memory['failure_hypotheses'])}"
        )

        round_record = {
            "round": round_index + 1,
            "phase": phase,
            "step": step,
            "generated_config_count": generated_config_count,
            "config_count": len(refined_configs),
            "prefilter": prefilter_info,
            "improved": improved,
            "best": round_best,
            "top_results": persisted_round_candidate_summaries(
                summaries,
                decision_round_best=decision_round_best,
            ),
            "control_experiments": control_summaries,
        }
        status["updated_at"] = datetime.now().isoformat(timespec="seconds")
        status["best"] = strip_target_results(best_summary) if best_summary else None
        status["search_base"] = search_base_info
        status["prefilter"]["completed_latest"] = prefilter_info
        if observability_only:
            round_stage_tracker.transition(
                "persistence_skipped_observability_only",
                round_index=round_index + 1,
                active_workers=0,
                generated_config_count=generated_config_count,
                selected_config_count=len(refined_configs),
            )
            status["persistence_policy"]["skipped_rounds"].append(round_index + 1)
            log(
                f"round={round_index + 1} persistence=skipped "
                "reason=observability_only"
            )
        else:
            round_stage_tracker.transition(
                "persistence_and_prediction_refresh",
                round_index=round_index + 1,
                active_workers=1,
                generated_config_count=generated_config_count,
                selected_config_count=len(refined_configs),
            )
            with get_connection() as conn:
                ensure_training_round_results_schema(conn)
                upsert_training_round_result(conn, run_id=run_id, round_info=round_record, status=status)
                upsert_training_line_round_result(
                    conn,
                    training_line_round_payload(
                        run_id=run_id,
                        round_index=round_index + 1,
                        line_key=STATIC_100_LINE_KEY,
                        line_label=STATIC_100_LINE_LABEL,
                        line_kind="static_training",
                        policy_key=str(round_best.get("config_hash") or ""),
                        policy_params={"config_hash": round_best.get("config_hash")},
                        summary=round_best,
                        status=status,
                        training_payload={"source": "training_supervisor_round_best"},
                    ),
                )
                if dynamic_line_payload is not None:
                    upsert_training_line_round_result(conn, dynamic_line_payload)
                if near_dynamic_line_payload is not None:
                    upsert_training_line_round_result(conn, near_dynamic_line_payload)
                if should_checkpoint_supervisor_best(
                    best_summary,
                    round_index=round_index + 1,
                    improved=improved,
                ):
                    upsert_training_supervisor_best(
                        conn,
                        run_id=run_id,
                        round_index=round_index + 1,
                        best_summary=best_summary,
                        status=status,
                    )
                if enable_target_weight_inversion_advisor and inversion_rows:
                    ensure_training_target_weight_inversions_schema(conn)
                    for inversion in inversion_rows:
                        upsert_training_target_weight_inversion(
                            conn,
                            {
                                **inversion,
                                "run_id": run_id,
                                "round_index": round_index + 1,
                                "aggregate": inversion_aggregate,
                                "prefilter": target_weight_inversion_latest or {},
                            },
                        )
                if best_summary:
                    try:
                        status["next_candidates"] = refresh_training_prediction_lines_current(
                            conn,
                            run_id=run_id,
                            top_n=top_n,
                            ranked_universe=ranked_universe,
                            dynamic_policy=dynamic_kdj_best_policy,
                            near_dynamic_policy=near_dynamic_kdj_latest_policy or near_dynamic_kdj_best_policy,
                            near_dynamic_sealed=False,
                        )
                        if near_dynamic_kdj_latest_policy is not None or near_dynamic_kdj_best_policy is not None:
                            try:
                                status["near_dynamic_kdj_training"]["report"] = write_near_dynamic_line_report(conn)
                            except Exception as report_exc:  # pragma: no cover - reporting must not stop training.
                                status["near_dynamic_kdj_training"]["report"] = {
                                    "status": "failed",
                                    "error": str(report_exc),
                                }
                    except Exception as exc:  # pragma: no cover - candidate refresh must not stop training.
                        status["next_candidates"] = {"status": "failed", "error": str(exc)}
                        log(f"next_candidates_warning round={round_index + 1} error={exc}")
        round_stage_tracker.complete(round_index=round_index + 1)
        rounds.append(compact_round_info(round_record))
        publish_status_snapshot(status_path, status, event_url=resolved_event_url, write_json=write_status_json)
        write_report(report_path, status)
        round_index += 1
        state.values.update(
            {
                "best_config": best_config,
                "best_summary": best_summary,
                "dynamic_kdj_best_policy": dynamic_kdj_best_policy,
                "dynamic_kdj_best_training_summary": dynamic_kdj_best_training_summary,
                "leaderboard": leaderboard,
                "near_dynamic_kdj_best_policy": near_dynamic_kdj_best_policy,
                "near_dynamic_kdj_best_training_summary": near_dynamic_kdj_best_training_summary,
                "near_dynamic_kdj_latest_policy": near_dynamic_kdj_latest_policy,
                "near_dynamic_kdj_seal_reason": near_dynamic_kdj_seal_reason,
                "near_dynamic_kdj_sealed": near_dynamic_kdj_sealed,
                "near_dynamic_kdj_stagnation_rounds": near_dynamic_kdj_stagnation_rounds,
                "near_miss_inversion_configs": near_miss_inversion_configs,
                "near_miss_inversion_latest": near_miss_inversion_latest,
                "probability_focus_config": probability_focus_config,
                "probability_focus_hash": probability_focus_hash,
                "probability_focus_remaining": probability_focus_remaining,
                "probability_focus_score": probability_focus_score,
                "probability_focus_source": probability_focus_source,
                "round_index": round_index,
                "rounds": rounds,
                "search_base_config": search_base_config,
                "status": status,
                "target_weight_inversion_configs": target_weight_inversion_configs,
                "target_weight_inversion_latest": target_weight_inversion_latest,
            }
        )
        state.completed_rounds = round_index
        return RuntimeRoundOutcome(request=request, result=status)


@dataclass
class ProductionTrainingSession:
    state: RuntimeTrainingState
    executor: ProductionRuntimeRoundExecutor = field(
        default_factory=ProductionRuntimeRoundExecutor
    )
    _finished: bool = False

    def next_request(self) -> RuntimeRoundRequest | None:
        if self._finished:
            return None
        values = self.state.values
        round_index = int(values["round_index"])
        if not should_continue_training(round_index, values["deadline"]) or (
            values["max_rounds"] is not None
            and round_index >= max(0, int(values["max_rounds"]))
        ):
            self.finish()
            return None
        status = values["status"]
        return RuntimeRoundRequest(
            TrainingRoundRequest(
                run_id=str(values["run_id"]),
                round_index=round_index + 1,
                as_of_issue=str(values["as_of_issue_value"]),
                history_fingerprint=str(values["history_fingerprint_value"]),
                objective_policy_version=str(status["objective_policy_version"]),
                objective_policy_hash=str(status["objective_policy_hash"]),
                candidate_budget=int(values["max_configs_per_round"]),
                random_seed=round_index + 1,
            )
        )

    def finish(
        self,
        *,
        status: str = "completed",
        error: Exception | None = None,
    ) -> dict:
        values = self.state.values
        runtime_status = values["status"]
        if self._finished:
            return runtime_status
        self._finished = True
        runtime_status["status"] = status
        if error is not None:
            runtime_status["error_message"] = str(error)
            round_stage_tracker = values.get("round_stage_tracker")
            if round_stage_tracker is not None:
                round_stage_tracker.fail(error=error)
        pool = values.get("pool")
        if pool is not None:
            pool.close()
            pool.join()
            values["pool"] = None
        runtime_status["updated_at"] = datetime.now().isoformat(timespec="seconds")
        best_summary = values.get("best_summary")
        runtime_status["best"] = strip_target_results(best_summary) if best_summary else None
        publish_status_snapshot(
            values["status_path"],
            runtime_status,
            event_url=values["resolved_event_url"],
            write_json=values["write_status_json"],
        )
        write_report(values["report_path"], runtime_status)
        log(
            f"finished status={runtime_status['status']} "
            f"status_path={values['status_path']} report_path={values['report_path']}"
        )
        return runtime_status


def build_production_training_session(
    *,
    duration_hours: float,
    train_window: int,
    eval_window: int,
    top_n: int,
    as_of_issue: str | None,
    workers: int | None,
    train_mode: str,
    history_scope: HistoryScope,
    regime_years: int,
    output_dir: Path,
    progress_interval: int,
    max_configs_per_round: int,
    memory_budget_gb: int,
    event_url: str | None = None,
    write_status_json: bool = False,
    enable_weight_kdj_advisor: bool = False,
    enable_ridge_kdj_advisor: bool = False,
    enable_neural_kdj_advisor: bool = False,
    enable_target_weight_inversion_advisor: bool = True,
    weight_kdj_run_id: str | None = None,
    weight_kdj_limit: int = 1000,
    weight_kdj_budget_share: float = DEFAULT_WEIGHT_KDJ_BUDGET_SHARE,
    weight_kdj_min_objective_delta: float = DEFAULT_WEIGHT_KDJ_MIN_OBJECTIVE_DELTA,
    weight_kdj_min_abs_offset: float = DEFAULT_WEIGHT_KDJ_MIN_ABS_OFFSET,
    weight_kdj_slope_window: int = DEFAULT_WEIGHT_KDJ_SLOPE_WINDOW,
    weight_kdj_neutral_band: float = DEFAULT_WEIGHT_KDJ_NEUTRAL_BAND,
    ridge_kdj_budget_share: float = DEFAULT_RIDGE_KDJ_BUDGET_SHARE,
    ridge_kdj_alpha: float = DEFAULT_RIDGE_KDJ_ALPHA,
    ridge_kdj_min_confidence: float = DEFAULT_RIDGE_KDJ_MIN_CONFIDENCE,
    ridge_kdj_min_train_rows: int = DEFAULT_RIDGE_KDJ_MIN_TRAIN_ROWS,
    ridge_kdj_min_validation_rows: int = DEFAULT_RIDGE_KDJ_MIN_VALIDATION_ROWS,
    neural_kdj_budget_share: float = DEFAULT_NEURAL_KDJ_BUDGET_SHARE,
    neural_kdj_min_confidence: float = DEFAULT_NEURAL_KDJ_MIN_CONFIDENCE,
    neural_kdj_seed: int = DEFAULT_NEURAL_KDJ_SEED,
    neural_kdj_hidden_units: int = DEFAULT_NEURAL_KDJ_HIDDEN_UNITS,
    neural_kdj_epochs: int = DEFAULT_NEURAL_KDJ_EPOCHS,
    target_weight_inversion_budget_share: float = DEFAULT_TARGET_WEIGHT_INVERSION_BUDGET_SHARE,
    target_weight_inversion_max_candidates: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_CANDIDATES,
    target_weight_inversion_max_targets: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_TARGETS,
    target_weight_inversion_max_deltas_per_target: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_DELTAS_PER_TARGET,
    max_rounds: int | None = None,
    observability_only: bool = False,
) -> ProductionTrainingSession:
    if observability_only and (max_rounds is None or max_rounds < 1):
        raise ValueError("observability-only mode requires --max-rounds >= 1")
    apply_observability_only_database_guard(observability_only)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    started_at = datetime.now()
    deadline = resolve_training_deadline(started_at, duration_hours)
    resolved_event_url = None if observability_only else training_event_url(event_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / f"training-supervisor-{run_id}.json"
    report_path = output_dir / f"training-supervisor-{run_id}.md"

    with get_connection() as conn:
        if not observability_only:
            ensure_training_round_results_schema(conn)
            ensure_training_supervisor_best_schema(conn)
        selection = select_history(conn, scope=history_scope, as_of_issue=as_of_issue, regime_years=regime_years)
        history_table_fields = load_ssq_history_column_names(conn)
        training_history = selection.dated_history
        prediction_input_boundary = build_prediction_input_boundary(
            history=training_history,
            training_fields=DRAW_PREDICTION_HISTORY_FIELDS,
            available_history_fields=history_table_fields,
        )
        enforce_prediction_input_boundary(prediction_input_boundary)
        log(
            "prediction_input_boundary="
            f"{prediction_input_boundary['status']} "
            f"fields={prediction_input_boundary['training_fields']} "
            f"market_selected={prediction_input_boundary['selected_market_aggregate_fields']} "
            f"ticket_distribution_observed={prediction_input_boundary['ticket_distribution_observed']}"
        )
        universe = load_red_combination_universe(conn)

    worker_count = normalize_worker_count(workers)
    as_of_issue_value = history_issue(training_history[-1])
    history_fingerprint_value = fingerprint_history(training_history)
    log(
        f"run_id={run_id} building static universe rows={len(universe)} workers={worker_count} "
        f"memory_budget_gb={memory_budget_gb}"
    )
    ranked_universe = build_ranked_universe(universe)
    matrix_cache_info = dict(getattr(ranked_universe, "cache_info", {}))
    log(
        "static_matrix_ready="
        f"backend={matrix_cache_info.get('backend', 'unknown')} "
        f"cache_hit={matrix_cache_info.get('cache_hit')} "
        f"rows={len(ranked_universe)} "
        f"elapsed={matrix_cache_info.get('build_seconds')}s"
    )
    prior_leaderboard = load_db_supervisor_candidates(
        as_of_issue=as_of_issue_value,
        history_fingerprint_value=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        eval_window=eval_window,
        top_n=top_n,
        universe_size=len(ranked_universe),
        ensure_schema=not observability_only,
    )
    if not prior_leaderboard:
        prior_leaderboard = load_prior_supervisor_candidates(
            output_dir=output_dir,
            current_status_path=status_path,
            as_of_issue=as_of_issue_value,
            history_fingerprint_value=history_fingerprint_value,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            universe_size=len(ranked_universe),
        )
    if prior_leaderboard:
        log(
            "seeded_prior_best="
            f"top100={prior_leaderboard[0]['top_100_hits']} "
            f"top1000={prior_leaderboard[0]['top_1000_hits']} "
            f"top10000={prior_leaderboard[0]['top_10000_hits']} "
            f"run_key={prior_leaderboard[0]['run_key']}"
        )
    db_carryover_configs = load_db_supervisor_carryover_configs(
        current_as_of_issue=as_of_issue_value,
        current_history_fingerprint=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        eval_window=eval_window,
        top_n=top_n,
        universe_size=len(ranked_universe),
        ensure_schema=not observability_only,
    )
    status_carryover_configs = load_prior_supervisor_carryover_configs(
        output_dir=output_dir,
        current_status_path=status_path,
        current_as_of_issue=as_of_issue_value,
        current_history_fingerprint=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        eval_window=eval_window,
        top_n=top_n,
        universe_size=len(ranked_universe),
    )
    same_history_seed_configs = config_candidates_from_summaries(prior_leaderboard, limit=16)
    carryover_configs = merge_config_candidates(
        same_history_seed_configs,
        db_carryover_configs,
        status_carryover_configs,
        limit=16,
    )
    # Historical summaries predate the disjoint search/frozen split. Keep their configs,
    # but never compare their full-window metrics against the new search-only metrics.
    prior_leaderboard = []
    with get_connection() as conn:
        navigation_records = load_training_round_navigation_records(
            conn,
            as_of_issue=as_of_issue_value,
            history_fingerprint=history_fingerprint_value,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            limit=80,
        )
        sequential_null_ledger = load_training_sequential_null_ledger(
            conn,
            as_of_issue=as_of_issue_value,
            history_fingerprint=history_fingerprint_value,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            current_run_id=run_id,
        )
    log(
        "sequential_null_ledger="
        f"rounds={sequential_null_ledger['observed_diagnostic_round_count']}/"
        f"{sequential_null_ledger['total_round_count']} "
        f"candidate_tests={sequential_null_ledger['observed_candidate_hypothesis_count']} "
        f"family={sequential_null_ledger['observed_familywise_hypothesis_count']} "
        f"legacy_uncounted={sequential_null_ledger['legacy_uncounted_round_count']}"
    )
    strategy_memory_prior_diagnostics, strategy_memory_continuity_info = (
        recover_strategy_memory_diagnostics(
            navigation_records,
            current_run_id=run_id,
            limit=8,
        )
    )
    guard_history, guard_continuity_info = recover_supervisor_guard_history(
        navigation_records,
        limit=80,
    )
    continuity_configs, continuity_recovery_info = recover_holdout_isolated_continuity_configs(
        navigation_records,
        limit=4,
    )
    pool = create_worker_pool(worker_count, ranked_universe)

    carryover_summaries: list[dict] = []
    if carryover_configs:
        log(
            "seeded_carryover_configs="
            f"count={len(carryover_configs)} "
            f"hashes={bounded_unique_config_hashes(carryover_configs, limit=len(carryover_configs))}"
        )
        carryover_summaries = evaluate_configs(
            history=training_history,
            ranked_universe=ranked_universe,
            configs=carryover_configs,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            workers=worker_count,
            pool=pool,
            progress_interval=0,
            round_index=0,
            frozen_validation_window_value=frozen_validation_window(eval_window),
        )
        prior_leaderboard = merge_leaderboard([], carryover_summaries, limit=32)
        if carryover_summaries:
            log(
                "seeded_carryover_best="
                f"top100={carryover_summaries[0]['top_100_hits']} "
                f"top1000={carryover_summaries[0]['top_1000_hits']} "
                f"top10000={carryover_summaries[0]['top_10000_hits']} "
                f"run_key={carryover_summaries[0]['run_key']}"
            )

    best_summary: dict | None = prior_leaderboard[0] if prior_leaderboard else None
    best_config = FrequencyRankerConfig(**best_summary["config"]) if best_summary else FrequencyRankerConfig()
    continuity_summaries: list[dict] = []
    if continuity_configs:
        log(
            "seeded_supervisor_continuity_configs="
            f"count={len(continuity_configs)} "
            f"hashes={bounded_unique_config_hashes(continuity_configs, limit=len(continuity_configs))}"
        )
        continuity_summaries = evaluate_configs(
            history=training_history,
            ranked_universe=ranked_universe,
            configs=continuity_configs,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            workers=worker_count,
            pool=pool,
            progress_interval=0,
            round_index=0,
            frozen_validation_window_value=frozen_validation_window(eval_window),
        )
    continuity_seed, continuity_seed_info = select_holdout_isolated_continuity_seed(
        continuity_summaries,
        baseline=best_summary,
    )
    continuity_seed_info.update(continuity_recovery_info)
    search_base_config = (
        FrequencyRankerConfig(**continuity_seed["config"])
        if continuity_seed is not None
        else best_config
    )
    if continuity_seed is not None:
        log(
            "seeded_supervisor_continuity_search_base="
            f"config_hash={config_hash(search_base_config)} "
            "selection_basis=search_slice_revalidated "
            "frozen_validation_used=False"
        )
    dynamic_kdj_best_training_summary: dict | None = None
    dynamic_kdj_best_policy: dict | None = None
    near_dynamic_kdj_best_training_summary: dict | None = None
    near_dynamic_kdj_best_policy: dict | None = None
    near_dynamic_kdj_latest_policy: dict | None = None
    near_dynamic_kdj_stagnation_rounds = 0
    near_dynamic_kdj_sealed = False
    near_dynamic_kdj_seal_reason = ""
    leaderboard: list[dict] = merge_leaderboard(prior_leaderboard, continuity_summaries, limit=32)
    rounds: list[dict] = []
    if guard_history:
        log(
            "seeded_guard_continuity="
            f"stagnation={guard_continuity_info['stagnation_rounds']} "
            f"signatures={guard_continuity_info['unique_rank_signature_count']}/"
            f"{guard_continuity_info['rank_signature_count']} "
            f"source_runs={guard_continuity_info['source_run_ids']}"
        )
    target_weight_inversion_configs: tuple[FrequencyRankerConfig, ...] = ()
    target_weight_inversion_latest: dict | None = None
    near_miss_inversion_configs: tuple[FrequencyRankerConfig, ...] = ()
    near_miss_inversion_latest: dict | None = None
    probability_focus_config: FrequencyRankerConfig | None = None
    probability_focus_hash = ""
    probability_focus_source = ""
    probability_focus_score: tuple = ()
    probability_focus_remaining = 0
    weight_kdj_thresholds = {
        "min_objective_delta": weight_kdj_min_objective_delta,
        "min_abs_offset": weight_kdj_min_abs_offset,
        "slope_window": weight_kdj_slope_window,
        "neutral_band": weight_kdj_neutral_band,
    }
    ridge_kdj_params = {
        "step": DEFAULT_RIDGE_KDJ_STEP,
        "ridge_alpha": ridge_kdj_alpha,
    }
    ridge_kdj_thresholds = {
        "min_confidence": ridge_kdj_min_confidence,
        "min_train_rows": ridge_kdj_min_train_rows,
        "min_validation_rows": ridge_kdj_min_validation_rows,
    }
    neural_kdj_params = {
        "step": DEFAULT_NEURAL_KDJ_STEP,
        "seed": neural_kdj_seed,
        "hidden_units": neural_kdj_hidden_units,
        "epochs": neural_kdj_epochs,
        "model": "numpy_mlp_kdj_offset_v0",
    }
    neural_kdj_thresholds = {
        "min_confidence": neural_kdj_min_confidence,
    }
    status = {
        "run_id": run_id,
        "objective_policy_version": DEFAULT_OBJECTIVE_POLICY.version,
        "objective_policy_hash": DEFAULT_OBJECTIVE_POLICY.policy_hash,
        "started_at": started_at.isoformat(timespec="seconds"),
        "updated_at": started_at.isoformat(timespec="seconds"),
        "deadline": deadline.isoformat(timespec="seconds") if deadline else None,
        "run_mode": "continuous" if deadline is None else "timed",
        "execution_mode": "observability_only" if observability_only else "production",
        "persistence_policy": training_persistence_policy(observability_only),
        "round_execution_history": [],
        "status": "running",
        "pid": os.getpid(),
        "history_scope": selection.scope,
        "regime_years": selection.regime_years,
        "regime_start_date": selection.start_date.isoformat() if selection.start_date else "",
        "prediction_input_boundary": prediction_input_boundary,
        "train_mode": train_mode,
        "train_window": train_window,
        "eval_window": eval_window,
        "top_n": top_n,
        "workers": worker_count,
        "memory_budget_gb": memory_budget_gb,
        "legal_universe_size": len(universe),
        "ranked_universe_size": len(ranked_universe),
        "excluded_universe_count": max(0, len(universe) - len(ranked_universe)),
        "universe_size": len(ranked_universe),
        "matrix_backend": "NumPy 特征矩阵",
        "feature_matrix_cache": matrix_cache_info,
        "red5_rank_mode": "红5候选使用完整分数向量精排，不重复计算特征矩阵",
        "prefilter": {
            "mode": "light_prefilter",
            "description": "每轮先用最近100期每4期取1期做轻量预筛，正式指标仍来自完整精排",
            "latest": None,
            "completed_latest": None,
        },
        "weight_kdj_advisor": {
            "enabled": enable_weight_kdj_advisor,
            "signal_run_id": weight_kdj_run_id,
            "limit": weight_kdj_limit,
            "budget_share": weight_kdj_budget_share if enable_weight_kdj_advisor else 0.0,
            "thresholds": weight_kdj_thresholds,
            "latest": None,
        },
        "ridge_kdj_advisor": {
            "enabled": enable_ridge_kdj_advisor,
            "signal_run_id": weight_kdj_run_id,
            "limit": weight_kdj_limit,
            "budget_share": ridge_kdj_budget_share if enable_ridge_kdj_advisor else 0.0,
            "params": ridge_kdj_params,
            "thresholds": ridge_kdj_thresholds,
            "latest": None,
        },
        "neural_kdj_advisor": {
            "enabled": enable_neural_kdj_advisor,
            "signal_run_id": weight_kdj_run_id,
            "limit": weight_kdj_limit,
            "budget_share": neural_kdj_budget_share if enable_neural_kdj_advisor else 0.0,
            "params": neural_kdj_params,
            "thresholds": neural_kdj_thresholds,
            "latest": None,
        },
        "dynamic_kdj_training": {
            "enabled": True,
            "protocol": DYNAMIC_KDJ_TRAINING_PROTOCOL_VERSION,
            "line_key": DYNAMIC_KDJ_LINE_KEY,
            "latest": None,
            "best": None,
        },
        "near_dynamic_kdj_training": {
            "enabled": True,
            "protocol": NEAR_DYNAMIC_KDJ_TRAINING_PROTOCOL_VERSION,
            "line_key": NEAR_DYNAMIC_KDJ_LINE_KEY,
            "eval_window": NEAR_DYNAMIC_KDJ_EVAL_WINDOW,
            "train_mode": NEAR_DYNAMIC_KDJ_TRAIN_MODE,
            "continuous_training": True,
            "latest": None,
            "best": None,
            "sealed": False,
        },
        "target_weight_inversion_advisor": {
            "enabled": enable_target_weight_inversion_advisor,
            "budget_share": target_weight_inversion_budget_share if enable_target_weight_inversion_advisor else 0.0,
            "max_candidates": max(0, target_weight_inversion_max_candidates),
            "max_targets": max(0, target_weight_inversion_max_targets),
            "max_deltas_per_target": max(1, target_weight_inversion_max_deltas_per_target),
            "latest": target_weight_inversion_latest,
        },
        "near_miss_inversion_advisor": {
            "enabled": enable_target_weight_inversion_advisor,
            "stagnation_threshold": NEAR_MISS_INVERSION_STAGNATION_THRESHOLD,
            "latest": near_miss_inversion_latest,
        },
        "probability_focus": {
            "enabled": True,
            "hold_rounds": PROBABILITY_FOCUS_HOLD_ROUNDS,
            "latest": None,
        },
        "carryover_seed": {
            "mode": "cross_history_config_replay",
            "config_count": len(carryover_configs),
            "config_hashes": bounded_unique_config_hashes(carryover_configs, limit=len(carryover_configs) or 1),
            "evaluated_config_count": len(carryover_summaries),
            "best": strip_target_results(carryover_summaries[0]) if carryover_summaries else None,
        },
        "continuity_seed": {
            **continuity_seed_info,
            "config_hashes": bounded_unique_config_hashes(
                continuity_configs,
                limit=len(continuity_configs) or 1,
            ),
            "selected": strip_target_results(continuity_seed) if continuity_seed is not None else None,
        },
        "strategy_memory_continuity": strategy_memory_continuity_info,
        "sequential_null_ledger": sequential_null_ledger,
        "guard_continuity": guard_continuity_info,
        "qian_kun": qian_kun_distribution(selection.history),
        "next_candidates": None,
        "self_diagnostics": None,
        "strategy_memory": None,
        "rounds": rounds,
        "best": strip_target_results(best_summary) if best_summary else None,
        "search_base": {
            "source": "supervisor_continuity" if continuity_seed is not None else "initial_best",
            "changed": continuity_seed is not None,
            "previous_config_hash": config_hash(best_config) if continuity_seed is not None else "",
            "config_hash": config_hash(search_base_config),
            "config": config_dict(search_base_config),
        },
        "latest_progress": None,
        "round_execution": None,
        "status_path": str(status_path),
        "report_path": str(report_path),
    }

    def publish_progress(progress: dict) -> None:
        status["latest_progress"] = progress
        status["updated_at"] = progress["logged_at"]
        publish_status_snapshot(status_path, status, event_url=resolved_event_url, write_json=write_status_json)

    def publish_round_execution() -> None:
        status["updated_at"] = datetime.now().isoformat(timespec="seconds")
        publish_status_snapshot(
            status_path,
            status,
            event_url=resolved_event_url,
            write_json=write_status_json,
        )

    round_stage_tracker = RoundStageTracker(
        status=status,
        publish=publish_round_execution,
        log=log,
    )

    if not observability_only and should_checkpoint_supervisor_best(best_summary, round_index=0, improved=True):
        with get_connection() as conn:
            upsert_training_supervisor_best(
                conn,
                run_id=run_id,
                round_index=0,
                best_summary=best_summary,
                status=status,
            )
    publish_status_snapshot(status_path, status, event_url=resolved_event_url, write_json=write_status_json)

    round_index = 0
    values = dict(locals())
    values["round_index"] = round_index
    return ProductionTrainingSession(RuntimeTrainingState(values=values))


def iter_supervisor_rounds(
    *,
    duration_hours: float,
    train_window: int,
    eval_window: int,
    top_n: int,
    as_of_issue: str | None,
    workers: int | None,
    train_mode: str,
    history_scope: HistoryScope,
    regime_years: int,
    output_dir: Path,
    progress_interval: int,
    max_configs_per_round: int,
    memory_budget_gb: int,
    event_url: str | None = None,
    write_status_json: bool = False,
    enable_weight_kdj_advisor: bool = False,
    enable_ridge_kdj_advisor: bool = False,
    enable_neural_kdj_advisor: bool = False,
    enable_target_weight_inversion_advisor: bool = True,
    weight_kdj_run_id: str | None = None,
    weight_kdj_limit: int = 1000,
    weight_kdj_budget_share: float = DEFAULT_WEIGHT_KDJ_BUDGET_SHARE,
    weight_kdj_min_objective_delta: float = DEFAULT_WEIGHT_KDJ_MIN_OBJECTIVE_DELTA,
    weight_kdj_min_abs_offset: float = DEFAULT_WEIGHT_KDJ_MIN_ABS_OFFSET,
    weight_kdj_slope_window: int = DEFAULT_WEIGHT_KDJ_SLOPE_WINDOW,
    weight_kdj_neutral_band: float = DEFAULT_WEIGHT_KDJ_NEUTRAL_BAND,
    ridge_kdj_budget_share: float = DEFAULT_RIDGE_KDJ_BUDGET_SHARE,
    ridge_kdj_alpha: float = DEFAULT_RIDGE_KDJ_ALPHA,
    ridge_kdj_min_confidence: float = DEFAULT_RIDGE_KDJ_MIN_CONFIDENCE,
    ridge_kdj_min_train_rows: int = DEFAULT_RIDGE_KDJ_MIN_TRAIN_ROWS,
    ridge_kdj_min_validation_rows: int = DEFAULT_RIDGE_KDJ_MIN_VALIDATION_ROWS,
    neural_kdj_budget_share: float = DEFAULT_NEURAL_KDJ_BUDGET_SHARE,
    neural_kdj_min_confidence: float = DEFAULT_NEURAL_KDJ_MIN_CONFIDENCE,
    neural_kdj_seed: int = DEFAULT_NEURAL_KDJ_SEED,
    neural_kdj_hidden_units: int = DEFAULT_NEURAL_KDJ_HIDDEN_UNITS,
    neural_kdj_epochs: int = DEFAULT_NEURAL_KDJ_EPOCHS,
    target_weight_inversion_budget_share: float = DEFAULT_TARGET_WEIGHT_INVERSION_BUDGET_SHARE,
    target_weight_inversion_max_candidates: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_CANDIDATES,
    target_weight_inversion_max_targets: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_TARGETS,
    target_weight_inversion_max_deltas_per_target: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_DELTAS_PER_TARGET,
    max_rounds: int | None = None,
    observability_only: bool = False,
) -> Iterator[dict]:
    session = build_production_training_session(**locals())
    while request := session.next_request():
        outcome = session.executor.execute(request, session.state)
        yield outcome.result
    return session.finish()
