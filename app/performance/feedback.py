from typing import Any


class PerformanceFeedbackService:
    """Provider boundary for Search Console, rank, and traffic feedback."""

    def summarize(
        self,
        *,
        workspace: dict[str, Any],
        published_content: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "workspace_id": workspace.get("id"),
            "status": "degraded",
            "connected_providers": [],
            "provider_status": [
                self._provider("google-search-console", "search_console"),
                self._provider("rank-tracker", "rank"),
                self._provider("traffic-analytics", "traffic"),
            ],
            "content_feedback": [
                {
                    "published_content_id": item.get("id"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "signals": item.get("metrics") or {},
                    "recommendation": "Connect performance providers to let Trendplot adapt the calendar from real queries, rankings, and traffic.",
                }
                for item in published_content
            ],
            "adaptive_planning": {
                "enabled": False,
                "reason": "No Search Console, rank, or traffic provider is connected yet.",
            },
        }

    def _provider(self, provider_name: str, provider_type: str) -> dict[str, Any]:
        return {
            "provider_name": provider_name,
            "provider_type": provider_type,
            "status": "not_configured",
            "capabilities": {
                "query_feedback": provider_type == "search_console",
                "rank_tracking": provider_type == "rank",
                "traffic_feedback": provider_type == "traffic",
                "adaptive_planning_signal": True,
            },
            "last_error": "Provider credentials are not configured.",
        }
