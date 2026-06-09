from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.providers.base import GeneratedContent


@dataclass(slots=True)
class StageMetric:
    name: str
    started_at: float
    runtime_seconds: float = 0.0
    status: str = "running"
    model_calls: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        token_input = sum(int(call.get("token_input") or 0) for call in self.model_calls)
        token_output = sum(int(call.get("token_output") or 0) for call in self.model_calls)
        estimated_cost = round(sum(float(call.get("estimated_cost") or 0) for call in self.model_calls), 6)
        return {
            "stage": self.name,
            "runtime_seconds": round(self.runtime_seconds, 3),
            "status": self.status,
            "model_calls": self.model_calls,
            "token_input": token_input,
            "token_output": token_output,
            "estimated_cost": estimated_cost,
        }


class JobRunMetrics:
    def __init__(self) -> None:
        self.started_at = time.perf_counter()
        self._stages: dict[str, StageMetric] = {}
        self._order: list[str] = []

    def start_stage(self, name: str) -> None:
        if name in self._stages and self._stages[name].status == "running":
            return
        self._stages[name] = StageMetric(name=name, started_at=time.perf_counter())
        self._order.append(name)

    def finish_stage(self, name: str, status: str = "completed") -> None:
        stage = self._stages.get(name)
        if stage is None:
            return
        stage.runtime_seconds = max(0.0, time.perf_counter() - stage.started_at)
        stage.status = status

    def fail_stage(self, name: str, error: str) -> None:
        stage = self._stages.get(name)
        if stage is None:
            self.start_stage(name)
            stage = self._stages[name]
        stage.runtime_seconds = max(0.0, time.perf_counter() - stage.started_at)
        stage.status = "failed"
        stage.model_calls.append({"error": error})

    def record_model_call(self, stage_name: str, generated: GeneratedContent | None) -> None:
        if generated is None:
            return
        if stage_name not in self._stages:
            self.start_stage(stage_name)
        usage = generated.usage
        self._stages[stage_name].model_calls.append(
            {
                "provider": generated.provider,
                "model": generated.model,
                "task_type": generated.task_type,
                "token_input": usage.token_input if usage else None,
                "token_output": usage.token_output if usage else None,
                "estimated_cost": usage.estimated_cost if usage else None,
            }
        )

    def artifacts(
        self,
        *,
        repair_pass_count: int,
        expansion_pass_count: int,
        final_word_count: int,
        final_quality_status: str,
        final_sanity_status: str,
    ) -> dict[str, dict[str, Any]]:
        stage_dicts = [self._stages[name].as_dict() for name in self._order if name in self._stages]
        total_runtime = round(time.perf_counter() - self.started_at, 3)
        total_cost = round(sum(float(stage.get("estimated_cost") or 0) for stage in stage_dicts), 6)
        total_input = sum(int(stage.get("token_input") or 0) for stage in stage_dicts)
        total_output = sum(int(stage.get("token_output") or 0) for stage in stage_dicts)
        slowest = sorted(stage_dicts, key=lambda item: item.get("runtime_seconds") or 0, reverse=True)[:5]
        model_usage = [
            {"stage": stage["stage"], **call}
            for stage in stage_dicts
            for call in stage.get("model_calls", [])
            if call.get("model") or call.get("provider")
        ]
        return {
            "job_run_metrics": {
                "total_runtime_seconds": total_runtime,
                "total_estimated_cost": total_cost,
                "token_input": total_input,
                "token_output": total_output,
                "repair_pass_count": repair_pass_count,
                "expansion_pass_count": expansion_pass_count,
                "final_word_count": final_word_count,
                "final_quality_status": final_quality_status,
                "final_sanity_status": final_sanity_status,
                "stages": stage_dicts,
            },
            "stage_timing_summary": {
                "total_runtime_seconds": total_runtime,
                "slowest_stages": slowest,
                "stages": [
                    {
                        "stage": stage["stage"],
                        "runtime_seconds": stage["runtime_seconds"],
                        "status": stage["status"],
                    }
                    for stage in stage_dicts
                ],
            },
            "model_cost_summary": {
                "total_estimated_cost": total_cost,
                "token_input": total_input,
                "token_output": total_output,
                "model_usage": model_usage,
            },
        }
