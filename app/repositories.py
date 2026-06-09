import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, desc, insert, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models
from app.providers.base import GeneratedContent


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        return json.loads(value)
    return value


def _json_string(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value)


def _row_dict(row: Any) -> dict[str, Any]:
    return dict(row)


class JobRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_job(
        self,
        request_input: dict[str, Any],
        human_review_required: bool,
        workspace_id: str | None = None,
        content_plan_item_id: str | None = None,
        origin_type: str | None = None,
    ) -> str:
        job_id = str(uuid4())
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                insert(models.jobs).values(
                    id=job_id,
                    status="queued",
                    request_input=request_input,
                    workspace_id=workspace_id,
                    content_plan_item_id=content_plan_item_id,
                    origin_type=origin_type,
                    retry_count=0,
                    last_attempt_at=now,
                    human_review_required=human_review_required,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
        return job_id

    async def mark_status(self, job_id: str, status: str, last_error: str | None = None) -> None:
        async with self.session_factory() as session:
            await session.execute(
                update(models.jobs)
                .where(models.jobs.c.id == job_id)
                .values(status=status, last_error=last_error, updated_at=utc_now())
            )
            await session.commit()

    async def increment_retry(self, job_id: str) -> None:
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                update(models.jobs)
                .where(models.jobs.c.id == job_id)
                .values(
                    retry_count=models.jobs.c.retry_count + 1,
                    last_attempt_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    async def list_recent(
        self,
        limit: int = 10,
        workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            query = select(models.jobs).order_by(desc(models.jobs.c.created_at))
            if workspace_id:
                query = query.where(models.jobs.c.workspace_id == workspace_id)
            result = await session.execute(query.limit(limit))
            rows = result.mappings().all()

        jobs = []
        for row in rows:
            job = _row_dict(row)
            job["request_input"] = _load_json(job["request_input"], {})
            job["human_review_required"] = bool(job["human_review_required"])
            jobs.append(job)
        return jobs

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(select(models.jobs).where(models.jobs.c.id == job_id))
            row = result.mappings().first()
        if row is None:
            return None

        job = _row_dict(row)
        job["request_input"] = _load_json(job["request_input"], {})
        job["human_review_required"] = bool(job["human_review_required"])
        return job

    async def clear_generated_job_references(self, job_id: str) -> None:
        async with self.session_factory() as session:
            now = utc_now()
            for table, column in (
                (models.content_plan_items, models.content_plan_items.c.generated_job_id),
                (models.workspace_content_inventory, models.workspace_content_inventory.c.generated_job_id),
                (models.published_content, models.published_content.c.job_id),
            ):
                values: dict[str, Any] = {column.key: None}
                if hasattr(table.c, "updated_at"):
                    values["updated_at"] = now
                await session.execute(update(table).where(column == job_id).values(**values))
            await session.commit()

    async def delete_job(self, job_id: str) -> bool:
        async with self.session_factory() as session:
            result = await session.execute(delete(models.jobs).where(models.jobs.c.id == job_id))
            await session.commit()
        return bool(result.rowcount)

    async def update_wordpress_publish_state(self, job_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {
            "wordpress_post_id",
            "wordpress_edit_url",
            "wordpress_public_url",
            "wordpress_status",
            "wordpress_draft_created_at",
            "wordpress_connector_site_url",
            "wordpress_publish_error",
            "wordpress_publish_attempted_at",
            "wordpress_draft_updated_at",
            "last_wordpress_sync_at",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return await self.get_job(job_id)
        updates["updated_at"] = utc_now()
        async with self.session_factory() as session:
            await session.execute(update(models.jobs).where(models.jobs.c.id == job_id).values(**updates))
            await session.commit()
        return await self.get_job(job_id)

    async def update_job_seo(self, job_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {
            "seo_title",
            "seo_description",
            "seo_focus_keyword",
            "seo_canonical_url",
            "seo_robots",
            "seo_schema_type",
            "seo_generated_at",
            "seo_synced_at",
            "seo_last_error",
            "rank_math_score",
            "recommended_slug",
            "seo_manually_edited",
            "suggested_featured_image_alt",
            "suggested_inline_image_alt",
            "seo_optimized_at",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return await self.get_job(job_id)
        updates["updated_at"] = utc_now()
        async with self.session_factory() as session:
            await session.execute(update(models.jobs).where(models.jobs.c.id == job_id).values(**updates))
            await session.commit()
        return await self.get_job(job_id)


class ArtifactRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_artifact(
        self,
        job_id: str,
        artifact_type: str,
        content: GeneratedContent,
    ) -> str:
        artifact_id = str(uuid4())
        usage = content.usage
        async with self.session_factory() as session:
            await session.execute(
                insert(models.artifacts).values(
                    id=artifact_id,
                    job_id=job_id,
                    artifact_type=artifact_type,
                    content_json=content.content_json,
                    content_text=content.content_text,
                    provider=content.provider,
                    model=content.model,
                    token_input=usage.token_input if usage else None,
                    token_output=usage.token_output if usage else None,
                    estimated_cost=usage.estimated_cost if usage else None,
                    created_at=utc_now(),
                )
            )
            await session.commit()
        return artifact_id

    async def create_text_artifact(
        self,
        job_id: str,
        artifact_type: str,
        content_text: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> str:
        return await self.create_artifact(
            job_id,
            artifact_type,
            GeneratedContent(
                content_text=content_text,
                provider=provider or "",
                model=model,
            ),
        )

    async def get_latest_artifact(
        self,
        job_id: str,
        artifact_type: str,
    ) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.artifacts)
                .where(
                    models.artifacts.c.job_id == job_id,
                    models.artifacts.c.artifact_type == artifact_type,
                )
                .order_by(desc(models.artifacts.c.created_at))
                .limit(1)
            )
            row = result.mappings().first()
        if row is None:
            return None

        artifact = _row_dict(row)
        artifact["content_json"] = _json_string(artifact.get("content_json"))
        return artifact

    async def list_for_job(self, job_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.artifacts)
                .where(models.artifacts.c.job_id == job_id)
                .order_by(models.artifacts.c.created_at.asc())
            )
            rows = result.mappings().all()

        artifacts = []
        for row in rows:
            artifact = _row_dict(row)
            if artifact.get("content_json") is not None:
                artifact["content_json"] = _load_json(artifact["content_json"])
            artifacts.append(artifact)
        return artifacts


class JobLogRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def add_log(
        self,
        job_id: str,
        level: str,
        step: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        async with self.session_factory() as session:
            await session.execute(
                insert(models.job_logs).values(
                    id=str(uuid4()),
                    job_id=job_id,
                    level=level,
                    step=step,
                    message=message,
                    context_json=context,
                    created_at=utc_now(),
                )
            )
            await session.commit()

    async def list_for_job(self, job_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.job_logs)
                .where(models.job_logs.c.job_id == job_id)
                .order_by(models.job_logs.c.created_at.asc())
            )
            rows = result.mappings().all()

        logs = []
        for row in rows:
            log = _row_dict(row)
            if log.get("context_json") is not None:
                log["context_json"] = _load_json(log["context_json"])
            logs.append(log)
        return logs


class AnalysisJobRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(
        self,
        website_url: str,
        competitor_urls: list[str],
        max_pages_per_site: int,
        workspace_id: str | None = None,
    ) -> str:
        analysis_job_id = str(uuid4())
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                insert(models.analysis_jobs).values(
                    id=analysis_job_id,
                    workspace_id=workspace_id,
                    website_url=website_url,
                    competitor_urls_json=competitor_urls,
                    status="queued",
                    max_pages_per_site=max_pages_per_site,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
        return analysis_job_id

    async def mark_status(
        self,
        analysis_job_id: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        async with self.session_factory() as session:
            await session.execute(
                update(models.analysis_jobs)
                .where(models.analysis_jobs.c.id == analysis_job_id)
                .values(status=status, error_message=error_message, updated_at=utc_now())
            )
            await session.commit()

    async def save_artifacts(
        self,
        analysis_job_id: str,
        summary: str | None = None,
        prompt: str | None = None,
        raw_response: dict[str, Any] | None = None,
    ) -> None:
        values: dict[str, Any] = {"updated_at": utc_now()}
        if summary is not None:
            values["summary"] = summary
        if prompt is not None:
            values["prompt"] = prompt
        if raw_response is not None:
            values["raw_response_json"] = raw_response

        async with self.session_factory() as session:
            await session.execute(
                update(models.analysis_jobs)
                .where(models.analysis_jobs.c.id == analysis_job_id)
                .values(**values)
            )
            await session.commit()

    async def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(
                    models.analysis_jobs.c.id,
                    models.analysis_jobs.c.website_url,
                    models.analysis_jobs.c.competitor_urls_json,
                    models.analysis_jobs.c.status,
                    models.analysis_jobs.c.max_pages_per_site,
                    models.analysis_jobs.c.error_message,
                    models.analysis_jobs.c.summary,
                    literal(None).label("prompt"),
                    literal(None).label("raw_response_json"),
                    models.analysis_jobs.c.created_at,
                    models.analysis_jobs.c.updated_at,
                )
                .order_by(desc(models.analysis_jobs.c.created_at))
                .limit(limit)
            )
            rows = result.mappings().all()
        return [self._parse_job(_row_dict(row)) for row in rows]

    async def get(self, analysis_job_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.analysis_jobs).where(models.analysis_jobs.c.id == analysis_job_id)
            )
            row = result.mappings().first()
        if row is None:
            return None
        return self._parse_job(_row_dict(row))

    def _parse_job(self, job: dict[str, Any]) -> dict[str, Any]:
        job["competitor_urls"] = _load_json(job.pop("competitor_urls_json"), [])
        raw_response_json = job.pop("raw_response_json", None)
        job["raw_response"] = _load_json(raw_response_json) if raw_response_json is not None else None
        return job


class AnalysisPageRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(
        self,
        analysis_job_id: str,
        source_type: str,
        source_url: str,
        page: dict[str, Any],
    ) -> str:
        page_id = str(uuid4())
        headings = page.get("headings", [])
        h1 = [heading.get("text", "") for heading in headings if heading.get("level") == "h1"]
        h2 = [heading.get("text", "") for heading in headings if heading.get("level") == "h2"]
        h3 = [heading.get("text", "") for heading in headings if heading.get("level") == "h3"]
        async with self.session_factory() as session:
            await session.execute(
                insert(models.analysis_pages).values(
                    id=page_id,
                    analysis_job_id=analysis_job_id,
                    source_type=source_type,
                    source_url=source_url,
                    page_url=page.get("url", ""),
                    title=page.get("title", ""),
                    meta_description=page.get("meta_description", ""),
                    h1_json=h1,
                    h2_json=h2,
                    h3_json=h3,
                    canonical_url=page.get("canonical_url", ""),
                    extracted_links_json=page.get("commercial_links", []),
                    navigation_links_json=page.get("navigation_links", []),
                    questions_json=page.get("questions", []),
                    entities_json=page.get("entities", []),
                    body_sample=page.get("text_sample", ""),
                    error_message=page.get("error"),
                    created_at=utc_now(),
                )
            )
            await session.commit()
        return page_id

    async def list_for_job(self, analysis_job_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.analysis_pages)
                .where(models.analysis_pages.c.analysis_job_id == analysis_job_id)
                .order_by(models.analysis_pages.c.created_at.asc())
            )
            rows = result.mappings().all()

        pages = []
        for row in rows:
            page = _row_dict(row)
            page["h1"] = _load_json(page.pop("h1_json"), [])
            page["h2"] = _load_json(page.pop("h2_json"), [])
            page["h3"] = _load_json(page.pop("h3_json"), [])
            page["extracted_links"] = _load_json(page.pop("extracted_links_json"), [])
            page["navigation_links"] = _load_json(page.pop("navigation_links_json"), [])
            page["questions"] = _load_json(page.pop("questions_json"), [])
            page["entities"] = _load_json(page.pop("entities_json"), [])
            pages.append(page)
        return pages


class AnalysisSuggestionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(
        self,
        analysis_job_id: str,
        suggestions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        created = []
        for suggestion in suggestions:
            created.append(await self.create(analysis_job_id, suggestion))
        return created

    async def create(
        self,
        analysis_job_id: str,
        suggestion: dict[str, Any],
    ) -> dict[str, Any]:
        suggestion_id = str(uuid4())
        now = utc_now()
        row = {
            "id": suggestion_id,
            "analysis_job_id": analysis_job_id,
            "title": suggestion.get("title", ""),
            "target_keyword": suggestion.get("target_keyword", ""),
            "product_name": suggestion.get("product_name", ""),
            "product_url": suggestion.get("product_url", ""),
            "reason": suggestion.get("reason", ""),
            "confidence": suggestion.get("confidence", "medium"),
            "status": suggestion.get("status", "suggested"),
            "generated_job_id": suggestion.get("generated_job_id"),
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.analysis_suggestions).values(**row))
            await session.commit()
        return row

    async def list_for_job(self, analysis_job_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.analysis_suggestions)
                .where(models.analysis_suggestions.c.analysis_job_id == analysis_job_id)
                .order_by(models.analysis_suggestions.c.created_at.asc())
            )
            rows = result.mappings().all()
        return [_row_dict(row) for row in rows]

    async def get(self, suggestion_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.analysis_suggestions).where(models.analysis_suggestions.c.id == suggestion_id)
            )
            row = result.mappings().first()
        if row is None:
            return None
        return _row_dict(row)

    async def update(
        self,
        suggestion_id: str,
        fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        allowed = {
            "title",
            "target_keyword",
            "product_name",
            "product_url",
            "reason",
            "confidence",
            "status",
        }
        updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
        if updates:
            updates["updated_at"] = utc_now()
            async with self.session_factory() as session:
                await session.execute(
                    update(models.analysis_suggestions)
                    .where(models.analysis_suggestions.c.id == suggestion_id)
                    .values(**updates)
                )
                await session.commit()
        return await self.get(suggestion_id)

    async def mark_generated(self, suggestion_id: str, generated_job_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            await session.execute(
                update(models.analysis_suggestions)
                .where(models.analysis_suggestions.c.id == suggestion_id)
                .values(status="generated", generated_job_id=generated_job_id, updated_at=utc_now())
            )
            await session.commit()
        return await self.get(suggestion_id)


class AudienceProfileRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(self, analysis_job_id: str, audiences: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [await self.create(analysis_job_id, audience) for audience in audiences]

    async def create(self, analysis_job_id: str, audience: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(audience.get("id") or uuid4()),
            "analysis_job_id": analysis_job_id,
            "name": str(audience.get("name") or "General audience"),
            "description": str(audience.get("description") or ""),
            "audience_type": str(audience.get("audience_type") or "inferred"),
            "expertise_level": str(audience.get("expertise_level") or "mixed"),
            "confidence": _float_value(audience.get("confidence"), 0.65),
            "commercial_intent": _float_value(audience.get("commercial_intent"), 0.4),
            "research_intent": _float_value(audience.get("research_intent"), 0.6),
            "concerns_json": _list_value(audience.get("concerns")),
            "recurring_questions_json": _list_value(audience.get("recurring_questions")),
            "preferred_content_types_json": _list_value(audience.get("preferred_content_types")),
            "authority_topics_json": _list_value(audience.get("authority_topics")),
            "related_entities_json": _list_value(audience.get("related_entities")),
            "related_clusters_json": _list_value(audience.get("related_clusters")),
            "source_signals_json": audience.get("source_signals") or {},
            "manual_override": bool(audience.get("manual_override", False)),
            "status": str(audience.get("status") or "inferred"),
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.audience_profiles).values(**row))
            await session.commit()
        return self._parse(row)

    async def list_for_job(self, analysis_job_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.audience_profiles)
                .where(models.audience_profiles.c.analysis_job_id == analysis_job_id)
                .order_by(models.audience_profiles.c.created_at.asc())
            )
            rows = result.mappings().all()
        return [self._parse(_row_dict(row)) for row in rows]

    async def update(self, audience_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {"name", "description", "audience_type", "expertise_level", "status", "manual_override"}
        updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
        if updates:
            updates["updated_at"] = utc_now()
            async with self.session_factory() as session:
                await session.execute(
                    update(models.audience_profiles).where(models.audience_profiles.c.id == audience_id).values(**updates)
                )
                await session.commit()
        async with self.session_factory() as session:
            result = await session.execute(select(models.audience_profiles).where(models.audience_profiles.c.id == audience_id))
            row = result.mappings().first()
        return self._parse(_row_dict(row)) if row else None

    def _parse(self, row: dict[str, Any]) -> dict[str, Any]:
        return _parse_json_suffixes(row)


class OpportunityClusterRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(self, analysis_job_id: str, clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [await self.create(analysis_job_id, cluster) for cluster in clusters]

    async def create(self, analysis_job_id: str, cluster: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(cluster.get("id") or uuid4()),
            "analysis_job_id": analysis_job_id,
            "name": str(cluster.get("name") or "Untitled Cluster"),
            "description": str(cluster.get("description") or ""),
            "parent_cluster_id": cluster.get("parent_cluster_id"),
            "entities_json": _list_value(cluster.get("entities")),
            "source_terms_json": _list_value(cluster.get("source_terms")),
            "confidence": _float_value(cluster.get("confidence"), 0.65),
            "authority_value": _float_value(cluster.get("authority_value"), 0.5),
            "seo_value": _float_value(cluster.get("seo_value"), 0.5),
            "editorial_value": _float_value(cluster.get("editorial_value"), 0.5),
            "geo_value": _float_value(cluster.get("geo_value"), 0.5),
            "opportunity_count": int(cluster.get("opportunity_count") or 0),
            "primary_audiences_json": _list_value(cluster.get("primary_audiences")),
            "audience_overlap_json": _list_value(cluster.get("audience_overlap")),
            "pillar_candidate": bool(cluster.get("pillar_candidate", False)),
            "semantic_authority_role": str(cluster.get("semantic_authority_role") or ""),
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.opportunity_clusters).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def list_for_job(self, analysis_job_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.opportunity_clusters)
                .where(models.opportunity_clusters.c.analysis_job_id == analysis_job_id)
                .order_by(models.opportunity_clusters.c.created_at.asc())
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class OpportunityRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(self, analysis_job_id: str, opportunities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [await self.create(analysis_job_id, opportunity) for opportunity in opportunities]

    async def create(self, analysis_job_id: str, opportunity: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(opportunity.get("id") or uuid4()),
            "analysis_job_id": analysis_job_id,
            "cluster_id": opportunity.get("cluster_id"),
            "title": str(opportunity.get("title") or "Untitled opportunity"),
            "target_keyword": str(opportunity.get("target_keyword") or opportunity.get("title") or ""),
            "product_name": str(opportunity.get("product_name") or ""),
            "product_url": str(opportunity.get("product_url") or ""),
            "opportunity_type": str(opportunity.get("opportunity_type") or "semantic_support_article"),
            "search_intent": str(opportunity.get("search_intent") or "informational"),
            "funnel_stage": str(opportunity.get("funnel_stage") or "awareness"),
            "content_role": str(opportunity.get("content_role") or "supporting_article"),
            "primary_audience_id": opportunity.get("primary_audience_id"),
            "secondary_audience_ids_json": _list_value(opportunity.get("secondary_audience_ids")),
            "audience_rationale": str(opportunity.get("audience_rationale") or ""),
            "expertise_level": str(opportunity.get("expertise_level") or "mixed"),
            "confidence": _float_value(opportunity.get("confidence"), 0.65),
            "scores_json": opportunity.get("scores") or {},
            "related_products_json": _list_value(opportunity.get("related_products")),
            "related_keywords_json": _list_value(opportunity.get("related_keywords")),
            "related_entities_json": _list_value(opportunity.get("related_entities")),
            "authority_graph_node_ids_json": _list_value(opportunity.get("authority_graph_node_ids")),
            "relationship_ids_json": _list_value(opportunity.get("relationship_ids")),
            "rationale": str(opportunity.get("rationale") or opportunity.get("reason") or ""),
            "source_type": str(opportunity.get("source_type") or "inferred"),
            "evidence_summary": str(opportunity.get("evidence_summary") or ""),
            "needs_verification": bool(opportunity.get("needs_verification", True)),
            "evidence_items_json": _list_value(opportunity.get("evidence_items")),
            "competitor_references_json": _list_value(opportunity.get("competitor_references")),
            "suggested_article_length": int(opportunity.get("suggested_article_length") or 1800),
            "suggested_structure_json": _list_value(opportunity.get("suggested_structure")),
            "suggested_media_json": _list_value(opportunity.get("suggested_media")),
            "suggested_internal_links_json": _list_value(opportunity.get("suggested_internal_links")),
            "cta_strategy": str(opportunity.get("cta_strategy") or ""),
            "status": str(opportunity.get("status") or "suggested"),
            "generated_job_id": opportunity.get("generated_job_id"),
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.opportunities).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def list_for_job(
        self,
        analysis_job_id: str,
        *,
        cluster_id: str | None = None,
        audience_id: str | None = None,
        opportunity_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query = select(models.opportunities).where(models.opportunities.c.analysis_job_id == analysis_job_id)
        if cluster_id:
            query = query.where(models.opportunities.c.cluster_id == cluster_id)
        if audience_id:
            query = query.where(models.opportunities.c.primary_audience_id == audience_id)
        if opportunity_type:
            query = query.where(models.opportunities.c.opportunity_type == opportunity_type)
        if status:
            query = query.where(models.opportunities.c.status == status)
        query = query.order_by(desc(models.opportunities.c.confidence)).offset(max(0, offset)).limit(max(1, min(limit, 500)))
        async with self.session_factory() as session:
            result = await session.execute(query)
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    async def get(self, opportunity_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(select(models.opportunities).where(models.opportunities.c.id == opportunity_id))
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def update(self, opportunity_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {"status", "title", "target_keyword", "product_name", "product_url", "generated_job_id"}
        updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
        if updates:
            updates["updated_at"] = utc_now()
            async with self.session_factory() as session:
                await session.execute(update(models.opportunities).where(models.opportunities.c.id == opportunity_id).values(**updates))
                await session.commit()
        return await self.get(opportunity_id)


class OpportunityAudienceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(self, analysis_job_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created = []
        for row in rows:
            item = {
                "id": str(uuid4()),
                "analysis_job_id": analysis_job_id,
                "opportunity_id": row.get("opportunity_id"),
                "audience_id": row.get("audience_id"),
                "role": str(row.get("role") or "secondary"),
                "rationale": str(row.get("rationale") or ""),
                "created_at": utc_now(),
            }
            if not item["opportunity_id"] or not item["audience_id"]:
                continue
            async with self.session_factory() as session:
                await session.execute(insert(models.opportunity_audiences).values(**item))
                await session.commit()
            created.append(item)
        return created


class AuthorityGraphRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_nodes(self, analysis_job_id: str, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created = []
        seen_ids: set[str] = set()
        for node in nodes:
            source_id = str(node.get("id") or uuid4())
            scoped_id = _scoped_authority_node_id(analysis_job_id, source_id)
            if scoped_id in seen_ids:
                continue
            seen_ids.add(scoped_id)
            row = {
                "id": scoped_id,
                "analysis_job_id": analysis_job_id,
                "node_type": str(node.get("node_type") or "concept"),
                "label": str(node.get("label") or ""),
                "description": str(node.get("description") or ""),
                "confidence": _float_value(node.get("confidence"), 0.65),
                "source_signals_json": {
                    **(node.get("source_signals") if isinstance(node.get("source_signals"), dict) else {}),
                    "source_node_id": source_id,
                },
                "created_at": utc_now(),
            }
            if not row["label"]:
                continue
            async with self.session_factory() as session:
                await session.execute(insert(models.authority_graph_nodes).values(**row))
                await session.commit()
            created.append(_parse_json_suffixes(row))
        return created

    async def create_edges(self, analysis_job_id: str, edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created = []
        for edge in edges:
            row = {
                "id": str(uuid4()),
                "analysis_job_id": analysis_job_id,
                "source_node_id": _scoped_authority_node_id(analysis_job_id, edge.get("source_node_id")),
                "target_node_id": _scoped_authority_node_id(analysis_job_id, edge.get("target_node_id")),
                "relationship_type": str(edge.get("relationship_type") or "relates_to"),
                "strength": _float_value(edge.get("strength"), 0.5),
                "rationale": str(edge.get("rationale") or ""),
                "created_at": utc_now(),
            }
            if not row["source_node_id"] or not row["target_node_id"]:
                continue
            async with self.session_factory() as session:
                await session.execute(insert(models.authority_graph_edges).values(**row))
                await session.commit()
            created.append(row)
        return created

    async def list_for_job(self, analysis_job_id: str) -> dict[str, list[dict[str, Any]]]:
        async with self.session_factory() as session:
            node_result = await session.execute(
                select(models.authority_graph_nodes).where(models.authority_graph_nodes.c.analysis_job_id == analysis_job_id)
            )
            edge_result = await session.execute(
                select(models.authority_graph_edges).where(models.authority_graph_edges.c.analysis_job_id == analysis_job_id)
            )
        return {
            "nodes": [_parse_json_suffixes(_row_dict(row)) for row in node_result.mappings().all()],
            "edges": [_row_dict(row) for row in edge_result.mappings().all()],
        }


class OpportunityRelationshipRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(self, analysis_job_id: str, relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created = []
        for relationship in relationships:
            row = {
                "id": str(uuid4()),
                "analysis_job_id": analysis_job_id,
                "parent_id": relationship.get("parent_id"),
                "child_id": relationship.get("child_id"),
                "relationship_type": str(relationship.get("relationship_type") or "supports"),
                "strength": _float_value(relationship.get("strength"), 0.5),
                "rationale": str(relationship.get("rationale") or ""),
                "source": str(relationship.get("source") or "opportunity-engine"),
                "created_at": utc_now(),
            }
            if not row["parent_id"] or not row["child_id"] or row["parent_id"] == row["child_id"]:
                continue
            async with self.session_factory() as session:
                await session.execute(insert(models.opportunity_relationships).values(**row))
                await session.commit()
            created.append(row)
        return created

    async def list_for_opportunity(self, opportunity_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.opportunity_relationships).where(
                    (models.opportunity_relationships.c.parent_id == opportunity_id)
                    | (models.opportunity_relationships.c.child_id == opportunity_id)
                )
            )
            rows = result.mappings().all()
        return [_row_dict(row) for row in rows]


class AnalysisIntelligenceArtifactRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(self, analysis_job_id: str, artifact_type: str, content: dict[str, Any], provider: str = "") -> str:
        artifact_id = str(uuid4())
        async with self.session_factory() as session:
            await session.execute(
                insert(models.analysis_intelligence_artifacts).values(
                    id=artifact_id,
                    analysis_job_id=analysis_job_id,
                    artifact_type=artifact_type,
                    content_json=content,
                    provider=provider,
                    created_at=utc_now(),
                )
            )
            await session.commit()
        return artifact_id

    async def list_for_job(self, analysis_job_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.analysis_intelligence_artifacts)
                .where(models.analysis_intelligence_artifacts.c.analysis_job_id == analysis_job_id)
                .order_by(models.analysis_intelligence_artifacts.c.created_at.asc())
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class AutopilotWorkspaceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(
        self,
        *,
        website_url: str,
        name: str = "",
        mode: str = "manual_review",
        cadence: str = "weekly",
        user_context: str = "",
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(uuid4()),
            "name": name or _workspace_name_from_url(website_url),
            "website_url": website_url,
            "mode": mode,
            "status": "setup",
            "cadence": cadence,
            "user_context": user_context,
            "settings_json": settings or {},
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.autopilot_workspaces).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def get(self, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(select(models.autopilot_workspaces).where(models.autopilot_workspaces.c.id == workspace_id))
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def list_recent(self, limit: int = 25) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.autopilot_workspaces).order_by(desc(models.autopilot_workspaces.c.updated_at)).limit(max(1, min(limit, 100)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    async def update(self, workspace_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {
            "name",
            "mode",
            "status",
            "cadence",
            "user_context",
            "settings_json",
            "last_analysis_job_id",
            "last_content_plan_id",
            "last_reassessment_id",
        }
        updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
        if updates:
            updates["updated_at"] = utc_now()
            async with self.session_factory() as session:
                await session.execute(update(models.autopilot_workspaces).where(models.autopilot_workspaces.c.id == workspace_id).values(**updates))
                await session.commit()
        return await self.get(workspace_id)


class WorkspaceConnectionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def upsert(
        self,
        *,
        workspace_id: str,
        connection_type: str,
        status: str,
        capabilities: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = await self.get(workspace_id, connection_type)
        now = utc_now()
        if existing:
            async with self.session_factory() as session:
                await session.execute(
                    update(models.workspace_connections)
                    .where(models.workspace_connections.c.id == existing["id"])
                    .values(
                        status=status,
                        capabilities_json=capabilities or {},
                        metadata_json=metadata or {},
                        last_checked_at=now,
                        updated_at=now,
                    )
                )
                await session.commit()
            return await self.get(workspace_id, connection_type) or existing
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "connection_type": connection_type,
            "status": status,
            "capabilities_json": capabilities or {},
            "metadata_json": metadata or {},
            "last_checked_at": now,
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.workspace_connections).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def get(self, workspace_id: str, connection_type: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.workspace_connections).where(
                    models.workspace_connections.c.workspace_id == workspace_id,
                    models.workspace_connections.c.connection_type == connection_type,
                )
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def list_for_workspace(self, workspace_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.workspace_connections)
                .where(models.workspace_connections.c.workspace_id == workspace_id)
                .order_by(models.workspace_connections.c.connection_type.asc())
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class SiteUnderstandingRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(self, workspace_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        source_payload = dict(snapshot.get("source") or {})
        strategy_profile = snapshot.get("strategy_profile")
        if isinstance(strategy_profile, dict) and strategy_profile:
            source_payload["strategy_profile"] = strategy_profile
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "analysis_job_id": snapshot.get("analysis_job_id"),
            "summary": str(snapshot.get("summary") or ""),
            "detected_niche": str(snapshot.get("detected_niche") or "generic"),
            "niche_confidence": _float_value(snapshot.get("niche_confidence"), 0.5),
            "products_services_json": _list_value(snapshot.get("products_services")),
            "audiences_json": _list_value(snapshot.get("audiences")),
            "competitors_json": _list_value(snapshot.get("competitors")),
            "brand_voice_json": snapshot.get("brand_voice") or {},
            "trust_topics_json": _list_value(snapshot.get("trust_topics")),
            "content_gaps_json": _list_value(snapshot.get("content_gaps")),
            "vertical_detection_json": snapshot.get("vertical_detection") or {},
            "source_json": source_payload,
            "created_at": utc_now(),
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.site_understanding_snapshots).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def latest_for_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.site_understanding_snapshots)
                .where(models.site_understanding_snapshots.c.workspace_id == workspace_id)
                .order_by(desc(models.site_understanding_snapshots.c.created_at))
                .limit(1)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None


class WorkspaceNicheProfileRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def upsert(self, workspace_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        existing = await self.get(workspace_id)
        now = utc_now()
        values = {
            "workspace_id": workspace_id,
            "primary_niche": str(profile.get("primary_niche") or "generic"),
            "secondary_niches_json": _list_value(profile.get("secondary_niches")),
            "known_entities_json": _list_value(profile.get("known_entities")),
            "known_products_json": _list_value(profile.get("known_products")),
            "known_categories_json": _list_value(profile.get("known_categories")),
            "known_audiences_json": _list_value(profile.get("known_audiences")),
            "common_terminology_json": _list_value(profile.get("common_terminology")),
            "confidence": _float_value(profile.get("confidence"), 0.5),
            "sources_json": profile.get("sources") or {},
            "last_updated": str(profile.get("last_updated") or now),
            "updated_at": now,
        }
        if existing:
            async with self.session_factory() as session:
                await session.execute(
                    update(models.workspace_niche_profiles)
                    .where(models.workspace_niche_profiles.c.id == existing["id"])
                    .values(**values)
                )
                await session.commit()
            return await self.get(workspace_id) or existing
        row = {
            "id": str(uuid4()),
            **values,
            "created_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.workspace_niche_profiles).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def get(self, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.workspace_niche_profiles)
                .where(models.workspace_niche_profiles.c.workspace_id == workspace_id)
                .order_by(desc(models.workspace_niche_profiles.c.updated_at))
                .limit(1)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None


class CompetitorSnapshotRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(self, workspace_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created = []
        for item in rows:
            row = {
                "id": str(uuid4()),
                "workspace_id": workspace_id,
                "analysis_job_id": item.get("analysis_job_id"),
                "competitor_url": str(item.get("competitor_url") or item.get("url") or ""),
                "summary": str(item.get("summary") or ""),
                "topics_json": _list_value(item.get("topics")),
                "products_services_json": _list_value(item.get("products_services")),
                "content_formats_json": _list_value(item.get("content_formats")),
                "gap_notes_json": _list_value(item.get("gap_notes")),
                "created_at": utc_now(),
            }
            if not row["competitor_url"]:
                continue
            async with self.session_factory() as session:
                await session.execute(insert(models.competitor_snapshots).values(**row))
                await session.commit()
            created.append(_parse_json_suffixes(row))
        return created

    async def list_for_workspace(self, workspace_id: str, limit: int = 50) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.competitor_snapshots)
                .where(models.competitor_snapshots.c.workspace_id == workspace_id)
                .order_by(desc(models.competitor_snapshots.c.created_at))
                .limit(max(1, min(limit, 200)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    async def list_peer_urls_for_niche(
        self,
        niche: str,
        *,
        exclude_workspace_id: str | None = None,
        limit: int = 20,
    ) -> list[str]:
        label = str(niche or "").strip().lower()
        if not label or label in {"generic", "unknown"}:
            return []
        async with self.session_factory() as session:
            query = (
                select(models.competitor_snapshots.c.competitor_url)
                .join(
                    models.workspace_niche_profiles,
                    models.competitor_snapshots.c.workspace_id == models.workspace_niche_profiles.c.workspace_id,
                )
                .where(models.workspace_niche_profiles.c.primary_niche.ilike(label))
                .order_by(desc(models.competitor_snapshots.c.created_at))
                .limit(max(1, min(limit, 100)))
            )
            if exclude_workspace_id:
                query = query.where(models.competitor_snapshots.c.workspace_id != exclude_workspace_id)
            result = await session.execute(query)
            rows = result.scalars().all()
        return list(dict.fromkeys(str(item).strip() for item in rows if str(item).strip()))


class TrendSignalRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(self, workspace_id: str, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created = []
        for signal in signals:
            created.append(await self.create(workspace_id, signal))
        return created

    async def create(self, workspace_id: str, signal: dict[str, Any]) -> dict[str, Any]:
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "analysis_job_id": signal.get("analysis_job_id"),
            "run_id": signal.get("run_id"),
            "query_id": signal.get("query_id"),
            "trend_topic": str(signal.get("trend_topic") or signal.get("topic") or ""),
            "query": str(signal.get("query") or ""),
            "source_type": str(signal.get("source_type") or "inferred"),
            "source_provider": str(signal.get("source_provider") or signal.get("provider") or "trendplot"),
            "confidence": _float_value(signal.get("confidence"), 0.5),
            "freshness_score": _float_value(signal.get("freshness_score"), 0.4),
            "trend_velocity": _float_value(signal.get("trend_velocity"), 0.0),
            "niche_relevance": _float_value(signal.get("niche_relevance"), 0.5),
            "audience_relevance": _float_value(signal.get("audience_relevance"), 0.5),
            "business_relevance": _float_value(signal.get("business_relevance"), 0.5),
            "opportunity_score": _float_value(signal.get("opportunity_score"), 0.5),
            "why_it_matters": str(signal.get("why_it_matters") or ""),
            "recommended_angle": str(signal.get("recommended_angle") or ""),
            "recommended_format": str(signal.get("recommended_format") or "supporting_article"),
            "evergreen_classification": str(signal.get("evergreen_classification") or "evergreen"),
            "expires_at": signal.get("expires_at"),
            "content_opportunity_id": signal.get("content_opportunity_id"),
            "needs_verification": bool(signal.get("needs_verification", True)),
            "evidence_items_json": _list_value(signal.get("evidence_items")),
            "raw_signal_json": signal.get("raw_signal") or {},
            "status": str(signal.get("status") or "active"),
            "created_at": utc_now(),
        }
        if not row["trend_topic"]:
            row["trend_topic"] = "General publishing trend"
        async with self.session_factory() as session:
            await session.execute(insert(models.trend_signals).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def list_for_workspace(self, workspace_id: str, limit: int = 25) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.trend_signals)
                .where(models.trend_signals.c.workspace_id == workspace_id)
                .order_by(desc(models.trend_signals.c.created_at))
                .limit(max(1, min(limit, 200)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class TrendDiscoveryRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(self, workspace_id: str, run: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(run.get("id") or uuid4()),
            "workspace_id": workspace_id,
            "analysis_job_id": run.get("analysis_job_id"),
            "status": str(run.get("status") or "completed"),
            "summary": str(run.get("summary") or ""),
            "context_json": run.get("context") or {},
            "provider_status_json": _list_value(run.get("provider_status")),
            "warnings_json": _list_value(run.get("warnings")),
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.trend_discovery_runs).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def latest_for_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.trend_discovery_runs)
                .where(models.trend_discovery_runs.c.workspace_id == workspace_id)
                .order_by(desc(models.trend_discovery_runs.c.created_at))
                .limit(1)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def get(self, run_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(select(models.trend_discovery_runs).where(models.trend_discovery_runs.c.id == run_id))
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None


class TrendDiscoveryQueryRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(self, run_id: str, queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [await self.create(run_id, query) for query in queries]

    async def create(self, run_id: str, query: dict[str, Any]) -> dict[str, Any]:
        row = {
            "id": str(query.get("id") or uuid4()),
            "run_id": run_id,
            "query": str(query.get("query") or ""),
            "query_type": str(query.get("query_type") or "market"),
            "target_entity": str(query.get("target_entity") or ""),
            "target_audience": str(query.get("target_audience") or ""),
            "reason": str(query.get("reason") or ""),
            "created_at": utc_now(),
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.trend_discovery_queries).values(**row))
            await session.commit()
        return row

    async def list_for_run(self, run_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.trend_discovery_queries)
                .where(models.trend_discovery_queries.c.run_id == run_id)
                .order_by(models.trend_discovery_queries.c.created_at.asc())
            )
            rows = result.mappings().all()
        return [_row_dict(row) for row in rows]


class ContentEntityRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def replace_for_workspace(self, workspace_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            await session.execute(models.content_entities.delete().where(models.content_entities.c.workspace_id == workspace_id))
            created = []
            for item in rows:
                row = {
                    "id": str(uuid4()),
                    "workspace_id": workspace_id,
                    "post_id": item.get("post_id"),
                    "job_id": item.get("job_id"),
                    "content_plan_item_id": item.get("content_plan_item_id"),
                    "entity": str(item.get("entity") or ""),
                    "entity_type": str(item.get("entity_type") or "topic"),
                    "confidence": _float_value(item.get("confidence"), 0.6),
                    "source": str(item.get("source") or "publishing_memory"),
                    "created_at": utc_now(),
                }
                if not row["entity"]:
                    continue
                await session.execute(insert(models.content_entities).values(**row))
                created.append(row)
            await session.commit()
        return created

    async def list_for_workspace(self, workspace_id: str, limit: int = 500) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.content_entities)
                .where(models.content_entities.c.workspace_id == workspace_id)
                .limit(max(1, min(limit, 1000)))
            )
            rows = result.mappings().all()
        return [_row_dict(row) for row in rows]


class ContentClusterRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def replace_for_workspace(self, workspace_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            await session.execute(models.content_clusters.delete().where(models.content_clusters.c.workspace_id == workspace_id))
            created = []
            for item in rows:
                row = {
                    "id": str(uuid4()),
                    "workspace_id": workspace_id,
                    "post_id": item.get("post_id"),
                    "job_id": item.get("job_id"),
                    "content_plan_item_id": item.get("content_plan_item_id"),
                    "cluster": str(item.get("cluster") or ""),
                    "confidence": _float_value(item.get("confidence"), 0.6),
                    "source": str(item.get("source") or "publishing_memory"),
                    "created_at": utc_now(),
                }
                if not row["cluster"]:
                    continue
                await session.execute(insert(models.content_clusters).values(**row))
                created.append(row)
            await session.commit()
        return created

    async def list_for_workspace(self, workspace_id: str, limit: int = 500) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.content_clusters)
                .where(models.content_clusters.c.workspace_id == workspace_id)
                .limit(max(1, min(limit, 1000)))
            )
            rows = result.mappings().all()
        return [_row_dict(row) for row in rows]


class ContentCoverageRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def replace_for_workspace(self, workspace_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            await session.execute(models.content_coverage.delete().where(models.content_coverage.c.workspace_id == workspace_id))
            created = []
            for item in rows:
                row = self._row(workspace_id, item)
                await session.execute(insert(models.content_coverage).values(**row))
                created.append(_parse_json_suffixes(row))
            await session.commit()
        return created

    async def list_for_workspace(self, workspace_id: str, coverage_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = select(models.content_coverage).where(models.content_coverage.c.workspace_id == workspace_id)
        if coverage_type:
            query = query.where(models.content_coverage.c.coverage_type == coverage_type)
        query = query.order_by(desc(models.content_coverage.c.gap_score), models.content_coverage.c.name.asc()).limit(max(1, min(limit, 500)))
        async with self.session_factory() as session:
            result = await session.execute(query)
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    async def refresh_candidates(self, workspace_id: str, limit: int = 25) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.content_coverage)
                .where(
                    models.content_coverage.c.workspace_id == workspace_id,
                    models.content_coverage.c.refresh_candidate.is_(True),
                )
                .order_by(desc(models.content_coverage.c.refresh_score))
                .limit(max(1, min(limit, 100)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    def _row(self, workspace_id: str, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(item.get("id") or uuid4()),
            "workspace_id": workspace_id,
            "coverage_type": str(item.get("coverage_type") or "entity"),
            "name": str(item.get("name") or ""),
            "coverage_score": _float_value(item.get("coverage_score"), 0.0),
            "freshness_score": _float_value(item.get("freshness_score"), 0.5),
            "content_count": int(item.get("content_count") or 0),
            "published_count": int(item.get("published_count") or 0),
            "draft_count": int(item.get("draft_count") or 0),
            "gap_score": _float_value(item.get("gap_score"), 1.0),
            "saturation_score": _float_value(item.get("saturation_score"), 0.0),
            "cannibalization_risk": _float_value(item.get("cannibalization_risk"), 0.0),
            "duplicate_topic_risk": _float_value(item.get("duplicate_topic_risk"), 0.0),
            "refresh_score": _float_value(item.get("refresh_score"), 0.0),
            "refresh_candidate": bool(item.get("refresh_candidate", False)),
            "refresh_reason": str(item.get("refresh_reason") or ""),
            "last_published": item.get("last_published"),
            "last_updated": item.get("last_updated"),
            "last_major_update": item.get("last_major_update"),
            "metadata_json": item.get("metadata") or {},
            "updated_at": utc_now(),
        }


class ContentPlanRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(self, workspace_id: str, plan: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "analysis_job_id": plan.get("analysis_job_id"),
            "name": str(plan.get("name") or "30-day publishing plan"),
            "cadence": str(plan.get("cadence") or "weekly"),
            "publish_policy": str(plan.get("publish_policy") or "manual_review"),
            "horizon_days": int(plan.get("horizon_days") or 30),
            "status": str(plan.get("status") or "draft"),
            "summary": str(plan.get("summary") or ""),
            "plan_json": plan.get("plan") or {},
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.content_plans).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def get(self, plan_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(select(models.content_plans).where(models.content_plans.c.id == plan_id))
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def latest_for_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.content_plans)
                .where(models.content_plans.c.workspace_id == workspace_id)
                .order_by(desc(models.content_plans.c.created_at))
                .limit(1)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None


class ContentPlanItemRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(self, workspace_id: str, content_plan_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [await self.create(workspace_id, content_plan_id, item) for item in items]

    async def create(self, workspace_id: str, content_plan_id: str, item: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(uuid4()),
            "content_plan_id": content_plan_id,
            "workspace_id": workspace_id,
            "opportunity_id": item.get("opportunity_id"),
            "trend_signal_id": item.get("trend_signal_id"),
            "generated_job_id": item.get("generated_job_id"),
            "published_content_id": item.get("published_content_id"),
            "sequence_index": int(item.get("sequence_index") or 0),
            "scheduled_for": item.get("scheduled_for"),
            "state": str(item.get("state") or "planned"),
            "content_role": str(item.get("content_role") or "supporting_article"),
            "title": str(item.get("title") or "Untitled publishing opportunity"),
            "target_keyword": str(item.get("target_keyword") or ""),
            "audience": str(item.get("audience") or ""),
            "notes": str(item.get("notes") or ""),
            "policy": str(item.get("policy") or ""),
            "metadata_json": item.get("metadata") or {},
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.content_plan_items).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def get(self, item_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(select(models.content_plan_items).where(models.content_plan_items.c.id == item_id))
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def list_for_plan(self, content_plan_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.content_plan_items)
                .where(models.content_plan_items.c.content_plan_id == content_plan_id)
                .order_by(models.content_plan_items.c.sequence_index.asc())
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    async def list_for_workspace(self, workspace_id: str, states: list[str] | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = select(models.content_plan_items).where(models.content_plan_items.c.workspace_id == workspace_id)
        if states:
            query = query.where(models.content_plan_items.c.state.in_(states))
        query = query.order_by(models.content_plan_items.c.scheduled_for.asc(), models.content_plan_items.c.sequence_index.asc()).limit(max(1, min(limit, 300)))
        async with self.session_factory() as session:
            result = await session.execute(query)
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    async def update(self, item_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {
            "state",
            "scheduled_for",
            "generated_job_id",
            "published_content_id",
            "title",
            "target_keyword",
            "notes",
            "policy",
            "metadata_json",
        }
        updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
        if updates:
            updates["updated_at"] = utc_now()
            async with self.session_factory() as session:
                await session.execute(update(models.content_plan_items).where(models.content_plan_items.c.id == item_id).values(**updates))
                await session.commit()
        return await self.get(item_id)


class PublishedContentRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(self, workspace_id: str, content: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "job_id": content.get("job_id"),
            "content_plan_item_id": content.get("content_plan_item_id"),
            "external_id": str(content.get("external_id") or ""),
            "url": str(content.get("url") or ""),
            "title": str(content.get("title") or ""),
            "status": str(content.get("status") or "draft"),
            "channel": str(content.get("channel") or "wordpress"),
            "clusters_json": _list_value(content.get("clusters")),
            "metrics_json": content.get("metrics") or {},
            "published_at": content.get("published_at"),
            "last_checked_at": content.get("last_checked_at"),
            "refresh_after": content.get("refresh_after"),
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.published_content).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def upsert_from_connector(self, workspace_id: str, content: dict[str, Any]) -> dict[str, Any]:
        external_id = str(content.get("external_id") or content.get("id") or "")
        existing = await self.get_by_external_id(workspace_id, external_id) if external_id else None
        values = {
            "job_id": content.get("job_id"),
            "content_plan_item_id": content.get("content_plan_item_id"),
            "external_id": external_id,
            "url": str(content.get("url") or ""),
            "title": str(content.get("title") or ""),
            "status": str(content.get("status") or "unknown"),
            "channel": str(content.get("channel") or "wordpress"),
            "clusters_json": _list_value(content.get("clusters")),
            "metrics_json": content.get("metrics") or {},
            "published_at": content.get("published_at"),
            "last_checked_at": content.get("last_checked_at") or utc_now(),
            "refresh_after": content.get("refresh_after"),
            "updated_at": utc_now(),
        }
        if existing:
            async with self.session_factory() as session:
                await session.execute(
                    update(models.published_content)
                    .where(models.published_content.c.id == existing["id"])
                    .values(**{key: value for key, value in values.items() if value is not None})
                )
                await session.commit()
            return await self.get_by_external_id(workspace_id, external_id) or existing
        return await self.create(workspace_id, values)

    async def get_by_external_id(self, workspace_id: str, external_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.published_content).where(
                    models.published_content.c.workspace_id == workspace_id,
                    models.published_content.c.external_id == external_id,
                )
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def list_for_workspace(self, workspace_id: str, limit: int = 50) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.published_content)
                .where(models.published_content.c.workspace_id == workspace_id)
                .order_by(desc(models.published_content.c.created_at))
                .limit(max(1, min(limit, 200)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class ReassessmentRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(self, workspace_id: str, report: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "status": str(report.get("status") or "completed"),
            "summary": str(report.get("summary") or ""),
            "strategy_adjustments_json": _list_value(report.get("strategy_adjustments")),
            "new_opportunities_json": _list_value(report.get("new_opportunities")),
            "retired_opportunities_json": _list_value(report.get("retired_opportunities")),
            "recommended_refreshes_json": _list_value(report.get("recommended_refreshes")),
            "calendar_diff_json": report.get("calendar_diff") or {},
            "provider_status_json": report.get("provider_status") or {},
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.reassessment_runs).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def latest_for_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.reassessment_runs)
                .where(models.reassessment_runs.c.workspace_id == workspace_id)
                .order_by(desc(models.reassessment_runs.c.created_at))
                .limit(1)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None


class ProviderStatusRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def upsert(
        self,
        *,
        provider_name: str,
        provider_type: str,
        status: str,
        workspace_id: str | None = None,
        capabilities: dict[str, Any] | None = None,
        last_error: str | None = None,
    ) -> dict[str, Any]:
        existing = await self.get(provider_name=provider_name, provider_type=provider_type, workspace_id=workspace_id)
        now = utc_now()
        if existing:
            async with self.session_factory() as session:
                await session.execute(
                    update(models.provider_status)
                    .where(models.provider_status.c.id == existing["id"])
                    .values(
                        status=status,
                        capabilities_json=capabilities or {},
                        last_error=last_error,
                        last_checked_at=now,
                        updated_at=now,
                    )
                )
                await session.commit()
            return await self.get(provider_name=provider_name, provider_type=provider_type, workspace_id=workspace_id) or existing
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "provider_name": provider_name,
            "provider_type": provider_type,
            "status": status,
            "capabilities_json": capabilities or {},
            "last_error": last_error,
            "last_checked_at": now,
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.provider_status).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def get(self, *, provider_name: str, provider_type: str, workspace_id: str | None = None) -> dict[str, Any] | None:
        query = select(models.provider_status).where(
            models.provider_status.c.provider_name == provider_name,
            models.provider_status.c.provider_type == provider_type,
        )
        if workspace_id is None:
            query = query.where(models.provider_status.c.workspace_id.is_(None))
        else:
            query = query.where(models.provider_status.c.workspace_id == workspace_id)
        async with self.session_factory() as session:
            result = await session.execute(query)
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def list_for_workspace(self, workspace_id: str | None = None) -> list[dict[str, Any]]:
        query = select(models.provider_status)
        if workspace_id is None:
            query = query.where(models.provider_status.c.workspace_id.is_(None))
        else:
            query = query.where((models.provider_status.c.workspace_id == workspace_id) | (models.provider_status.c.workspace_id.is_(None)))
        async with self.session_factory() as session:
            result = await session.execute(query.order_by(models.provider_status.c.provider_type.asc()))
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class ApprovalEventRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(
        self,
        *,
        workspace_id: str,
        event_type: str,
        content_plan_item_id: str | None = None,
        actor: str = "user",
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "content_plan_item_id": content_plan_item_id,
            "event_type": event_type,
            "actor": actor,
            "notes": notes,
            "metadata_json": metadata or {},
            "created_at": utc_now(),
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.approval_events).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def list_for_workspace(self, workspace_id: str, limit: int = 50) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.approval_events)
                .where(models.approval_events.c.workspace_id == workspace_id)
                .order_by(desc(models.approval_events.c.created_at))
                .limit(max(1, min(limit, 200)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class OpportunityRecommendationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def replace_for_workspace(self, workspace_id: str, recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            manual_rows = await session.execute(
                select(models.opportunity_recommendations).where(
                    models.opportunity_recommendations.c.workspace_id == workspace_id,
                    models.opportunity_recommendations.c.source_type == "manual_recommendation",
                    models.opportunity_recommendations.c.status == "active",
                )
            )
            preserved = [self._parse(_row_dict(row)) for row in manual_rows.mappings().all()]
            await session.execute(
                models.opportunity_recommendations.delete().where(
                    models.opportunity_recommendations.c.workspace_id == workspace_id,
                    models.opportunity_recommendations.c.source_type != "manual_recommendation",
                )
            )
            created: list[dict[str, Any]] = []
            for item in recommendations:
                row = self._row(workspace_id, item)
                await session.execute(insert(models.opportunity_recommendations).values(**row))
                created.append(self._parse(row))
            for item in preserved:
                row = self._row(workspace_id, item)
                row["id"] = item.get("id") or row["id"]
                await session.execute(insert(models.opportunity_recommendations).values(**row))
                created.append(self._parse(row))
            await session.commit()
        return created

    async def create_for_workspace(self, workspace_id: str, item: dict[str, Any]) -> dict[str, Any]:
        row = self._row(workspace_id, item)
        async with self.session_factory() as session:
            await session.execute(insert(models.opportunity_recommendations).values(**row))
            await session.commit()
        return self._parse(row)

    async def get_by_id(self, recommendation_id: str, *, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.opportunity_recommendations).where(
                    models.opportunity_recommendations.c.id == recommendation_id,
                    models.opportunity_recommendations.c.workspace_id == workspace_id,
                )
            )
            row = result.mappings().first()
        return self._parse(_row_dict(row)) if row else None

    async def update_status(self, recommendation_id: str, *, workspace_id: str, status: str) -> dict[str, Any] | None:
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                models.opportunity_recommendations.update()
                .where(
                    models.opportunity_recommendations.c.id == recommendation_id,
                    models.opportunity_recommendations.c.workspace_id == workspace_id,
                )
                .values(status=status, updated_at=now)
            )
            await session.commit()
        return await self.get_by_id(recommendation_id, workspace_id=workspace_id)

    async def list_for_workspace(
        self,
        workspace_id: str,
        *,
        action: str | None = None,
        status: str = "active",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = select(models.opportunity_recommendations).where(
            models.opportunity_recommendations.c.workspace_id == workspace_id
        )
        if status:
            query = query.where(models.opportunity_recommendations.c.status == status)
        if action:
            query = query.where(models.opportunity_recommendations.c.action == action)
        query = query.order_by(desc(models.opportunity_recommendations.c.score)).limit(max(1, min(limit, 500)))
        async with self.session_factory() as session:
            result = await session.execute(query)
            rows = result.mappings().all()
        return [self._parse(_row_dict(row)) for row in rows]

    def _row(self, workspace_id: str, item: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        metadata = {
            **metadata,
            "explanation": item.get("explanation") or metadata.get("explanation"),
            "demand_evidence": item.get("demand_evidence") or metadata.get("demand_evidence") or {},
        }
        return {
            "id": str(item.get("id") or uuid4()),
            "workspace_id": workspace_id,
            "analysis_job_id": item.get("analysis_job_id"),
            "source_type": str(item.get("source_type") or "inferred"),
            "source_id": item.get("source_id"),
            "topic": str(item.get("topic") or item.get("target_keyword") or item.get("title") or ""),
            "title": str(item.get("title") or item.get("topic") or "Untitled recommendation"),
            "target_keyword": str(item.get("target_keyword") or item.get("topic") or ""),
            "action": str(item.get("action") or "monitor"),
            "priority": str(item.get("priority") or "medium"),
            "confidence": _float_value(item.get("confidence"), 0.5),
            "score": _float_value(item.get("score"), 0.5),
            "business_relevance": _float_value(item.get("business_relevance"), 0.5),
            "niche_relevance": _float_value(item.get("niche_relevance"), 0.5),
            "trend_relevance": _float_value(item.get("trend_relevance"), 0.0),
            "coverage_gap": _float_value(item.get("coverage_gap"), 0.5),
            "freshness": _float_value(item.get("freshness"), 0.5),
            "audience_relevance": _float_value(item.get("audience_relevance"), 0.5),
            "competitor_gap": _float_value(item.get("competitor_gap"), 0.0),
            "cannibalization_risk": _float_value(item.get("cannibalization_risk"), 0.0),
            "reasons_json": _list_value(item.get("reasons")),
            "evidence_json": _list_value(item.get("evidence")),
            "related_opportunity_id": item.get("related_opportunity_id"),
            "related_content_id": item.get("related_content_id"),
            "trend_signal_id": item.get("trend_signal_id"),
            "coverage_id": item.get("coverage_id"),
            "status": str(item.get("status") or "active"),
            "metadata_json": metadata,
            "created_at": now,
            "updated_at": now,
        }

    def _parse(self, row: dict[str, Any]) -> dict[str, Any]:
        parsed = _parse_json_suffixes(row)
        metadata = parsed.get("metadata") if isinstance(parsed.get("metadata"), dict) else {}
        demand = metadata.get("demand_evidence") if isinstance(metadata.get("demand_evidence"), dict) else {}
        parsed["explanation"] = metadata.get("explanation") or ""
        parsed["demand_evidence"] = demand
        parsed["demand_score"] = demand.get("demand_score", 0.0)
        parsed["velocity_score"] = demand.get("velocity_score", 0.0)
        parsed["source_diversity"] = demand.get("source_diversity", 0.0)
        parsed["evidence_confidence"] = demand.get("evidence_confidence", 0.0)
        parsed["has_external_evidence"] = bool(demand.get("has_external_evidence"))
        parsed["demand_summary"] = str(demand.get("summary") or "")
        return parsed


class ManualRecommendationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(
        self,
        *,
        workspace_id: str,
        raw_headline: str,
        raw_notes: str = "",
        content_type_hint: str | None = None,
        target_audience_hint: str | None = None,
        selected_products: list[str] | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "source": "manual",
            "status": "draft",
            "raw_headline": raw_headline,
            "raw_notes": raw_notes,
            "enhanced_headline": None,
            "abstract": None,
            "search_intent": None,
            "content_type": content_type_hint,
            "recommendation_type": "create",
            "related_products_json": _list_value(selected_products or []),
            "related_topics_json": [],
            "target_audience": target_audience_hint,
            "priority_reason": None,
            "safety_notes_json": [],
            "enrichment_json": {},
            "duplicate_warnings_json": [],
            "recommendation_id": None,
            "created_by": created_by,
            "ai_enriched_at": None,
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.manual_recommendations).values(**row))
            await session.commit()
        return self._parse(row)

    async def get(self, manual_id: str, *, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.manual_recommendations).where(
                    models.manual_recommendations.c.id == manual_id,
                    models.manual_recommendations.c.workspace_id == workspace_id,
                )
            )
            row = result.mappings().first()
        return self._parse(_row_dict(row)) if row else None

    async def list_for_workspace(
        self,
        workspace_id: str,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = select(models.manual_recommendations).where(
            models.manual_recommendations.c.workspace_id == workspace_id,
        )
        if status:
            query = query.where(models.manual_recommendations.c.status == status)
        query = query.order_by(desc(models.manual_recommendations.c.created_at)).limit(max(1, min(limit, 500)))
        async with self.session_factory() as session:
            result = await session.execute(query)
            rows = result.mappings().all()
        return [self._parse(_row_dict(row)) for row in rows]

    async def update(self, manual_id: str, *, workspace_id: str, **fields: Any) -> dict[str, Any]:
        now = utc_now()
        updates: dict[str, Any] = {"updated_at": now}
        if fields.get("ai_enriched_at") is True:
            updates["ai_enriched_at"] = now
        mapping = {
            "status": "status",
            "enhanced_headline": "enhanced_headline",
            "abstract": "abstract",
            "search_intent": "search_intent",
            "content_type": "content_type",
            "recommendation_type": "recommendation_type",
            "target_audience": "target_audience",
            "priority_reason": "priority_reason",
            "recommendation_id": "recommendation_id",
        }
        for key, column in mapping.items():
            if key in fields and fields[key] is not None:
                updates[column] = fields[key]
        if "related_products" in fields:
            updates["related_products_json"] = _list_value(fields.get("related_products"))
        if "related_topics" in fields:
            updates["related_topics_json"] = _list_value(fields.get("related_topics"))
        if "safety_notes" in fields:
            updates["safety_notes_json"] = _list_value(fields.get("safety_notes"))
        if "enrichment_json" in fields:
            updates["enrichment_json"] = fields.get("enrichment_json") or {}
        if "duplicate_warnings_json" in fields:
            updates["duplicate_warnings_json"] = _list_value(fields.get("duplicate_warnings_json"))
        async with self.session_factory() as session:
            await session.execute(
                models.manual_recommendations.update()
                .where(
                    models.manual_recommendations.c.id == manual_id,
                    models.manual_recommendations.c.workspace_id == workspace_id,
                )
                .values(**updates)
            )
            await session.commit()
        manual = await self.get(manual_id, workspace_id=workspace_id)
        if not manual:
            raise ValueError("Manual recommendation not found after update.")
        return manual

    async def delete(self, manual_id: str, *, workspace_id: str) -> None:
        async with self.session_factory() as session:
            await session.execute(
                models.manual_recommendations.delete().where(
                    models.manual_recommendations.c.id == manual_id,
                    models.manual_recommendations.c.workspace_id == workspace_id,
                )
            )
            await session.commit()

    def _parse(self, row: dict[str, Any]) -> dict[str, Any]:
        parsed = _parse_json_suffixes(row)
        parsed["selected_products"] = list(parsed.get("related_products") or [])
        parsed["duplicate_warnings"] = list(parsed.get("duplicate_warnings") or [])
        if parsed.get("content_type") and not parsed.get("content_type_hint"):
            parsed["content_type_hint"] = parsed.get("content_type")
        return parsed


class DemandObservationRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_started(
        self,
        *,
        workspace_id: str,
        provider: str,
        source_type: str,
        date_start: str | None = None,
        date_end: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "provider": provider,
            "source_type": source_type,
            "status": "running",
            "started_at": now,
            "completed_at": None,
            "date_start": date_start,
            "date_end": date_end,
            "rows_fetched": 0,
            "rows_persisted": 0,
            "warnings_json": [],
            "error_message": None,
            "metadata_json": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.demand_observation_runs).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def mark_completed(
        self,
        run_id: str,
        *,
        rows_fetched: int,
        rows_persisted: int,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "completed",
    ) -> dict[str, Any] | None:
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                update(models.demand_observation_runs)
                .where(models.demand_observation_runs.c.id == run_id)
                .values(
                    status=status,
                    completed_at=now,
                    rows_fetched=max(0, rows_fetched),
                    rows_persisted=max(0, rows_persisted),
                    warnings_json=warnings or [],
                    metadata_json=metadata or {},
                    updated_at=now,
                )
            )
            await session.commit()
        return await self.get(run_id)

    async def mark_failed(
        self,
        run_id: str,
        *,
        error_message: str,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "failed",
    ) -> dict[str, Any] | None:
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                update(models.demand_observation_runs)
                .where(models.demand_observation_runs.c.id == run_id)
                .values(
                    status=status,
                    completed_at=now,
                    warnings_json=warnings or [],
                    error_message=error_message,
                    metadata_json=metadata or {},
                    updated_at=now,
                )
            )
            await session.commit()
        return await self.get(run_id)

    async def get(self, run_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.demand_observation_runs).where(models.demand_observation_runs.c.id == run_id)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def latest_for_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.demand_observation_runs)
                .where(models.demand_observation_runs.c.workspace_id == workspace_id)
                .order_by(desc(models.demand_observation_runs.c.created_at))
                .limit(1)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def list_for_workspace(self, workspace_id: str, limit: int = 25) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.demand_observation_runs)
                .where(models.demand_observation_runs.c.workspace_id == workspace_id)
                .order_by(desc(models.demand_observation_runs.c.created_at))
                .limit(max(1, min(limit, 100)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class DemandObservationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(self, workspace_id: str, run_id: str | None, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created = []
        async with self.session_factory() as session:
            for observation in observations:
                row = self._row(workspace_id, run_id, observation)
                await session.execute(insert(models.demand_observations).values(**row))
                created.append(_parse_json_suffixes(row))
            await session.commit()
        return created

    async def list_for_workspace(
        self,
        workspace_id: str,
        *,
        limit: int = 100,
        query: str | None = None,
        page_url: str | None = None,
        country: str | None = None,
        device: str | None = None,
        provider: str | None = None,
        min_impressions: float | None = None,
        min_opportunity_score: float | None = None,
    ) -> list[dict[str, Any]]:
        statement = select(models.demand_observations).where(models.demand_observations.c.workspace_id == workspace_id)
        if query:
            statement = statement.where(models.demand_observations.c.query == query)
        if page_url:
            statement = statement.where(models.demand_observations.c.page_url == page_url)
        if country:
            statement = statement.where(models.demand_observations.c.country == country)
        if device:
            statement = statement.where(models.demand_observations.c.device == device)
        if provider:
            statement = statement.where(models.demand_observations.c.provider == provider)
        if min_impressions is not None:
            statement = statement.where(models.demand_observations.c.impressions >= min_impressions)
        if min_opportunity_score is not None:
            statement = statement.where(models.demand_observations.c.normalized_opportunity_score >= min_opportunity_score)
        statement = statement.order_by(desc(models.demand_observations.c.normalized_opportunity_score)).limit(max(1, min(limit, 1000)))
        async with self.session_factory() as session:
            result = await session.execute(statement)
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    async def top_queries(self, workspace_id: str, limit: int = 25) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.demand_observations)
                .where(
                    models.demand_observations.c.workspace_id == workspace_id,
                    models.demand_observations.c.query.is_not(None),
                )
                .order_by(desc(models.demand_observations.c.impressions))
                .limit(max(1, min(limit, 100)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    async def top_opportunities(self, workspace_id: str, limit: int = 25) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.demand_observations)
                .where(models.demand_observations.c.workspace_id == workspace_id)
                .order_by(desc(models.demand_observations.c.normalized_opportunity_score))
                .limit(max(1, min(limit, 100)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    async def pages_with_low_ctr(self, workspace_id: str, limit: int = 25) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.demand_observations)
                .where(
                    models.demand_observations.c.workspace_id == workspace_id,
                    models.demand_observations.c.page_url.is_not(None),
                    models.demand_observations.c.impressions >= 25,
                    models.demand_observations.c.ctr <= 0.02,
                )
                .order_by(desc(models.demand_observations.c.impressions))
                .limit(max(1, min(limit, 100)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    async def observations_for_query(self, workspace_id: str, query: str, limit: int = 50) -> list[dict[str, Any]]:
        return await self.list_for_workspace(workspace_id, query=query, limit=limit)

    async def observations_for_page(self, workspace_id: str, page_url: str, limit: int = 50) -> list[dict[str, Any]]:
        return await self.list_for_workspace(workspace_id, page_url=page_url, limit=limit)

    def _row(self, workspace_id: str, run_id: str | None, observation: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(observation.get("id") or uuid4()),
            "workspace_id": workspace_id,
            "run_id": run_id,
            "provider": str(observation.get("provider") or "unknown"),
            "source_type": str(observation.get("source_type") or "unknown"),
            "observed_at": str(observation.get("observed_at") or utc_now()),
            "date_start": observation.get("date_start"),
            "date_end": observation.get("date_end"),
            "query": observation.get("query"),
            "page_url": observation.get("page_url"),
            "topic": observation.get("topic"),
            "entity": observation.get("entity"),
            "country": observation.get("country"),
            "device": observation.get("device"),
            "impressions": _metric_float(observation.get("impressions")),
            "clicks": _metric_float(observation.get("clicks")),
            "ctr": _metric_float(observation.get("ctr")),
            "position": _metric_float(observation.get("position")),
            "normalized_demand_score": _float_value(observation.get("normalized_demand_score"), 0.0),
            "normalized_opportunity_score": _float_value(observation.get("normalized_opportunity_score"), 0.0),
            "freshness_score": _float_value(observation.get("freshness_score"), 0.0),
            "confidence": _float_value(observation.get("confidence"), 0.0),
            "trend_signal_id": observation.get("trend_signal_id"),
            "opportunity_id": observation.get("opportunity_id"),
            "coverage_id": observation.get("coverage_id"),
            "published_content_id": observation.get("published_content_id"),
            "raw_payload_json": observation.get("raw_payload") or observation.get("raw_payload_json") or {},
            "created_at": utc_now(),
        }


class ConnectorEventRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create(self, event: dict[str, Any], workspace_id: str | None = None) -> dict[str, Any]:
        existing = await self.get(event.get("site_id", ""), event.get("event_id", ""))
        if existing:
            return existing
        row = {
            "id": str(uuid4()),
            "site_id": str(event.get("site_id") or ""),
            "event_id": str(event.get("event_id") or uuid4()),
            "event_type": str(event.get("event_type") or "unknown"),
            "workspace_id": workspace_id,
            "occurred_at": str(event.get("occurred_at") or utc_now()),
            "source": str(event.get("source") or "wordpress-plugin"),
            "post_json": event.get("post") or {},
            "payload_json": event.get("payload") or {},
            "created_at": utc_now(),
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.connector_events).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def get(self, site_id: str, event_id: str) -> dict[str, Any] | None:
        if not site_id or not event_id:
            return None
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.connector_events).where(
                    models.connector_events.c.site_id == site_id,
                    models.connector_events.c.event_id == event_id,
                )
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def list_recent(self, workspace_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = select(models.connector_events)
        if workspace_id:
            query = query.where(models.connector_events.c.workspace_id == workspace_id)
        query = query.order_by(desc(models.connector_events.c.created_at)).limit(max(1, min(limit, 500)))
        async with self.session_factory() as session:
            result = await session.execute(query)
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class MarketIntelligenceRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_started(
        self,
        *,
        workspace_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "status": "running",
            "started_at": now,
            "completed_at": None,
            "signals_fetched": 0,
            "signals_persisted": 0,
            "clusters_created": 0,
            "candidates_created": 0,
            "warnings_json": [],
            "error_message": None,
            "metadata_json": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.market_intelligence_runs).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def mark_completed(
        self,
        run_id: str,
        *,
        signals_fetched: int,
        signals_persisted: int,
        clusters_created: int,
        candidates_created: int,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "completed",
    ) -> dict[str, Any] | None:
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                update(models.market_intelligence_runs)
                .where(models.market_intelligence_runs.c.id == run_id)
                .values(
                    status=status,
                    completed_at=now,
                    signals_fetched=max(0, signals_fetched),
                    signals_persisted=max(0, signals_persisted),
                    clusters_created=max(0, clusters_created),
                    candidates_created=max(0, candidates_created),
                    warnings_json=warnings or [],
                    metadata_json=metadata or {},
                    updated_at=now,
                )
            )
            await session.commit()
        return await self.get(run_id)

    async def mark_failed(
        self,
        run_id: str,
        *,
        error_message: str,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "failed",
    ) -> dict[str, Any] | None:
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                update(models.market_intelligence_runs)
                .where(models.market_intelligence_runs.c.id == run_id)
                .values(
                    status=status,
                    completed_at=now,
                    warnings_json=warnings or [],
                    error_message=error_message,
                    metadata_json=metadata or {},
                    updated_at=now,
                )
            )
            await session.commit()
        return await self.get(run_id)

    async def get(self, run_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.market_intelligence_runs).where(models.market_intelligence_runs.c.id == run_id)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def latest_for_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.market_intelligence_runs)
                .where(models.market_intelligence_runs.c.workspace_id == workspace_id)
                .order_by(desc(models.market_intelligence_runs.c.created_at))
                .limit(1)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def list_for_workspace(self, workspace_id: str, limit: int = 25) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.market_intelligence_runs)
                .where(models.market_intelligence_runs.c.workspace_id == workspace_id)
                .order_by(desc(models.market_intelligence_runs.c.created_at))
                .limit(max(1, min(limit, 100)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class MarketSignalRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(self, workspace_id: str, run_id: str, drafts: list[Any]) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        async with self.session_factory() as session:
            for draft in drafts:
                signal_id = str(uuid4())
                now = utc_now()
                row = {
                    "id": signal_id,
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "provider": _draft_field(draft, "provider"),
                    "source": _draft_field(draft, "source"),
                    "signal_type": _draft_field(draft, "signal_type"),
                    "topic": _draft_field(draft, "topic"),
                    "entity": _draft_field(draft, "entity"),
                    "audience": _draft_field(draft, "audience"),
                    "market_scope": _draft_field(draft, "market_scope"),
                    "language": _draft_field(draft, "language"),
                    "country": _draft_field(draft, "country"),
                    "confidence": _draft_field(draft, "confidence"),
                    "freshness": _draft_field(draft, "freshness"),
                    "velocity": _draft_field(draft, "velocity"),
                    "novelty": _draft_field(draft, "novelty"),
                    "relevance": _draft_field(draft, "relevance"),
                    "evidence_count": _draft_field(draft, "evidence_count") or 1,
                    "source_url": _draft_field(draft, "source_url"),
                    "observed_at": _draft_field(draft, "observed_at") or now,
                    "raw_payload_json": _draft_field(draft, "raw_payload") or {},
                    "created_at": now,
                }
                await session.execute(insert(models.market_signals).values(**row))
                evidence_items = _draft_field(draft, "evidence") or []
                for evidence in evidence_items:
                    evidence_row = {
                        "id": str(uuid4()),
                        "signal_id": signal_id,
                        "evidence_type": _draft_field(evidence, "evidence_type"),
                        "title": _draft_field(evidence, "title"),
                        "url": _draft_field(evidence, "url"),
                        "snippet": _draft_field(evidence, "snippet"),
                        "source_name": _draft_field(evidence, "source_name"),
                        "published_at": _draft_field(evidence, "published_at"),
                        "metric_name": _draft_field(evidence, "metric_name"),
                        "metric_value": _draft_field(evidence, "metric_value"),
                        "confidence": _draft_field(evidence, "confidence"),
                        "raw_payload_json": _draft_field(evidence, "raw_payload") or {},
                        "created_at": now,
                    }
                    await session.execute(insert(models.market_signal_evidence).values(**evidence_row))
                created.append(_parse_json_suffixes(row))
            await session.commit()
        return created

    async def list_for_workspace(self, workspace_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.market_signals)
                .where(models.market_signals.c.workspace_id == workspace_id)
                .order_by(desc(models.market_signals.c.relevance), desc(models.market_signals.c.confidence))
                .limit(max(1, min(limit, 1000)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class MarketTopicClusterRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(self, workspace_id: str, run_id: str, clusters: list[Any]) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        async with self.session_factory() as session:
            for cluster in clusters:
                now = utc_now()
                row = {
                    "id": str(uuid4()),
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "topic": _draft_field(cluster, "topic"),
                    "entities_json": _draft_field(cluster, "entities") or [],
                    "audiences_json": _draft_field(cluster, "audiences") or [],
                    "dominant_intents_json": _draft_field(cluster, "dominant_intents") or [],
                    "source_mix_json": _draft_field(cluster, "source_mix") or {},
                    "confidence": _draft_field(cluster, "confidence"),
                    "freshness": _draft_field(cluster, "freshness"),
                    "velocity": _draft_field(cluster, "velocity"),
                    "novelty": _draft_field(cluster, "novelty"),
                    "relevance": _draft_field(cluster, "relevance"),
                    "saturation": _draft_field(cluster, "saturation"),
                    "opportunity_score": _draft_field(cluster, "opportunity_score"),
                    "signal_ids_json": _draft_field(cluster, "signal_ids") or [],
                    "metadata_json": _draft_field(cluster, "metadata") or {},
                    "created_at": now,
                }
                await session.execute(insert(models.market_topic_clusters).values(**row))
                created.append(_parse_json_suffixes(row))
            await session.commit()
        return created

    async def top_for_workspace(self, workspace_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.market_topic_clusters)
                .where(models.market_topic_clusters.c.workspace_id == workspace_id)
                .order_by(desc(models.market_topic_clusters.c.opportunity_score))
                .limit(max(1, min(limit, 200)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class EditorialGenerationRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_started(
        self,
        *,
        workspace_id: str,
        market_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "market_run_id": market_run_id,
            "status": "running",
            "started_at": now,
            "completed_at": None,
            "seeds_processed": 0,
            "concepts_created": 0,
            "finalists_created": 0,
            "warnings_json": [],
            "error_message": None,
            "metadata_json": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.editorial_generation_runs).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def mark_completed(
        self,
        run_id: str,
        *,
        seeds_processed: int,
        concepts_created: int,
        finalists_created: int,
        warnings: list[str] | None = None,
        status: str = "completed",
    ) -> dict[str, Any] | None:
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                update(models.editorial_generation_runs)
                .where(models.editorial_generation_runs.c.id == run_id)
                .values(
                    status=status,
                    completed_at=now,
                    seeds_processed=max(0, seeds_processed),
                    concepts_created=max(0, concepts_created),
                    finalists_created=max(0, finalists_created),
                    warnings_json=warnings or [],
                    updated_at=now,
                )
            )
            await session.commit()
        return await self.get(run_id)

    async def mark_failed(
        self,
        run_id: str,
        *,
        error_message: str,
        warnings: list[str] | None = None,
    ) -> dict[str, Any] | None:
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                update(models.editorial_generation_runs)
                .where(models.editorial_generation_runs.c.id == run_id)
                .values(
                    status="failed",
                    completed_at=now,
                    error_message=error_message,
                    warnings_json=warnings or [],
                    updated_at=now,
                )
            )
            await session.commit()
        return await self.get(run_id)

    async def get(self, run_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.editorial_generation_runs).where(models.editorial_generation_runs.c.id == run_id)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def latest_for_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.editorial_generation_runs)
                .where(models.editorial_generation_runs.c.workspace_id == workspace_id)
                .order_by(desc(models.editorial_generation_runs.c.created_at))
                .limit(1)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None


class EditorialOpportunityConceptRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def replace_for_run(
        self,
        workspace_id: str,
        run_id: str,
        drafts: list[Any],
    ) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        async with self.session_factory() as session:
            for draft in drafts:
                now = utc_now()
                row = {
                    "id": str(uuid4()),
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "seed_candidate_id": _draft_field(draft, "seed_candidate_id"),
                    "cluster_id": _draft_field(draft, "cluster_id"),
                    "title": _draft_field(draft, "title"),
                    "topic": _draft_field(draft, "topic"),
                    "content_type": _draft_field(draft, "content_type"),
                    "audience": _draft_field(draft, "audience"),
                    "intent": _draft_field(draft, "intent"),
                    "angle": _draft_field(draft, "angle"),
                    "confidence": _draft_field(draft, "confidence"),
                    "novelty": _draft_field(draft, "novelty"),
                    "authority_value": _draft_field(draft, "authority_value"),
                    "evidence_summary": _draft_field(draft, "evidence_summary"),
                    "source_signal_ids_json": _draft_field(draft, "source_signal_ids") or [],
                    "target_keyword": _draft_field(draft, "target_keyword"),
                    "action_hint": _draft_field(draft, "action_hint") or "create",
                    "related_content_ids_json": _draft_field(draft, "related_content_ids") or [],
                    "is_finalist": 1 if _draft_field(draft, "is_finalist") else 0,
                    "metadata_json": _draft_field(draft, "metadata") or {},
                    "created_at": now,
                }
                await session.execute(insert(models.editorial_opportunity_concepts).values(**row))
                created.append(_parse_json_suffixes(row))
            await session.commit()
        return created

    async def list_for_workspace(self, workspace_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.editorial_opportunity_concepts)
                .where(models.editorial_opportunity_concepts.c.workspace_id == workspace_id)
                .order_by(desc(models.editorial_opportunity_concepts.c.confidence))
                .limit(max(1, min(limit, 500)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    async def list_finalists_for_workspace(self, workspace_id: str, *, limit: int = 120) -> list[dict[str, Any]]:
        latest_run_id = None
        latest = await EditorialGenerationRunRepository(self.session_factory).latest_for_workspace(workspace_id)
        if latest:
            latest_run_id = latest.get("id")
        async with self.session_factory() as session:
            statement = select(models.editorial_opportunity_concepts).where(
                models.editorial_opportunity_concepts.c.workspace_id == workspace_id,
                models.editorial_opportunity_concepts.c.is_finalist == 1,
            )
            if latest_run_id:
                statement = statement.where(models.editorial_opportunity_concepts.c.run_id == latest_run_id)
            result = await session.execute(
                statement.order_by(
                    desc(models.editorial_opportunity_concepts.c.authority_value),
                    desc(models.editorial_opportunity_concepts.c.confidence),
                ).limit(max(1, min(limit, 300)))
            )
            rows = result.mappings().all()
        parsed = [_parse_json_suffixes(_row_dict(row)) for row in rows]
        for row in parsed:
            row["is_finalist"] = bool(row.get("is_finalist"))
            row["source_signal_ids"] = row.get("source_signal_ids") or []
        return parsed


class AIEditorialStrategistRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_started(self, *, workspace_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "status": "running",
            "started_at": now,
            "completed_at": None,
            "ideas_created": 0,
            "warnings_json": [],
            "error_message": None,
            "metadata_json": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.ai_editorial_strategist_runs).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def mark_completed(
        self,
        run_id: str,
        *,
        ideas_created: int,
        warnings: list[str] | None = None,
        status: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        now = utc_now()
        values: dict[str, Any] = {
            "status": status,
            "completed_at": now,
            "ideas_created": max(0, ideas_created),
            "warnings_json": warnings or [],
            "updated_at": now,
        }
        if metadata is not None:
            values["metadata_json"] = metadata
        async with self.session_factory() as session:
            await session.execute(
                update(models.ai_editorial_strategist_runs)
                .where(models.ai_editorial_strategist_runs.c.id == run_id)
                .values(**values)
            )
            await session.commit()
        return await self.get(run_id)

    async def mark_failed(self, run_id: str, *, error_message: str, warnings: list[str] | None = None) -> dict[str, Any] | None:
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                update(models.ai_editorial_strategist_runs)
                .where(models.ai_editorial_strategist_runs.c.id == run_id)
                .values(
                    status="failed",
                    completed_at=now,
                    error_message=error_message,
                    warnings_json=warnings or [],
                    updated_at=now,
                )
            )
            await session.commit()
        return await self.get(run_id)

    async def get(self, run_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.ai_editorial_strategist_runs).where(models.ai_editorial_strategist_runs.c.id == run_id)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def latest_for_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.ai_editorial_strategist_runs)
                .where(models.ai_editorial_strategist_runs.c.workspace_id == workspace_id)
                .order_by(desc(models.ai_editorial_strategist_runs.c.created_at))
                .limit(1)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None


class AIEditorialStrategistIdeaRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def replace_for_run(self, workspace_id: str, run_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            await session.execute(
                delete(models.ai_editorial_strategist_ideas).where(
                    models.ai_editorial_strategist_ideas.c.run_id == run_id
                )
            )
            created: list[dict[str, Any]] = []
            for row in rows:
                await session.execute(insert(models.ai_editorial_strategist_ideas).values(**row))
                created.append(_parse_json_suffixes(row))
            await session.commit()
        return created

    async def list_for_workspace(self, workspace_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.ai_editorial_strategist_ideas)
                .where(models.ai_editorial_strategist_ideas.c.workspace_id == workspace_id)
                .order_by(desc(models.ai_editorial_strategist_ideas.c.created_at))
                .limit(max(1, min(limit, 500)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class AIOpportunityIdeationRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_started(self, *, workspace_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "status": "running",
            "started_at": now,
            "completed_at": None,
            "opportunities_created": 0,
            "warnings_json": [],
            "error_message": None,
            "metadata_json": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.ai_opportunity_ideation_runs).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def mark_completed(
        self,
        run_id: str,
        *,
        opportunities_created: int,
        warnings: list[str] | None = None,
        status: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        now = utc_now()
        values: dict[str, Any] = {
            "status": status,
            "completed_at": now,
            "opportunities_created": max(0, opportunities_created),
            "warnings_json": warnings or [],
            "updated_at": now,
        }
        if metadata is not None:
            values["metadata_json"] = metadata
        async with self.session_factory() as session:
            await session.execute(
                update(models.ai_opportunity_ideation_runs)
                .where(models.ai_opportunity_ideation_runs.c.id == run_id)
                .values(**values)
            )
            await session.commit()
        return await self.get(run_id)

    async def mark_failed(self, run_id: str, *, error_message: str, warnings: list[str] | None = None) -> dict[str, Any] | None:
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                update(models.ai_opportunity_ideation_runs)
                .where(models.ai_opportunity_ideation_runs.c.id == run_id)
                .values(
                    status="failed",
                    completed_at=now,
                    error_message=error_message,
                    warnings_json=warnings or [],
                    updated_at=now,
                )
            )
            await session.commit()
        return await self.get(run_id)

    async def get(self, run_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.ai_opportunity_ideation_runs).where(models.ai_opportunity_ideation_runs.c.id == run_id)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def latest_completed_for_cache(
        self,
        workspace_id: str,
        *,
        brief_cache_key: str,
        ttl_hours: int,
    ) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.ai_opportunity_ideation_runs)
                .where(models.ai_opportunity_ideation_runs.c.workspace_id == workspace_id)
                .where(models.ai_opportunity_ideation_runs.c.status == "completed")
                .order_by(desc(models.ai_opportunity_ideation_runs.c.completed_at))
                .limit(10)
            )
            rows = result.mappings().all()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, ttl_hours))
        for row in rows:
            parsed = _parse_json_suffixes(_row_dict(row))
            meta = parsed.get("metadata") if isinstance(parsed.get("metadata"), dict) else {}
            if str(meta.get("brief_cache_key") or "") != brief_cache_key:
                continue
            completed_at = parsed.get("completed_at")
            if not completed_at:
                continue
            try:
                completed_dt = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
                if completed_dt.tzinfo is None:
                    completed_dt = completed_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if completed_dt >= cutoff:
                return parsed
        return None


class AIOpportunityIdeationOpportunityRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def replace_for_run(
        self,
        workspace_id: str,
        run_id: str,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            await session.execute(
                delete(models.ai_opportunity_ideation_opportunities).where(
                    models.ai_opportunity_ideation_opportunities.c.run_id == run_id
                )
            )
            created: list[dict[str, Any]] = []
            for row in rows:
                await session.execute(insert(models.ai_opportunity_ideation_opportunities).values(**row))
                created.append(_parse_json_suffixes(row))
            await session.commit()
        return created

    async def list_for_run(self, run_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.ai_opportunity_ideation_opportunities)
                .where(models.ai_opportunity_ideation_opportunities.c.run_id == run_id)
                .order_by(models.ai_opportunity_ideation_opportunities.c.created_at)
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    async def list_for_workspace(self, workspace_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.ai_opportunity_ideation_opportunities)
                .where(models.ai_opportunity_ideation_opportunities.c.workspace_id == workspace_id)
                .order_by(desc(models.ai_opportunity_ideation_opportunities.c.created_at))
                .limit(max(1, min(limit, 500)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class AIRecommendationReviewRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_started(self, *, workspace_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": str(uuid4()),
            "workspace_id": workspace_id,
            "status": "running",
            "started_at": now,
            "completed_at": None,
            "items_reviewed": 0,
            "warnings_json": [],
            "error_message": None,
            "metadata_json": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.ai_recommendation_review_runs).values(**row))
            await session.commit()
        return _parse_json_suffixes(row)

    async def mark_completed(
        self,
        run_id: str,
        *,
        items_reviewed: int,
        warnings: list[str] | None = None,
        status: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        now = utc_now()
        values: dict[str, Any] = {
            "status": status,
            "completed_at": now,
            "items_reviewed": max(0, items_reviewed),
            "warnings_json": warnings or [],
            "updated_at": now,
        }
        if metadata is not None:
            values["metadata_json"] = metadata
        async with self.session_factory() as session:
            await session.execute(
                update(models.ai_recommendation_review_runs)
                .where(models.ai_recommendation_review_runs.c.id == run_id)
                .values(**values)
            )
            await session.commit()
        return await self.get(run_id)

    async def mark_failed(self, run_id: str, *, error_message: str, warnings: list[str] | None = None) -> dict[str, Any] | None:
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                update(models.ai_recommendation_review_runs)
                .where(models.ai_recommendation_review_runs.c.id == run_id)
                .values(
                    status="failed",
                    completed_at=now,
                    error_message=error_message,
                    warnings_json=warnings or [],
                    updated_at=now,
                )
            )
            await session.commit()
        return await self.get(run_id)

    async def get(self, run_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.ai_recommendation_review_runs).where(models.ai_recommendation_review_runs.c.id == run_id)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def latest_for_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.ai_recommendation_review_runs)
                .where(models.ai_recommendation_review_runs.c.workspace_id == workspace_id)
                .order_by(desc(models.ai_recommendation_review_runs.c.created_at))
                .limit(1)
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None


class AIRecommendationReviewRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def replace_for_run(self, workspace_id: str, run_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            await session.execute(
                delete(models.ai_recommendation_reviews).where(models.ai_recommendation_reviews.c.run_id == run_id)
            )
            created: list[dict[str, Any]] = []
            for row in rows:
                await session.execute(insert(models.ai_recommendation_reviews).values(**row))
                created.append(_parse_json_suffixes(row))
            await session.commit()
        return created


class MarketOpportunityCandidateRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_many(
        self,
        workspace_id: str,
        run_id: str,
        drafts: list[Any],
        *,
        cluster_ids: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        cluster_ids = cluster_ids or {}
        created: list[dict[str, Any]] = []
        async with self.session_factory() as session:
            for draft in drafts:
                now = utc_now()
                topic = str(_draft_field(draft, "topic") or "")
                metadata = _draft_field(draft, "metadata") or {}
                cluster_id = (metadata.get("cluster_id") if isinstance(metadata, dict) else None) or cluster_ids.get(topic.lower())
                row = {
                    "id": str(uuid4()),
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "cluster_id": cluster_id,
                    "title": _draft_field(draft, "title"),
                    "topic": topic,
                    "target_keyword": _draft_field(draft, "target_keyword"),
                    "content_format": _draft_field(draft, "content_format"),
                    "editorial_angle": _draft_field(draft, "editorial_angle"),
                    "audience": _draft_field(draft, "audience"),
                    "intent": _draft_field(draft, "intent"),
                    "action_hint": _draft_field(draft, "action_hint") or "create",
                    "confidence": _draft_field(draft, "confidence"),
                    "evidence_summary": _draft_field(draft, "evidence_summary"),
                    "source_signal_ids_json": _draft_field(draft, "source_signal_ids") or [],
                    "risk_json": _draft_field(draft, "risk") or {},
                    "metadata_json": metadata if isinstance(metadata, dict) else {},
                    "created_at": now,
                }
                await session.execute(insert(models.market_opportunity_candidates).values(**row))
                created.append(_parse_json_suffixes(row))
            await session.commit()
        return created

    async def list_for_workspace(self, workspace_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.market_opportunity_candidates)
                .where(models.market_opportunity_candidates.c.workspace_id == workspace_id)
                .order_by(desc(models.market_opportunity_candidates.c.confidence))
                .limit(max(1, min(limit, 500)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]

    async def top_for_workspace(self, workspace_id: str, *, limit: int = 15) -> list[dict[str, Any]]:
        return await self.list_for_workspace(workspace_id, limit=limit)


class WorkspaceContentInventoryRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def upsert_page(self, workspace_id: str, item: dict[str, Any]) -> dict[str, Any]:
        canonical = str(item.get("canonical_url") or item.get("url") or "").strip()
        if not canonical:
            raise ValueError("Content inventory item requires canonical_url or url.")
        now = utc_now()
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.workspace_content_inventory).where(
                    models.workspace_content_inventory.c.workspace_id == workspace_id,
                    models.workspace_content_inventory.c.canonical_url == canonical,
                )
            )
            existing = result.mappings().first()
            values = {
                "url": str(item.get("url") or canonical),
                "canonical_url": canonical,
                "title": str(item.get("title") or ""),
                "slug": str(item.get("slug") or ""),
                "content_type": str(item.get("content_type") or "unknown"),
                "source": str(item.get("source") or "existing_site"),
                "wordpress_post_id": item.get("wordpress_post_id"),
                "created_by_trendplot": bool(item.get("created_by_trendplot")),
                "generated_job_id": item.get("generated_job_id"),
                "published_at": item.get("published_at"),
                "last_seen_at": now,
                "topic_fingerprint": str(item.get("topic_fingerprint") or ""),
                "coverage_topics_json": _list_value(item.get("coverage_topics")),
                "metadata_json": item.get("metadata") or {},
                "updated_at": now,
            }
            if existing:
                row_id = existing["id"]
                if existing["created_by_trendplot"] and not values["created_by_trendplot"]:
                    values["created_by_trendplot"] = True
                    values["source"] = str(item.get("source") or "trendplot_generated")
                await session.execute(
                    update(models.workspace_content_inventory)
                    .where(models.workspace_content_inventory.c.id == row_id)
                    .values(**values)
                )
            else:
                row_id = str(uuid4())
                await session.execute(
                    insert(models.workspace_content_inventory).values(
                        id=row_id,
                        workspace_id=workspace_id,
                        created_at=now,
                        **values,
                    )
                )
            await session.commit()
        return await self.get_by_canonical(workspace_id, canonical) or {"id": row_id, "workspace_id": workspace_id, **values}

    async def upsert_pages(self, workspace_id: str, pages: list[dict[str, Any]]) -> int:
        count = 0
        for page in pages:
            if not isinstance(page, dict):
                continue
            if str(page.get("status") or "") == "error":
                continue
            await self.upsert_page(workspace_id, page)
            count += 1
        return count

    async def get_by_canonical(self, workspace_id: str, canonical_url: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.workspace_content_inventory).where(
                    models.workspace_content_inventory.c.workspace_id == workspace_id,
                    models.workspace_content_inventory.c.canonical_url == canonical_url,
                )
            )
            row = result.mappings().first()
        return _parse_json_suffixes(_row_dict(row)) if row else None

    async def list_for_workspace(self, workspace_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.workspace_content_inventory)
                .where(models.workspace_content_inventory.c.workspace_id == workspace_id)
                .order_by(desc(models.workspace_content_inventory.c.last_seen_at))
                .limit(max(1, min(limit, 1000)))
            )
            rows = result.mappings().all()
        return [_parse_json_suffixes(_row_dict(row)) for row in rows]


class WorkspaceWordPressConnectorRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def get(self, workspace_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.workspace_wordpress_connector).where(
                    models.workspace_wordpress_connector.c.workspace_id == workspace_id,
                )
            )
            row = result.mappings().first()
        return _row_dict(row) if row else None

    async def upsert(self, workspace_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        existing = await self.get(workspace_id)
        allowed = {
            "connector_enabled",
            "wordpress_base_url",
            "trendplot_site_id",
            "trendplot_shared_secret",
            "last_connection_status",
            "last_connection_checked_at",
            "last_connection_error",
            "connector_plugin_version",
            "connector_api_version",
            "active_environment",
            "environments_json",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if existing:
            if not updates:
                return existing
            updates["updated_at"] = now
            async with self.session_factory() as session:
                await session.execute(
                    update(models.workspace_wordpress_connector)
                    .where(models.workspace_wordpress_connector.c.workspace_id == workspace_id)
                    .values(**updates)
                )
                await session.commit()
            return await self.get(workspace_id) or existing
        row = {
            "workspace_id": workspace_id,
            "connector_enabled": bool(updates.get("connector_enabled", False)),
            "wordpress_base_url": updates.get("wordpress_base_url"),
            "trendplot_site_id": updates.get("trendplot_site_id"),
            "trendplot_shared_secret": updates.get("trendplot_shared_secret"),
            "last_connection_status": updates.get("last_connection_status"),
            "last_connection_checked_at": updates.get("last_connection_checked_at"),
            "last_connection_error": updates.get("last_connection_error"),
            "connector_plugin_version": updates.get("connector_plugin_version"),
            "connector_api_version": updates.get("connector_api_version"),
            "active_environment": updates.get("active_environment") or "staging",
            "environments_json": updates.get("environments_json"),
            "created_at": now,
            "updated_at": now,
        }
        async with self.session_factory() as session:
            await session.execute(insert(models.workspace_wordpress_connector).values(**row))
            await session.commit()
        return await self.get(workspace_id) or row


class AnalyzeFlowRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def upsert(self, state: dict[str, Any]) -> dict[str, Any]:
        job_id = str(state.get("job_id") or "")
        if not job_id:
            raise ValueError("Analyze flow run requires job_id.")
        now = utc_now()
        row = {
            "id": job_id,
            "workspace_id": state.get("workspace_id"),
            "parent_run_id": state.get("parent_run_id"),
            "rerun_type": state.get("rerun_type"),
            "website_url": str(state.get("website_url") or ""),
            "run_label": state.get("run_label"),
            "overall_status": str(state.get("overall_status") or "queued"),
            "state_json": state,
            "request_json": state.get("request_payload") or {},
            "updated_at": now,
            "completed_at": now if state.get("overall_status") in {"succeeded", "failed", "warning"} else None,
        }
        async with self.session_factory() as session:
            existing = await session.execute(
                select(models.analyze_flow_runs).where(models.analyze_flow_runs.c.id == job_id)
            )
            if existing.mappings().first():
                await session.execute(
                    update(models.analyze_flow_runs).where(models.analyze_flow_runs.c.id == job_id).values(**row)
                )
            else:
                row["created_at"] = now
                await session.execute(insert(models.analyze_flow_runs).values(**row))
            await session.commit()
        return row

    async def get(self, job_id: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.analyze_flow_runs).where(models.analyze_flow_runs.c.id == job_id)
            )
            row = result.mappings().first()
        if not row:
            return None
        payload = _row_dict(row)
        state = _load_json(payload.get("state_json"), {})
        if isinstance(state, dict):
            return state
        return None

    async def list_recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(models.analyze_flow_runs)
                .order_by(desc(models.analyze_flow_runs.c.created_at))
                .limit(max(1, min(limit, 50)))
            )
            rows = result.mappings().all()
        summaries = []
        for row in rows:
            payload = _row_dict(row)
            state = _load_json(payload.get("state_json"), {}) or {}
            summary = state.get("summary") if isinstance(state, dict) else {}
            recs = (summary or {}).get("recommendations") or {}
            site = (summary or {}).get("site") or {}
            competitor_discovery = (summary or {}).get("competitor_discovery") or {}
            summaries.append(
                {
                    "job_id": payload.get("id"),
                    "workspace_id": payload.get("workspace_id"),
                    "parent_run_id": payload.get("parent_run_id"),
                    "rerun_type": payload.get("rerun_type"),
                    "website_url": payload.get("website_url"),
                    "run_label": payload.get("run_label") or (summary or {}).get("workspace", {}).get("name"),
                    "overall_status": payload.get("overall_status"),
                    "created_at": payload.get("created_at"),
                    "completed_at": payload.get("completed_at"),
                    "pages_analyzed": site.get("pages_analyzed"),
                    "recommendations_total": recs.get("total"),
                    "competitors_selected": competitor_discovery.get("selected_count")
                    or competitor_discovery.get("competitors_selected"),
                }
            )
        return summaries

    async def delete(self, job_id: str) -> bool:
        async with self.session_factory() as session:
            result = await session.execute(
                delete(models.analyze_flow_runs).where(models.analyze_flow_runs.c.id == job_id)
            )
            await session.commit()
        return bool(result.rowcount)


class Repositories:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.jobs = JobRepository(session_factory)
        self.artifacts = ArtifactRepository(session_factory)
        self.logs = JobLogRepository(session_factory)
        self.analysis_jobs = AnalysisJobRepository(session_factory)
        self.analysis_pages = AnalysisPageRepository(session_factory)
        self.analysis_suggestions = AnalysisSuggestionRepository(session_factory)
        self.analysis_intelligence_artifacts = AnalysisIntelligenceArtifactRepository(session_factory)
        self.autopilot_workspaces = AutopilotWorkspaceRepository(session_factory)
        self.workspace_connections = WorkspaceConnectionRepository(session_factory)
        self.site_understanding = SiteUnderstandingRepository(session_factory)
        self.workspace_niche_profiles = WorkspaceNicheProfileRepository(session_factory)
        self.content_plans = ContentPlanRepository(session_factory)
        self.content_plan_items = ContentPlanItemRepository(session_factory)
        self.published_content = PublishedContentRepository(session_factory)
        self.reassessment_runs = ReassessmentRunRepository(session_factory)
        self.provider_status = ProviderStatusRepository(session_factory)
        self.approval_events = ApprovalEventRepository(session_factory)
        self.opportunity_recommendations = OpportunityRecommendationRepository(session_factory)
        self.manual_recommendations = ManualRecommendationRepository(session_factory)
        self.ai_opportunity_ideation_runs = AIOpportunityIdeationRunRepository(session_factory)
        self.ai_opportunity_ideation_opportunities = AIOpportunityIdeationOpportunityRepository(session_factory)
        self.connector_events = ConnectorEventRepository(session_factory)
        self.analyze_flow_runs = AnalyzeFlowRunRepository(session_factory)
        self.workspace_content_inventory = WorkspaceContentInventoryRepository(session_factory)
        self.workspace_wordpress_connector = WorkspaceWordPressConnectorRepository(session_factory)


def _draft_field(draft: Any, name: str, default: Any = None) -> Any:
    if isinstance(draft, dict):
        return draft.get(name, default)
    return getattr(draft, name, default)


def _metric_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _float_value(value: Any, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    if numeric > 1:
        numeric = numeric / 100
    return max(0.0, min(1.0, numeric))


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [value]


def _parse_json_suffixes(row: dict[str, Any]) -> dict[str, Any]:
    parsed = dict(row)
    for key in list(parsed.keys()):
        if not key.endswith("_json"):
            continue
        parsed[key[:-5]] = _load_json(parsed.pop(key), [])
    return parsed


def _scoped_authority_node_id(analysis_job_id: str, node_id: Any) -> str:
    raw_id = str(node_id or uuid4())
    prefix = f"{analysis_job_id}:"
    if raw_id.startswith(prefix):
        return raw_id
    return f"{prefix}{raw_id}"


def _workspace_name_from_url(url: str) -> str:
    cleaned = str(url or "").replace("https://", "").replace("http://", "").strip("/")
    domain = cleaned.split("/", 1)[0] if cleaned else "Trendplot Workspace"
    return domain or "Trendplot Workspace"
