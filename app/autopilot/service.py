from typing import Any, Awaitable, Callable
from uuid import uuid4

from app.config import Settings
from app.ai_opportunity_ideation import AIOpportunityIdeationService
from app.ai_opportunity_ideation.recommendations import group_recommendations, recommendation_summary
from app.connectors.wordpress import TrendplotConnectorContract, TrendplotWordPressConnectorClient
from app.niche_intelligence import NicheIntelligenceService
from app.performance import PerformanceFeedbackService
from app.planning import ContentCalendarEngine
from app.reassessment import ReassessmentService
from app.repositories import Repositories
from app.services.jobs import GenerateArticleCommand, JobService
from app.website_analysis import AnalyzeWebsiteCommand, WebsiteAnalysisService

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


class AutopilotService:
    def __init__(
        self,
        *,
        settings: Settings,
        repositories: Repositories,
        website_analysis: WebsiteAnalysisService,
        job_service: JobService,
    ) -> None:
        self.settings = settings
        self.repositories = repositories
        self.website_analysis = website_analysis
        self.job_service = job_service
        self.calendar = ContentCalendarEngine()
        self.niche_intelligence = NicheIntelligenceService()
        self.reassessment = ReassessmentService()
        self.performance = PerformanceFeedbackService()
        self.connector_contract = TrendplotConnectorContract()
        content_provider = getattr(getattr(job_service, "registry", None), "content_generation", None)
        openai_client = getattr(content_provider, "client", None)
        self.ai_opportunity_ideation = AIOpportunityIdeationService(
            settings=settings,
            repositories=repositories,
            openai_client=openai_client,
        )

    async def create_workspace(
        self,
        *,
        website_url: str,
        name: str = "",
        competitors: list[str] | None = None,
        mode: str = "manual_review",
        cadence: str = "weekly",
        user_context: str = "",
    ) -> dict[str, Any]:
        workspace = await self.repositories.autopilot_workspaces.create(
            website_url=website_url,
            name=name,
            mode=_safe_mode(mode),
            cadence=_safe_cadence(cadence),
            user_context=user_context,
            settings={"competitors": competitors or [], "product_name": "", "product_url": website_url},
        )
        await self._refresh_connection_status(workspace["id"])
        await self._refresh_provider_status(workspace["id"])
        await self.repositories.approval_events.create(
            workspace_id=workspace["id"],
            event_type="workspace_created",
            notes="Trendplot Workspace created.",
            metadata={"website_url": website_url, "competitors": competitors or []},
        )
        return await self.get_workspace(workspace["id"])

    async def merge_workspace_competitors(
        self,
        workspace_id: str,
        competitor_urls: list[str],
    ) -> list[str]:
        """Merge operator-provided competitor URLs into workspace settings."""
        incoming = [str(item).strip() for item in competitor_urls if str(item).strip()]
        workspace = await self._workspace(workspace_id)
        settings = dict(workspace.get("settings") or {}) if isinstance(workspace.get("settings"), dict) else {}
        existing = [str(item).strip() for item in settings.get("competitors", []) if str(item).strip()]
        if not incoming:
            return existing
        merged = _merge_competitor_url_lists(existing, incoming)
        if merged != existing:
            settings["competitors"] = merged
            await self.repositories.autopilot_workspaces.update(workspace_id, {"settings": settings})
        return merged

    async def list_workspaces(self) -> list[dict[str, Any]]:
        return await self.repositories.autopilot_workspaces.list_recent(50)

    async def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        workspace = await self._workspace(workspace_id)
        latest_understanding = await self.repositories.site_understanding.latest_for_workspace(workspace_id)
        latest_plan = await self.repositories.content_plans.latest_for_workspace(workspace_id)
        plan_items = await self.repositories.content_plan_items.list_for_plan(latest_plan["id"]) if latest_plan else []
        published = await self.repositories.published_content.list_for_workspace(workspace_id, 25)
        reassessment = await self.repositories.reassessment_runs.latest_for_workspace(workspace_id)
        connections = await self.repositories.workspace_connections.list_for_workspace(workspace_id)
        provider_status = await self.repositories.provider_status.list_for_workspace(workspace_id)
        approvals = await self.repositories.approval_events.list_for_workspace(workspace_id, 20)
        niche_profile = await self.repositories.workspace_niche_profiles.get(workspace_id)
        recommendations = await self.repositories.opportunity_recommendations.list_for_workspace(workspace_id, limit=120)
        return {
            "workspace": workspace,
            "site_understanding": latest_understanding,
            "niche_profile": niche_profile,
            "content_plan": latest_plan,
            "calendar_items": plan_items,
            "opportunity_recommendations": recommendations,
            "opportunity_intelligence": {
                "recommendations": recommendations,
                "groups": group_recommendations(recommendations),
                "summary": recommendation_summary(recommendations),
            },
            "published_content": published,
            "reassessment": reassessment,
            "connections": connections,
            "provider_status": provider_status,
            "approval_events": approvals,
            "status_summary": _status_summary(workspace, latest_understanding, latest_plan, plan_items, [], published),
        }

    async def analyze_workspace(
        self,
        workspace_id: str,
        *,
        max_pages_per_site: int = 3,
        progress_callback: ProgressCallback | None = None,
        provided_competitor_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        del provided_competitor_urls
        if not self.settings.ai_opportunity_ideation_enabled:
            raise ValueError("AI opportunity ideation must be enabled (AI_OPPORTUNITY_IDEATION_ENABLED=true).")
        return await self._analyze_workspace_product(
            workspace_id,
            max_pages_per_site=max_pages_per_site,
            progress_callback=progress_callback,
        )

    async def _analyze_workspace_product(
        self,
        workspace_id: str,
        *,
        max_pages_per_site: int = 3,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Website analysis + AI opportunity ideation → recommendations queue."""
        workspace = await self._workspace(workspace_id)
        await _emit_progress(progress_callback, {"step": "website_crawl", "message": "Crawling website pages"})
        prefetched_website = await self.website_analysis.crawl_website_for_discovery(
            website_url=str(workspace.get("website_url") or ""),
            max_pages_per_site=max_pages_per_site,
            progress_callback=progress_callback,
        )
        await self.website_analysis.sync_content_inventory(workspace_id, prefetched_website)

        await _emit_progress(progress_callback, {"step": "website_analysis", "message": "Analyzing website content"})
        analysis = await self.website_analysis.create_analysis_job(
            AnalyzeWebsiteCommand(
                website_url=workspace["website_url"],
                competitor_urls=[],
                max_pages_per_site=max_pages_per_site,
                vertical="auto",
                workspace_id=workspace_id,
                progress_callback=progress_callback,
                prefetched_website=prefetched_website,
            )
        )
        analysis_job = analysis.get("analysis_job") or {}
        analysis_job_id = str(analysis_job.get("id") or "")
        snapshot = _site_understanding_snapshot(analysis, workspace)
        understanding = await self.repositories.site_understanding.create(workspace_id, snapshot)
        niche_profile = await self.refresh_niche_profile(
            workspace_id,
            understanding=understanding,
            competitor_snapshots=[],
            create_event=False,
        )
        await _emit_progress(
            progress_callback,
            {"step": "niche_intelligence", "status": "succeeded", "message": "Niche profile refreshed."},
        )

        await _emit_progress(
            progress_callback,
            {"step": "ai_opportunity_ideation", "message": "Generating AI article opportunities"},
        )
        ideation_result = await self._run_ai_opportunity_ideation(workspace_id)
        ideation_opportunities = ideation_result.get("opportunities") or []
        await _emit_progress(
            progress_callback,
            {
                "step": "ai_opportunity_ideation",
                "status": _site_first_progress_status(ideation_result, "ai_opportunity_ideation"),
                "message": _site_first_progress_message(
                    ideation_result,
                    "ai_opportunity_ideation",
                    ideation_opportunities,
                    [],
                ),
                "details": ideation_result.get("metrics") or {},
            },
        )

        await _emit_progress(
            progress_callback,
            {"step": "opportunity_ranking", "message": "Saving AI recommendations"},
        )
        opportunity_intelligence = await self._persist_ideation_recommendations(
            workspace_id,
            ideation_opportunities,
            analysis_job_id=analysis_job_id,
        )
        created = opportunity_intelligence.get("recommendations") or []

        await _emit_progress(
            progress_callback,
            {
                "step": "opportunity_ranking",
                "status": "succeeded",
                "message": f"Saved {len(created)} AI recommendations",
                "details": {"recommendations_ranked": len(created)},
            },
        )

        await self.repositories.autopilot_workspaces.update(
            workspace_id,
            {"status": "analyzed", "last_analysis_job_id": analysis_job_id},
        )
        try:
            page_count = len(await self.repositories.analysis_pages.list_for_job(analysis_job_id))
        except Exception:
            page_count = 0

        return {
            "workspace": await self.repositories.autopilot_workspaces.get(workspace_id),
            "analysis": analysis,
            "site_understanding": understanding,
            "strategy_profile": analysis.get("strategy_profile")
            or (understanding.get("source") or {}).get("strategy_profile")
            or {},
            "niche_profile": niche_profile,
            "opportunity_intelligence": opportunity_intelligence,
            "analysis_page_count": page_count,
            "low_content_warning": None,
            "ai_opportunity_ideation": ideation_result,
        }

    async def load_saved_website_crawl(
        self,
        workspace_id: str,
    ) -> dict[str, Any] | None:
        workspace = await self._workspace(workspace_id)
        job_id = str(workspace.get("last_analysis_job_id") or "")
        if not job_id:
            return None
        rows = await self.repositories.analysis_pages.list_for_job(job_id)
        website_rows = [row for row in rows if str(row.get("source_type") or "") == "website"]
        if not website_rows:
            return None
        pages = [_analysis_page_row_to_crawl_page(row) for row in website_rows]
        return {"url": str(workspace.get("website_url") or ""), "pages": pages}

    async def _persist_ideation_recommendations(
        self,
        workspace_id: str,
        ideation_opportunities: list[dict[str, Any]],
        *,
        analysis_job_id: str | None = None,
    ) -> dict[str, Any]:
        from app.ai_opportunity_ideation.recommendations import ideation_opportunities_to_recommendation_rows

        recommendation_rows = ideation_opportunities_to_recommendation_rows(
            ideation_opportunities,
            analysis_job_id=analysis_job_id,
        )
        created = await self.repositories.opportunity_recommendations.replace_for_workspace(
            workspace_id,
            recommendation_rows,
        )
        grouped = group_recommendations(created)
        summary = recommendation_summary(created)
        summary["ideation_opportunities_generated"] = len(ideation_opportunities)
        return {"recommendations": created, "groups": grouped, "summary": summary}

    async def rerun_recommendations(
        self,
        workspace_id: str,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        return await self._rerun_ideation_recommendations(workspace_id, progress_callback=progress_callback)

    async def _rerun_ideation_recommendations(
        self,
        workspace_id: str,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Re-run AI opportunity ideation and replace workspace recommendations (no OI merge)."""
        workspace = await self._workspace(workspace_id)
        if not workspace.get("last_analysis_job_id"):
            raise ValueError("Website analysis is not complete.")
        understanding = await self.repositories.site_understanding.latest_for_workspace(workspace_id)
        if not understanding:
            raise ValueError("Website analysis is not complete.")

        analysis_job_id = str(workspace.get("last_analysis_job_id") or "")

        await _emit_progress(
            progress_callback,
            {"step": "ai_opportunity_ideation", "message": "Re-generating AI article opportunities"},
        )
        ideation_result = await self._run_ai_opportunity_ideation(workspace_id, force_refresh=True)
        ideation_opportunities = ideation_result.get("opportunities") or []
        await _emit_progress(
            progress_callback,
            {
                "step": "ai_opportunity_ideation",
                "status": _site_first_progress_status(ideation_result, "ai_opportunity_ideation"),
                "message": _site_first_progress_message(
                    ideation_result,
                    "ai_opportunity_ideation",
                    ideation_opportunities,
                    [],
                ),
                "details": ideation_result.get("metrics") or {},
            },
        )

        await _emit_progress(
            progress_callback,
            {"step": "opportunity_ranking", "message": "Saving AI recommendations"},
        )
        opportunity_intelligence = await self._persist_ideation_recommendations(
            workspace_id,
            ideation_opportunities,
            analysis_job_id=analysis_job_id,
        )
        await _emit_progress(
            progress_callback,
            {
                "step": "opportunity_ranking",
                "status": "succeeded",
                "message": f"Saved {len(opportunity_intelligence.get('recommendations') or [])} AI recommendations",
                "details": {
                    "recommendations_ranked": len(opportunity_intelligence.get("recommendations") or []),
                },
            },
        )
        return {
            "opportunity_intelligence": opportunity_intelligence,
            "ai_opportunity_ideation": ideation_result,
        }

    async def generate_plan(self, workspace_id: str, *, horizon_days: int = 30) -> dict[str, Any]:
        workspace = await self._workspace(workspace_id)
        understanding = await self.repositories.site_understanding.latest_for_workspace(workspace_id)
        niche_profile = await self.repositories.workspace_niche_profiles.get(workspace_id)
        understanding = _understanding_with_niche_profile(understanding, niche_profile)
        analysis_job_id = workspace.get("last_analysis_job_id") or (understanding or {}).get("analysis_job_id")
        recommendations = await self.repositories.opportunity_recommendations.list_for_workspace(workspace_id, limit=100)
        decision_opportunities = _recommendations_as_plan_candidates(recommendations)
        result = self.calendar.build_plan(
            workspace=workspace,
            understanding=understanding,
            opportunities=decision_opportunities,
            trend_signals=[],
            coverage=[],
            horizon_days=horizon_days,
        )
        plan_payload = {**result["plan"], "analysis_job_id": analysis_job_id}
        plan = await self.repositories.content_plans.create(workspace_id, plan_payload)
        items = await self.repositories.content_plan_items.create_many(workspace_id, plan["id"], result["items"])
        await self.repositories.autopilot_workspaces.update(
            workspace_id,
            {"status": "planned", "last_content_plan_id": plan["id"]},
        )
        await self.repositories.approval_events.create(
            workspace_id=workspace_id,
            event_type="content_plan_created",
            notes="30-day publishing plan created.",
            metadata={"content_plan_id": plan["id"], "items": len(items)},
        )
        return {"content_plan": plan, "items": items}

    async def get_calendar(self, workspace_id: str) -> dict[str, Any]:
        workspace = await self._workspace(workspace_id)
        latest_plan = await self.repositories.content_plans.latest_for_workspace(workspace_id)
        items = await self.repositories.content_plan_items.list_for_plan(latest_plan["id"]) if latest_plan else []
        return {"workspace": workspace, "content_plan": latest_plan, "items": items}

    async def update_calendar_item(self, item_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        item = await self.repositories.content_plan_items.get(item_id)
        if item is None:
            raise ValueError("Content plan item not found.")
        updates: dict[str, Any] = {}
        if "state" in fields:
            updates["state"] = _safe_item_state(str(fields["state"]))
        if "scheduled_for" in fields:
            updates["scheduled_for"] = fields["scheduled_for"]
        if "title" in fields:
            updates["title"] = fields["title"]
        if "target_keyword" in fields:
            updates["target_keyword"] = fields["target_keyword"]
        if "notes" in fields:
            updates["notes"] = fields["notes"]
        updated = await self.repositories.content_plan_items.update(item_id, updates)
        await self.repositories.approval_events.create(
            workspace_id=item["workspace_id"],
            content_plan_item_id=item_id,
            event_type=f"plan_item_{updates.get('state', 'updated')}",
            notes=str(fields.get("notes") or "Content plan item updated."),
            metadata=updates,
        )
        return updated or item

    async def generate_calendar_item(self, item_id: str) -> dict[str, Any]:
        item = await self.repositories.content_plan_items.get(item_id)
        if item is None:
            raise ValueError("Content plan item not found.")
        workspace = await self._workspace(item["workspace_id"])
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else item.get("metadata_json")
        if not isinstance(metadata, dict):
            metadata = {}
        product_name = str(metadata.get("product_name") or item.get("target_keyword") or workspace.get("name") or "Trendplot content")
        product_url = str(metadata.get("product_url") or workspace.get("website_url") or "")
        publish_policy = item.get("policy") or workspace.get("mode") or "manual_review"
        result = await self.job_service.generate_article(
            GenerateArticleCommand(
                title=str(item.get("title") or "Untitled content"),
                target_keyword=str(item.get("target_keyword") or item.get("title") or ""),
                product_name=product_name,
                product_url=product_url,
                publish_policy=_publish_policy_for_mode(str(publish_policy)),
                unattended_mode=str(publish_policy) in {"auto_draft", "auto_publish"},
                workspace_id=item["workspace_id"],
                content_plan_item_id=item["id"],
                origin_type="content_plan_item",
            )
        )
        state = _state_from_job_status(str(result.get("status") or ""))
        updated = await self.repositories.content_plan_items.update(
            item_id,
            {"state": state, "generated_job_id": result.get("job_id")},
        )
        await self.repositories.approval_events.create(
            workspace_id=item["workspace_id"],
            content_plan_item_id=item_id,
            event_type="content_generated",
            notes=f"Generated content job {result.get('job_id')}.",
            metadata={"job_status": result.get("status"), "job_id": result.get("job_id")},
        )
        return {"item": updated, "article_job": result}

    async def enable_workspace(self, workspace_id: str, *, mode: str) -> dict[str, Any]:
        workspace = await self.repositories.autopilot_workspaces.update(
            workspace_id,
            {"mode": _safe_mode(mode), "status": "active"},
        )
        if workspace is None:
            raise ValueError("Workspace not found.")
        await self.repositories.approval_events.create(
            workspace_id=workspace_id,
            event_type="autopilot_enabled",
            notes=f"Autopilot enabled in {workspace['mode']} mode.",
            metadata={"mode": workspace["mode"]},
        )
        return await self.get_workspace(workspace_id)

    async def pause_workspace(self, workspace_id: str) -> dict[str, Any]:
        workspace = await self.repositories.autopilot_workspaces.update(workspace_id, {"status": "paused"})
        if workspace is None:
            raise ValueError("Workspace not found.")
        await self.repositories.approval_events.create(
            workspace_id=workspace_id,
            event_type="autopilot_paused",
            notes="Autopilot paused.",
        )
        return await self.get_workspace(workspace_id)

    async def run_due_items(self, workspace_id: str, *, limit: int = 1) -> dict[str, Any]:
        workspace = await self._workspace(workspace_id)
        if workspace.get("status") != "active":
            return {"workspace": workspace, "started": [], "skipped_reason": "Workspace is not active."}
        items = await self.repositories.content_plan_items.list_for_workspace(
            workspace_id,
            states=["approved", "scheduled", "planned"],
            limit=limit,
        )
        started = []
        for item in items[: max(1, min(limit, 5))]:
            started.append(await self.generate_calendar_item(item["id"]))
        return {"workspace": await self.repositories.autopilot_workspaces.get(workspace_id), "started": started}

    async def reassess_workspace(self, workspace_id: str) -> dict[str, Any]:
        workspace = await self._workspace(workspace_id)
        understanding = await self.repositories.site_understanding.latest_for_workspace(workspace_id)
        plan_items = await self.repositories.content_plan_items.list_for_workspace(workspace_id, limit=300)
        published = await self.repositories.published_content.list_for_workspace(workspace_id, 100)
        provider_status = await self.repositories.provider_status.list_for_workspace(workspace_id)
        report = self.reassessment.build_report(
            workspace=workspace,
            understanding=understanding,
            plan_items=plan_items,
            trend_signals=[],
            published_content=published,
            provider_status=provider_status,
            coverage=[],
        )
        created = await self.repositories.reassessment_runs.create(workspace_id, report)
        await self.repositories.autopilot_workspaces.update(workspace_id, {"last_reassessment_id": created["id"]})
        await self.repositories.approval_events.create(
            workspace_id=workspace_id,
            event_type="workspace_reassessed",
            notes=created.get("summary") or "Workspace reassessed.",
            metadata={"reassessment_id": created["id"]},
        )
        return {"reassessment": created}

    async def refresh_performance_feedback(self, workspace_id: str) -> dict[str, Any]:
        workspace = await self._workspace(workspace_id)
        published = await self.repositories.published_content.list_for_workspace(workspace_id, 100)
        feedback = self.performance.summarize(workspace=workspace, published_content=published)
        for provider in feedback["provider_status"]:
            await self.repositories.provider_status.upsert(workspace_id=workspace_id, **provider)
        await self.repositories.approval_events.create(
            workspace_id=workspace_id,
            event_type="performance_feedback_refreshed",
            notes="Performance feedback providers checked.",
            metadata={"connected_providers": feedback["connected_providers"]},
        )
        return feedback

    async def sync_connector_inventory(self, workspace_id: str) -> dict[str, Any]:
        workspace = await self._workspace(workspace_id)
        if not self.settings.wordpress_connector_enabled:
            raise ValueError("Trendplot Connector is not enabled.")
        connector = TrendplotWordPressConnectorClient(self.settings)
        capabilities = await connector.capabilities()
        content_inventory = await connector.content_inventory(limit=100)
        product_inventory = await connector.product_inventory(limit=100)
        metrics = await connector.content_metrics(limit=100)
        synced = []
        for item in _inventory_items(content_inventory):
            synced.append(
                await self.repositories.published_content.upsert_from_connector(
                    workspace_id,
                    {
                        "external_id": item.get("id"),
                        "url": item.get("url"),
                        "title": item.get("title"),
                        "status": item.get("status"),
                        "channel": "wordpress",
                        "published_at": item.get("published_at"),
                        "last_checked_at": item.get("updated_at"),
                        "metrics": {"connector_inventory": item},
                    },
                )
            )
        await self.repositories.workspace_connections.upsert(
            workspace_id=workspace_id,
            connection_type="trendplot_connector",
            status="connected",
            capabilities=capabilities.get("capabilities") if isinstance(capabilities.get("capabilities"), dict) else {},
            metadata={
                "site_id": self.settings.wordpress_connector_site_id,
                "site": capabilities.get("site"),
                "last_inventory_count": len(synced),
            },
        )
        await self.repositories.approval_events.create(
            workspace_id=workspace_id,
            event_type="connector_inventory_synced",
            actor="trendplot",
            notes=f"Synced {len(synced)} WordPress content items through Trendplot Connector.",
            metadata={
                "workspace": workspace.get("id"),
                "content_count": len(synced),
                "product_count": len(_inventory_items(product_inventory)),
                "metrics_count": len(_inventory_items(metrics)),
            },
        )
        return {
            "capabilities": capabilities,
            "synced_content": synced,
            "product_inventory": product_inventory,
            "metrics": metrics,
        }

    async def refresh_niche_profile(
        self,
        workspace_id: str,
        *,
        understanding: dict[str, Any] | None = None,
        competitor_snapshots: list[dict[str, Any]] | None = None,
        create_event: bool = True,
    ) -> dict[str, Any]:
        workspace = await self._workspace(workspace_id)
        if not self.settings.niche_intelligence_enabled:
            return await self.repositories.workspace_niche_profiles.get(workspace_id) or {}
        understanding = understanding or await self.repositories.site_understanding.latest_for_workspace(workspace_id)
        competitor_snapshots = competitor_snapshots or []
        existing = await self.repositories.workspace_niche_profiles.get(workspace_id)
        profile_payload = self.niche_intelligence.build_profile(
            workspace=workspace,
            understanding=understanding,
            competitor_snapshots=competitor_snapshots,
            trend_signals=[],
            coverage=[],
            existing_profile=existing,
        )
        profile = await self.repositories.workspace_niche_profiles.upsert(workspace_id, profile_payload)
        if create_event:
            await self.repositories.approval_events.create(
                workspace_id=workspace_id,
                event_type="niche_profile_refreshed",
                actor="trendplot",
                notes=f"Niche profile refreshed for {profile.get('primary_niche') or 'generic niche'}.",
                metadata={"niche_profile_id": profile["id"], "confidence": profile.get("confidence")},
            )
        return profile

    async def connector_capabilities(self, workspace_id: str | None = None) -> dict[str, Any]:
        if workspace_id:
            await self._workspace(workspace_id)
        payload = self.connector_contract.capabilities()
        payload["configured"] = bool(
            self.settings.wordpress_connector_enabled
            and self.settings.wordpress_connector_base_url
            and self.settings.wordpress_connector_site_id
            and self.settings.wordpress_connector_secret
        )
        return payload

    async def _run_ai_opportunity_ideation(
        self,
        workspace_id: str,
        *,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        if not self.settings.ai_opportunity_ideation_enabled:
            return {"opportunities": [], "run": None, "warnings": ["Ideation disabled."], "metrics": {"enabled": False}}
        workspace = await self.repositories.autopilot_workspaces.get(workspace_id)
        return await self.ai_opportunity_ideation.generate_for_workspace(
            workspace_id,
            workspace=workspace,
            force_refresh=force_refresh,
        )

    async def _workspace(self, workspace_id: str) -> dict[str, Any]:
        workspace = await self.repositories.autopilot_workspaces.get(workspace_id)
        if workspace is None:
            raise ValueError("Workspace not found.")
        return workspace

    async def _refresh_connection_status(self, workspace_id: str) -> None:
        connector_connected = bool(
            self.settings.wordpress_connector_enabled
            and self.settings.wordpress_connector_base_url
            and self.settings.wordpress_connector_site_id
            and self.settings.wordpress_connector_secret
        )
        await self.repositories.workspace_connections.upsert(
            workspace_id=workspace_id,
            connection_type="trendplot_connector",
            status="configured" if connector_connected else "not_connected",
            capabilities={
                "capability_discovery": connector_connected,
                "draft_publish": connector_connected,
                "live_publish": False,
                "media_upload": connector_connected,
                "inventory_sync": connector_connected,
                "metrics_events": connector_connected,
            },
            metadata={
                "base_url_configured": bool(self.settings.wordpress_connector_base_url),
                "site_id": self.settings.wordpress_connector_site_id,
            },
        )

    async def _refresh_provider_status(self, workspace_id: str) -> None:
        connector_connected = bool(
            self.settings.wordpress_connector_enabled
            and self.settings.wordpress_connector_base_url
            and self.settings.wordpress_connector_site_id
            and self.settings.wordpress_connector_secret
        )
        await self.repositories.provider_status.upsert(
            workspace_id=workspace_id,
            provider_name="trendplot-connector",
            provider_type="cms_connector",
            status="configured" if connector_connected else "not_configured",
            capabilities={
                "capability_discovery": connector_connected,
                "draft_publish": connector_connected,
                "plugin_owns_builder_metadata": True,
            },
        )
        for provider in self.performance.summarize(workspace={"id": workspace_id}, published_content=[])["provider_status"]:
            await self.repositories.provider_status.upsert(workspace_id=workspace_id, **provider)


def _collect_relevance_labels(
    *,
    niche_profile: dict[str, Any] | None = None,
    opportunities: list[dict[str, Any]] | None = None,
    coverage: list[dict[str, Any]] | None = None,
    competitor_snapshots: list[dict[str, Any]] | None = None,
    market_candidates: list[dict[str, Any]] | None = None,
    editorial_concepts: list[dict[str, Any]] | None = None,
    strategist_ideas: list[dict[str, Any]] | None = None,
    ideation_opportunities: list[dict[str, Any]] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Gather the universe of candidate entity/topic labels for relevance scoring.

    Mirrors the sources OI discovery draws from so the produced scores line up with the
    candidates that will be built. Returns ``(labels, provenance)`` where provenance is a
    ``{label_lower: hint}`` map. Provenance is computed from the SET of sources an entity
    appears in (Part 2), so an entity seen only on competitor pages is tagged
    ``competitor_only`` — the signal that distinguishes a competitor's product/client mention
    from one of the site's own topics.
    """
    labels: list[str] = []
    sources: dict[str, set[str]] = {}

    def add(value: Any, source: str) -> None:
        text = str(value or "").strip()
        if not text:
            return
        labels.append(text)
        sources.setdefault(text.lower(), set()).add(source)

    profile = niche_profile or {}
    for entity in _label_values(profile.get("known_entities")):
        add(entity, "site")
    for product in _label_values(profile.get("known_products")):
        add(product, "site")
    for category in _label_values(profile.get("known_categories")):
        add(category, "site")
    for opportunity in opportunities or []:
        add(opportunity.get("target_keyword") or opportunity.get("title"), "site")
    for item in coverage or []:
        add(item.get("name"), "site")
    for snapshot in competitor_snapshots or []:
        for topic in [*_label_values(snapshot.get("topics")), *_label_values(snapshot.get("gap_notes"))]:
            add(topic, "competitor")
    for candidate in market_candidates or []:
        add(candidate.get("topic") or candidate.get("target_keyword") or candidate.get("title"), "market")
    for concept in editorial_concepts or []:
        add(concept.get("topic") or concept.get("target_keyword") or concept.get("title"), "market")
    for idea in strategist_ideas or []:
        add(idea.get("topic") or idea.get("target_keyword") or idea.get("title") or idea.get("entity"), "site")
    for opp in ideation_opportunities or []:
        add(opp.get("headline") or opp.get("title"), "site")
        for product in opp.get("related_products") or []:
            add(product, "site")

    provenance = {label: _provenance_from_sources(srcs) for label, srcs in sources.items()}
    return labels, provenance


def _provenance_from_sources(srcs: set[str]) -> str:
    site = "site" in srcs
    competitor = "competitor" in srcs
    if site and competitor:
        return "mixed"
    if competitor:  # competitor presence without own-site presence (even if also "market")
        return "competitor_only"
    if site:
        return "own_site"
    if "market" in srcs:
        return "market"
    return "unknown"


def _build_relevance_context(
    workspace: dict[str, Any] | None,
    understanding: dict[str, Any] | None,
    niche_profile: dict[str, Any] | None,
    competitor_snapshots: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Grounding context for the relevance scorer (Part 1): the specific site, not the vertical."""
    ws = workspace or {}
    profile = niche_profile or {}
    u = understanding or {}
    settings = ws.get("settings") if isinstance(ws.get("settings"), dict) else {}

    competitor_domains: list[str] = []
    for value in settings.get("competitors") or []:
        dom = _domain_of(value)
        if dom and dom not in competitor_domains:
            competitor_domains.append(dom)
    for snapshot in competitor_snapshots or []:
        dom = _domain_of(snapshot.get("competitor_url"))
        if dom and dom not in competitor_domains:
            competitor_domains.append(dom)

    return {
        "workspace_name": ws.get("name") or "",
        "domain": ws.get("website_url") or "",
        "website_url": ws.get("website_url") or "",
        "primary_niche": profile.get("primary_niche") or u.get("detected_niche") or "generic",
        "secondary_niches": profile.get("secondary_niches") or [],
        "niche_description": profile.get("niche_description") or u.get("summary") or "",
        "site_summary": u.get("summary") or "",
        "known_entities": profile.get("known_entities") or [],
        "known_categories": profile.get("known_categories") or [],
        "known_audiences": profile.get("known_audiences") or u.get("audiences") or [],
        "competitor_domains": competitor_domains[:12],
    }


def _domain_of(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    from urllib.parse import urlparse

    host = urlparse(text if "://" in text else f"//{text}", scheme="").netloc or text
    return host.lower().lstrip("www.").split("/")[0]


def _label_values(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value:
        items = [value]
    else:
        items = []
    out: list[str] = []
    for item in items:
        text = str(item.get("name") if isinstance(item, dict) else item or "").strip()
        if text:
            out.append(text)
    return out


def _strategy_profile_from_understanding(understanding: dict[str, Any] | None) -> dict[str, Any] | None:
    if not understanding:
        return None
    source = understanding.get("source") if isinstance(understanding.get("source"), dict) else {}
    profile = source.get("strategy_profile") if isinstance(source, dict) else None
    return profile if isinstance(profile, dict) else None


def _site_understanding_snapshot(analysis: dict[str, Any], workspace: dict[str, Any]) -> dict[str, Any]:
    artifacts = _artifact_map(analysis.get("artifacts", []))
    vertical = artifacts.get("vertical_detection") or {}
    product = artifacts.get("product_intelligence") or {}
    niche = artifacts.get("niche_intelligence") or {}
    competitor = artifacts.get("competitor_intelligence") or {}
    opportunities = analysis.get("opportunities", [])
    clusters = analysis.get("clusters", [])
    strategy_profile = analysis.get("strategy_profile")
    if not isinstance(strategy_profile, dict):
        strategy_profile = next(
            (
                artifact.get("content_json")
                for artifact in analysis.get("artifacts", [])
                if artifact.get("artifact_type") == "site_strategy_profile"
            ),
            None,
        )
    return {
        "analysis_job_id": (analysis.get("analysis_job") or {}).get("id"),
        "summary": (analysis.get("analysis_job") or {}).get("summary") or f"Trendplot analyzed {workspace.get('website_url')}.",
        "detected_niche": vertical.get("detected_vertical") or niche.get("niche") or "generic",
        "niche_confidence": vertical.get("confidence") or vertical.get("detected_vertical_confidence") or 0.5,
        "products_services": product.get("extracted_products") or _top_keywords(opportunities),
        "audiences": analysis.get("audiences", [])[:8],
        "competitors": competitor.get("competitors") or _competitor_urls(analysis),
        "brand_voice": {"summary": "Inferred from website copy and headings.", "status": "inferred"},
        "trust_topics": niche.get("safety_or_trust_topics") or competitor.get("trust_topics") or [],
        "content_gaps": competitor.get("missing_topics") or [item.get("title") for item in opportunities[:8]],
        "vertical_detection": vertical,
        "strategy_profile": strategy_profile if isinstance(strategy_profile, dict) else {},
        "source": {
            "analysis_job_id": (analysis.get("analysis_job") or {}).get("id"),
            "clusters": len(clusters),
            "opportunities": len(opportunities),
            "strategy_profile": strategy_profile if isinstance(strategy_profile, dict) else {},
        },
    }


def _inventory_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(data, list):
        nested = payload.get("data") if isinstance(payload, dict) else {}
        data = nested.get("items", []) if isinstance(nested, dict) else []
    return [item for item in data if isinstance(item, dict)]


def _understanding_with_niche_profile(
    understanding: dict[str, Any] | None,
    niche_profile: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not niche_profile:
        return understanding
    merged = dict(understanding or {})
    if not merged.get("detected_niche") or merged.get("detected_niche") == "generic":
        merged["detected_niche"] = niche_profile.get("primary_niche") or "generic"
    merged["products_services"] = _merged_list(
        merged.get("products_services"),
        niche_profile.get("known_products"),
        niche_profile.get("known_entities"),
    )
    merged["audiences"] = _merged_list(merged.get("audiences"), niche_profile.get("known_audiences"))
    merged["content_gaps"] = _merged_list(
        merged.get("content_gaps"),
        niche_profile.get("secondary_niches"),
        niche_profile.get("known_categories"),
        niche_profile.get("common_terminology"),
    )
    merged["niche_profile"] = niche_profile
    return merged


def _recommendations_as_plan_candidates(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for recommendation in recommendations:
        action = str(recommendation.get("action") or "")
        if action not in {"create", "refresh", "expand"}:
            continue
        candidates.append(
            {
                "id": recommendation.get("related_opportunity_id"),
                "title": recommendation.get("title") or recommendation.get("topic"),
                "target_keyword": recommendation.get("target_keyword") or recommendation.get("topic"),
                "content_role": _content_role_for_recommendation(action),
                "source_type": "opportunity_intelligence",
                "opportunity_score": recommendation.get("score"),
                "confidence": recommendation.get("confidence"),
                "rationale": recommendation.get("explanation") or "; ".join(str(reason) for reason in recommendation.get("reasons", [])[:3]),
                "needs_verification": action == "create",
                "_planning_priority": recommendation.get("score"),
                "_planner_action": "refresh" if action == "refresh" else "create",
                "_coverage_gap_score": recommendation.get("coverage_gap"),
                "_cannibalization_risk": recommendation.get("cannibalization_risk"),
                "_refresh_score": 1 - float(recommendation.get("freshness") or 0.5),
                "metadata": {
                    "opportunity_recommendation_id": recommendation.get("id"),
                    "recommendation_action": action,
                    "recommendation_priority": recommendation.get("priority"),
                    "demand_evidence": recommendation.get("demand_evidence") or {},
                    "has_external_evidence": recommendation.get("has_external_evidence"),
                },
            }
        )
    return candidates


def _content_role_for_recommendation(action: str) -> str:
    if action == "refresh":
        return "refresh_task"
    if action == "expand":
        return "supporting_article"
    return "trend_article"


def _merged_list(*values: Any) -> list[Any]:
    merged = []
    seen: set[str] = set()
    for value in values:
        items = value if isinstance(value, list) else [value] if value else []
        for item in items:
            key = str(item.get("name") if isinstance(item, dict) else item or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def _competitor_snapshots(analysis: dict[str, Any], workspace_id: str) -> list[dict[str, Any]]:
    analysis_job_id = (analysis.get("analysis_job") or {}).get("id")
    artifacts = _artifact_map(analysis.get("artifacts") or [])
    seo_intelligence = artifacts.get("competitor_seo_intelligence") if isinstance(artifacts.get("competitor_seo_intelligence"), dict) else {}
    coverage_gaps = seo_intelligence.get("coverage_gaps") if isinstance(seo_intelligence.get("coverage_gaps"), list) else []
    topics_by_domain = seo_intelligence.get("competitor_coverage_topics") if isinstance(seo_intelligence.get("competitor_coverage_topics"), dict) else {}

    gaps_by_domain: dict[str, list[str]] = {}
    for item in coverage_gaps:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        for domain in item.get("competitors") or []:
            key = str(domain or "").strip().lower()
            if not topic or not key:
                continue
            gaps_by_domain.setdefault(key, []).append(topic)

    snapshots = []
    seen_domains: set[str] = set()
    from app.domain_classification import classify_domain, is_competitor_classification

    for page in analysis.get("pages", []):
        if page.get("source_type") != "competitor":
            continue
        competitor_url = page.get("source_url") or page.get("page_url") or ""
        domain = _domain_of(str(competitor_url))
        if not domain:
            continue
        profile = classify_domain(domain, str(competitor_url))
        if not is_competitor_classification(profile["classification"]):
            continue
        if domain in seen_domains:
            continue
        seen_domains.add(domain)
        topics = [str(item) for item in (topics_by_domain.get(domain) or []) if str(item).strip()][:14]
        gap_notes = list(dict.fromkeys(gaps_by_domain.get(domain, [])))[:12]
        snapshots.append(
            {
                "analysis_job_id": analysis_job_id,
                "competitor_url": competitor_url,
                "summary": page.get("title") or "",
                "topics": topics or gap_notes,
                "products_services": page.get("entities", [])[:8],
                "content_formats": ["faq", "guide", "product", "service", "category", "blog"],
                "gap_notes": gap_notes,
                "workspace_id": workspace_id,
            }
        )
    return snapshots


def _artifact_map(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    mapped = {}
    for artifact in artifacts:
        mapped[str(artifact.get("artifact_type"))] = artifact.get("content_json") or artifact.get("content_text") or {}
    return mapped


def _top_keywords(opportunities: list[dict[str, Any]]) -> list[str]:
    values = []
    for opportunity in opportunities[:12]:
        value = str(opportunity.get("product_name") or opportunity.get("target_keyword") or opportunity.get("title") or "").strip()
        if value and value not in values:
            values.append(value)
    return values


def _competitor_urls(analysis: dict[str, Any]) -> list[str]:
    urls = []
    for page in analysis.get("pages", []):
        if page.get("source_type") == "competitor" and page.get("source_url") not in urls:
            urls.append(page.get("source_url"))
    return urls


def _merge_competitor_url_lists(existing: list[str], incoming: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in incoming + existing:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        merged.append(text)
    return merged


def _safe_mode(mode: str) -> str:
    return mode if mode in {"manual_review", "auto_draft", "auto_publish"} else "manual_review"


def _safe_cadence(cadence: str) -> str:
    return cadence if cadence in {"daily", "weekly", "custom"} else "weekly"


def _analysis_page_row_to_crawl_page(row: dict[str, Any]) -> dict[str, Any]:
    outbound = []
    for key in ("extracted_links", "navigation_links"):
        for link in row.get(key) or []:
            if isinstance(link, dict) and link.get("url"):
                outbound.append({"text": str(link.get("text") or ""), "url": str(link.get("url"))})
    headings = []
    for level, values in (("h1", row.get("h1") or []), ("h2", row.get("h2") or []), ("h3", row.get("h3") or [])):
        for text in values:
            headings.append({"level": level, "text": str(text)})
    return {
        "url": str(row.get("page_url") or ""),
        "title": str(row.get("title") or ""),
        "headings": headings,
        "text_sample": str(row.get("body_sample") or ""),
        "outbound_links": outbound,
        "h1": list(row.get("h1") or []),
        "h2": list(row.get("h2") or []),
        "h3": list(row.get("h3") or []),
    }


def _competitor_snapshots_from_sites(
    competitor_sites: list[dict[str, Any]],
    workspace_id: str,
    analysis_job_id: str,
) -> list[dict[str, Any]]:
    from app.domain_classification import classify_domain, is_competitor_classification

    rows = []
    for site in competitor_sites:
        url = str(site.get("url") or "")
        domain = _domain_of(url)
        if domain:
            profile = classify_domain(domain, url)
            if not is_competitor_classification(profile["classification"]):
                continue
        rows.append(
            {
                "analysis_job_id": analysis_job_id,
                "competitor_url": url,
                "summary": f"Competitor site with {len(site.get('pages') or [])} pages analyzed.",
                "topics": [],
                "products_services": [],
                "content_formats": [],
                "gap_notes": [],
            }
        )
    return rows


async def _emit_progress(callback: ProgressCallback | None, event: dict[str, Any]) -> None:
    if callback is None:
        return
    try:
        await callback(event)
    except Exception:
        return


async def _emit_disabled_analyze_steps(callback: ProgressCallback | None) -> None:
    """Mark optional pipeline steps disabled for ideation short-circuit analyze."""
    disabled_steps = (
        ("competitor_discovery", "Competitor discovery disabled in short-circuit mode."),
        ("competitor_analysis", "Competitor analysis disabled in short-circuit mode."),
        ("market_intelligence", "Market intelligence disabled in short-circuit mode."),
        ("entity_relevance", "Entity relevance scoring disabled in short-circuit mode."),
        ("editorial_opportunity", "Editorial opportunity generation disabled in short-circuit mode."),
        ("ai_editorial_strategist", "AI editorial strategist disabled in short-circuit mode."),
        ("ai_recommendation_review", "AI recommendation review disabled in short-circuit mode."),
    )
    for step_key, message in disabled_steps:
        await _emit_progress(
            callback,
            {"step": step_key, "status": "disabled", "message": message},
        )


def _competitor_discovery_progress(discovery: dict[str, Any]) -> tuple[str, str]:
    source = str(discovery.get("source") or "none")
    provided_count = int(discovery.get("provided_count") or 0)
    discovered_count = int(discovery.get("discovered_count") or 0)
    selected_count = int(discovery.get("selected_count") or discovery.get("competitors_selected") or 0)
    warning = str(discovery.get("warning") or "").strip()

    if source == "provided+discovered":
        return "succeeded", f"Merged {provided_count} provided and {discovered_count} discovered competitors ({selected_count} total)."
    if source == "provided":
        return "succeeded", f"Using {selected_count or provided_count} provided competitor URL(s)."
    if source == "discovered":
        return "succeeded", f"Discovered {discovered_count} competitor URL(s)."
    if warning:
        return "warning", warning
    return "warning", "No competitors could be identified automatically."


def _entity_progress_message(metrics: dict[str, Any]) -> str:
    requested = int(metrics.get("entities_requested") or 0)
    scored = int(metrics.get("entities_scored") or 0)
    filtered = int(metrics.get("filtered_by_relevance") or 0)
    down_ranked = int(metrics.get("down_ranked_by_relevance") or 0)
    if requested or scored:
        return f"Scored {scored} of {requested} entities; filtered {filtered}, down-ranked {down_ranked}"
    return "Phase 2A entity relevance metrics collected"


def _entity_progress_details(metrics: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "entities_requested",
        "entities_scored",
        "model_calls",
        "cache_hits",
        "cache_misses",
        "filtered_by_relevance",
        "down_ranked_by_relevance",
        "fallback_count",
        "fail_open_reason",
    )
    return {key: metrics.get(key) for key in keys if key in metrics}


def _strategist_progress_message(result: dict[str, Any]) -> str:
    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
    if metrics.get("fail_open_reason"):
        return f"Strategist skipped ({metrics.get('fail_open_reason')})."
    warnings = result.get("warnings") or []
    if warnings:
        return str(warnings[0])[:160]
    return "No site-first ideas generated."


def _site_first_progress_status(result: dict[str, Any], step: str) -> str:
    if step == "ai_opportunity_ideation":
        metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
        if metrics.get("fail_open_reason"):
            return "warning"
        if result.get("opportunities"):
            return "succeeded"
        return "warning"
    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
    if not metrics.get("enabled", True):
        return "skipped"
    if result.get("ideas"):
        return "succeeded"
    return "warning"


def _site_first_progress_message(
    result: dict[str, Any],
    step: str,
    ideation_opportunities: list[Any],
    strategist_ideas: list[Any],
) -> str:
    if step == "ai_opportunity_ideation":
        metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
        if metrics.get("cache_hit"):
            return f"Loaded {len(ideation_opportunities)} cached AI opportunities."
        if ideation_opportunities:
            return f"Generated {len(ideation_opportunities)} AI article opportunities."
        if metrics.get("fail_open_reason"):
            return f"AI opportunity ideation skipped ({metrics.get('fail_open_reason')})."
        warnings = result.get("warnings") or []
        if warnings:
            return str(warnings[0])[:160]
        return "No AI article opportunities generated."
    if strategist_ideas:
        return f"Generated {len(strategist_ideas)} site-first ideas."
    return _strategist_progress_message(result)


def _review_progress_message(metrics: dict[str, Any]) -> str:
    if metrics.get("review_skipped"):
        reason = str(metrics.get("fail_open_reason") or "skipped")
        return f"Recommendation review skipped ({reason})."
    reviewed = int(metrics.get("items_reviewed") or 0)
    return f"Reviewed {reviewed} recommendations for site relevance."


def _safe_item_state(state: str) -> str:
    allowed = {
        "planned",
        "queued_for_generation",
        "generating",
        "draft_ready",
        "needs_review",
        "approved",
        "scheduled",
        "published",
        "skipped",
        "failed",
        "retired",
    }
    return state if state in allowed else "planned"


def _publish_policy_for_mode(mode: str) -> str:
    if mode == "auto_publish":
        return "auto_live"
    if mode == "auto_draft":
        return "auto_draft"
    return "manual_review"


def _state_from_job_status(status: str) -> str:
    if status == "published_live":
        return "published"
    if status == "published_draft":
        return "draft_ready"
    if status in {"ready_for_review", "failed_quality", "failed_sanity"}:
        return "needs_review"
    if status.startswith("failed"):
        return "failed"
    return "draft_ready"


def _status_summary(
    workspace: dict[str, Any],
    understanding: dict[str, Any] | None,
    plan: dict[str, Any] | None,
    items: list[dict[str, Any]],
    trends: list[dict[str, Any]],
    published: list[dict[str, Any]],
) -> dict[str, Any]:
    needs_review = len([item for item in items if item.get("state") in {"needs_review", "draft_ready"}])
    upcoming = [item for item in items if item.get("state") in {"planned", "approved", "scheduled"}]
    return {
        "autopilot": "on" if workspace.get("status") == "active" else "off",
        "mode": workspace.get("mode"),
        "has_site_understanding": bool(understanding),
        "has_plan": bool(plan),
        "upcoming_posts": len(upcoming),
        "needs_review": needs_review,
        "trend_alerts": len(trends),
        "published_posts": len(published),
        "next_post": upcoming[0] if upcoming else None,
    }
