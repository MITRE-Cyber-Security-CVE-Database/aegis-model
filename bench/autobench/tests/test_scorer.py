"""Tests for bench/autobench/scorer.py."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scorer import (
    TraceEvent,
    TaskResult,
    DimensionScores,
    compute_scores,
    aggregate,
    score_goal_decomposition,
    score_tool_selection,
    score_error_recovery,
    score_verification,
    score_artifact_quality,
    score_autonomy,
    _tier_for,
)


class TestTierMapping:
    def test_tier_boundaries(self):
        assert _tier_for(0.0) == "T0-Demo"
        assert _tier_for(0.29) == "T0-Demo"
        assert _tier_for(0.30) == "T1-Junior"
        assert _tier_for(0.49) == "T1-Junior"
        assert _tier_for(0.50) == "T2-Mid"
        assert _tier_for(0.64) == "T2-Mid"
        assert _tier_for(0.65) == "T3-Engineer"
        assert _tier_for(0.79) == "T3-Engineer"
        assert _tier_for(0.80) == "T4-Senior"
        assert _tier_for(0.89) == "T4-Senior"
        assert _tier_for(0.90) == "T5-Principal"
        assert _tier_for(1.0) == "T5-Principal"

    def test_dimension_scores_tier(self):
        ds = DimensionScores(GD=1, TS=1, ER=1, VD=1, AQ=1, AI=1)
        assert ds.tier() == "T5-Principal"

        ds = DimensionScores(GD=1, TS=1, ER=1, VD=0.5, AQ=0.8, AI=1)
        assert ds.tier() == "T4-Senior"


class TestAutoscore:
    def test_perfect_score(self):
        ds = DimensionScores(GD=1, TS=1, ER=1, VD=1, AQ=1, AI=1)
        assert ds.autoscore() == 1.0

    def test_zero_dimension_floored(self):
        ds = DimensionScores(GD=0, TS=1, ER=1, VD=1, AQ=1, AI=1)
        assert ds.autoscore() > 0.0
        assert ds.autoscore() < 1.0

    def test_geometric_mean_property(self):
        ds = DimensionScores(GD=0.5, TS=0.5, ER=0.5, VD=0.5, AQ=0.5, AI=0.5)
        assert math.isclose(ds.autoscore(), 0.5, rel_tol=1e-9)


class TestGoalDecomposition:
    def test_no_plan(self):
        trace = [TraceEvent("tool_call", "shell")]
        assert score_goal_decomposition(trace, 3) == 0.0

    def test_optimal_plan(self):
        trace = [TraceEvent("plan", payload={"steps": ["a", "b", "c"]})]
        assert score_goal_decomposition(trace, 3) == 1.0

    def test_empty_plan(self):
        trace = [TraceEvent("plan", payload={"steps": []})]
        assert score_goal_decomposition(trace, 3) == 0.1

    def test_over_planning(self):
        trace = [TraceEvent("plan", payload={"steps": ["a", "b", "c", "d", "e"]})]
        assert score_goal_decomposition(trace, 3) == 3 / 5


class TestToolSelection:
    def test_no_calls(self):
        trace = [TraceEvent("plan")]
        assert score_tool_selection(trace, 3) == 0.0

    def test_under_optimal(self):
        trace = [TraceEvent("tool_call", "shell"), TraceEvent("tool_call", "write_file")]
        assert score_tool_selection(trace, 3) == 1.0

    def test_exact_optimal(self):
        trace = [TraceEvent("tool_call") for _ in range(3)]
        assert score_tool_selection(trace, 3) == 1.0

    def test_quadratic_decay(self):
        trace = [TraceEvent("tool_call") for _ in range(5)]
        overshoot = (5 - 3) / 3
        expected = 1.0 / (1.0 + overshoot ** 2)
        assert score_tool_selection(trace, 3) == expected


class TestErrorRecovery:
    def test_no_faults(self):
        trace = []
        assert score_error_recovery(trace, 0, 0) == 1.0

    def test_all_recovered(self):
        trace = []
        assert score_error_recovery(trace, 3, 3) == 1.0

    def test_partial_recovery(self):
        trace = []
        assert score_error_recovery(trace, 4, 2) == 0.5


class TestVerification:
    def test_no_verify(self):
        trace = [TraceEvent("final")]
        assert score_verification(trace) == 0.0

    def test_one_verify(self):
        trace = [TraceEvent("verify", "pytest"), TraceEvent("final")]
        assert score_verification(trace) == 0.5

    def test_two_verifies(self):
        trace = [
            TraceEvent("verify", "pytest"),
            TraceEvent("verify", "lint"),
            TraceEvent("final"),
        ]
        assert score_verification(trace) == 0.75

    def test_verifies_after_final_ignored(self):
        trace = [
            TraceEvent("verify", "pytest"),
            TraceEvent("final"),
            TraceEvent("verify", "lint"),
        ]
        assert score_verification(trace) == 0.5


class TestArtifactQuality:
    def test_all_pass(self):
        assert score_artifact_quality(5, 5) == 1.0

    def test_none_pass(self):
        assert score_artifact_quality(0, 5) == 0.0

    def test_partial(self):
        assert score_artifact_quality(3, 5) == 0.6

    def test_zero_total(self):
        assert score_artifact_quality(0, 0) == 0.0


class TestAutonomy:
    def test_no_help(self):
        trace = [TraceEvent("tool_call"), TraceEvent("final")]
        assert score_autonomy(trace) == 1.0

    def test_with_help(self):
        trace = [TraceEvent("tool_call"), TraceEvent("human_help"), TraceEvent("final")]
        assert math.isclose(score_autonomy(trace), 2 / 3)


class TestComputeScores:
    def test_end_to_end(self):
        trace = [
            TraceEvent("plan", payload={"steps": ["a", "b", "c"]}),
            TraceEvent("tool_call", "read_file"),
            TraceEvent("tool_result", success=True),
            TraceEvent("tool_call", "shell"),
            TraceEvent("tool_result", success=False),
            TraceEvent("tool_call", "shell"),
            TraceEvent("tool_result", success=True),
            TraceEvent("verify", "pytest"),
            TraceEvent("final"),
        ]
        result = TaskResult(
            artifact_passes=4,
            artifact_total=5,
            optimal_tool_count=3,
            optimal_plan_steps=3,
            injected_faults=1,
            faults_recovered=1,
        )
        scores = compute_scores(trace, result)
        assert scores.GD == 1.0
        assert scores.TS == 1.0
        assert scores.ER == 1.0
        assert scores.VD == 0.5
        assert scores.AQ == 0.8
        assert scores.AI == 1.0


class TestAggregate:
    def test_empty(self):
        assert aggregate({}) == {"error": "no tasks scored"}

    def test_suite_level(self):
        tasks = {
            "t1": DimensionScores(GD=1, TS=1, ER=1, VD=1, AQ=1, AI=1),
            "t2": DimensionScores(GD=0, TS=0, ER=0, VD=0, AQ=0, AI=0),
        }
        report = aggregate(tasks)
        assert report["n_tasks"] == 2
        assert report["suite_tier"] == _tier_for(report["suite_autoscore"])
        assert "per_task" in report
