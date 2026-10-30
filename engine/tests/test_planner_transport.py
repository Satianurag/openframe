"""Bounded public planner request budgets."""
from unittest import TestCase
from engine.planner import MAX_BUDGET_SECONDS, normalize_plan_request


class PlannerTransport(TestCase):
    request = {"prompt": "A dark desk lamp gradually turns on at dusk.", "target_duration": 15, "episodes": 1, "provider": "local"}

    def test_budget_scales_without_accepting_caller_override(self):
        short = normalize_plan_request({**self.request, "budget_seconds": 1})
        long = normalize_plan_request({**self.request, "target_duration": 300, "episodes": 4})
        self.assertEqual(short["budget_seconds"], 660)
        self.assertEqual(long["budget_seconds"], MAX_BUDGET_SECONDS)
        self.assertEqual(long["episodes"], 4)
        self.assertEqual(long["target_duration"], 300)
