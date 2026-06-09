from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from app.config import Settings
from app.connectors.phase1_client import Phase1ConnectorError, TrendplotPhase1ConnectorClient
from app.prompts import build_seo_package_prompt
from app.providers.base import GeneratedContent
from app.repositories import Repositories
from app.wordpress_connector.seo import (
    apply_focus_keyword_strategy,
    job_seo_snapshot,
    normalize_connector_seo_payload,
    normalize_seo_package_payload,
    parse_llm_json_payload,
    sanitize_seo_save_fields,
    seo_fields_for_connector,
    seo_package_response,
    validate_seo_fields,
)
from app.wordpress_connector.slug import evaluate_slug_sync, slug_from_public_url

logger = logging.getLogger("trendplot.wordpress_connector")

ConnectorEnvironment = Literal["staging", "production"]
CONNECTOR_ENVIRONMENTS: tuple[ConnectorEnvironment, ...] = ("staging", "production")
ENVIRONMENT_LABELS: dict[ConnectorEnvironment, str] = {
    "staging": "Staging",
    "production": "Production",
}
WORDPRESS_EDITABLE_STATUSES = frozenset({"draft", "pending", "future", ""})
WORDPRESS_PUBLISHED_STATUSES = frozenset({"publish", "published", "private"})
_CONNECTOR_ERROR_CODES: dict[str, str] = {
    "not_found": "missing_draft",
    "post_not_found": "missing_draft",
    "not_trendplot_draft": "not_trendplot_draft",
    "forbidden": "not_trendplot_draft",
    "published_post_rejected": "published_post_rejected",
    "unauthorized": "auth_failed",
    "validation_failed": "validation_error",
}


class WordPressConnectorService:
    def __init__(self, settings: Settings, repositories: Repositories, job_service: Any | None = None) -> None:
        self.settings = settings
        self.repositories = repositories
        self.job_service = job_service

    async def get_settings(self, workspace_id: str) -> dict[str, Any]:
        await self._workspace(workspace_id)
        row = await self._connector_row(workspace_id)
        return self._public_settings(row)

    async def save_settings(
        self,
        workspace_id: str,
        *,
        connector_enabled: bool | None = None,
        active_environment: str | None = None,
        environment: str | None = None,
        wordpress_base_url: str | None = None,
        trendplot_site_id: str | None = None,
        trendplot_shared_secret: str | None = None,
        environments: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        await self._workspace(workspace_id)
        row = await self._connector_row(workspace_id)
        envs = self._parse_environments(row)
        target_env = self._normalize_environment(environment) or self._active_environment(row, envs)

        if environments:
            for env_name, payload in environments.items():
                normalized = self._normalize_environment(env_name)
                if not normalized or not isinstance(payload, dict):
                    continue
                envs[normalized] = self._merge_environment_profile(envs[normalized], payload)

        credential_updates = {
            "wordpress_base_url": wordpress_base_url,
            "trendplot_site_id": trendplot_site_id,
            "trendplot_shared_secret": trendplot_shared_secret,
        }
        if any(value is not None for value in credential_updates.values()):
            envs[target_env] = self._merge_environment_profile(envs[target_env], credential_updates)

        active = self._normalize_environment(active_environment) or self._active_environment(row, envs)
        updates: dict[str, Any] = {
            "active_environment": active,
            "environments_json": envs,
        }
        if connector_enabled is not None:
            updates["connector_enabled"] = bool(connector_enabled)
        updates.update(self._legacy_fields_for_environment(envs[active], active))
        row = await self.repositories.workspace_wordpress_connector.upsert(workspace_id, updates)
        return self._public_settings(row)

    async def test_wordpress_connector(self, workspace_id: str, *, environment: str | None = None) -> dict[str, Any]:
        row = await self._connector_row(workspace_id)
        envs = self._parse_environments(row)
        target_env = self._normalize_environment(environment) or self._active_environment(row, envs)
        config = await self._connector_config(workspace_id, environment=target_env)
        client = self._client(config)
        checked_at = _utc_now()
        try:
            health = await client.health()
            site_info = await client.site_info()
            plugin_version = str(health.get("plugin_version") or site_info.get("plugin_version") or "")
            api_version = str(health.get("api_version") or site_info.get("api_version") or "v1")
            envs[target_env] = self._merge_environment_profile(
                envs[target_env],
                {
                    "last_connection_status": "connected",
                    "last_connection_checked_at": checked_at,
                    "last_connection_error": None,
                    "connector_plugin_version": plugin_version,
                    "connector_api_version": api_version,
                },
            )
            updates: dict[str, Any] = {
                "environments_json": envs,
            }
            if target_env == self._active_environment(row, envs):
                updates.update(
                    {
                        "last_connection_status": "connected",
                        "last_connection_checked_at": checked_at,
                        "last_connection_error": None,
                        "connector_plugin_version": plugin_version,
                        "connector_api_version": api_version,
                    }
                )
            row = await self.repositories.workspace_wordpress_connector.upsert(workspace_id, updates)
            return {
                "status": "connected",
                "environment": target_env,
                "plugin_version": plugin_version,
                "api_version": api_version,
                "checked_at": checked_at,
                "settings": self._public_settings(row),
            }
        except Exception as exc:
            reason = str(exc)
            envs[target_env] = self._merge_environment_profile(
                envs[target_env],
                {
                    "last_connection_status": "failed",
                    "last_connection_checked_at": checked_at,
                    "last_connection_error": reason,
                },
            )
            updates = {"environments_json": envs}
            if target_env == self._active_environment(row, envs):
                updates.update(
                    {
                        "last_connection_status": "failed",
                        "last_connection_checked_at": checked_at,
                        "last_connection_error": reason,
                    }
                )
            row = await self.repositories.workspace_wordpress_connector.upsert(workspace_id, updates)
            return {
                "status": "failed",
                "environment": target_env,
                "error": reason,
                "checked_at": checked_at,
                "settings": self._public_settings(row),
            }

    async def create_wordpress_draft(self, job_id: str, *, force: bool = False) -> dict[str, Any]:
        if self.job_service is None:
            raise ValueError("Job service is not configured.")
        job = await self.repositories.jobs.get_job(job_id)
        if job is None:
            raise ValueError("Job not found.")
        workspace_id = str(job.get("workspace_id") or "").strip()
        if not workspace_id:
            raise ValueError("Job is not linked to a workspace.")

        status = str(job.get("status") or "")
        if status in {"failed_generation", "cancelled"}:
            raise ValueError("Article generation failed; cannot create WordPress draft.")

        if job.get("wordpress_post_id") and not force:
            return {
                "job_id": job_id,
                "status": "existing",
                "message": "WordPress draft already linked to this article.",
                "wordpress_post_id": job.get("wordpress_post_id"),
                "wordpress_edit_url": job.get("wordpress_edit_url"),
                "wordpress_public_url": job.get("wordpress_public_url"),
                "wordpress_status": job.get("wordpress_status") or "draft",
                "can_update": _wordpress_draft_is_editable(job),
            }

        if force and job.get("wordpress_post_id"):
            await self.repositories.jobs.update_wordpress_publish_state(
                job_id,
                wordpress_post_id=None,
                wordpress_edit_url=None,
                wordpress_public_url=None,
                wordpress_status=None,
                wordpress_draft_created_at=None,
                wordpress_publish_error=None,
            )
            job = await self.repositories.jobs.get_job(job_id) or job

        row = await self._connector_row(workspace_id)
        envs = self._parse_environments(row)
        active_env = self._active_environment(row, envs)
        config = await self._connector_config(workspace_id, environment=active_env)
        if not config.get("connector_enabled"):
            raise ValueError("WordPress connector is not enabled for this workspace.")

        if self.job_service is not None:
            await self.job_service.run_seo_optimization(job_id, respect_manual_seo=True)
            job = await self.repositories.jobs.get_job(job_id) or job

        body_json = await self._build_draft_body_json(job_id, job, workspace_id)
        attempted_at = _utc_now()
        await self.repositories.jobs.update_wordpress_publish_state(
            job_id,
            wordpress_publish_attempted_at=attempted_at,
            wordpress_publish_error=None,
        )

        client = self._client(config)
        try:
            response = await client.create_draft(body_json)
        except Phase1ConnectorError as exc:
            if exc.status_code == 409:
                existing_id = _extract_post_id(exc.payload)
                edit_url = ""
                public_url = ""
                wp_status = "draft"
                if isinstance(exc.payload, dict):
                    edit_url = str(exc.payload.get("edit_url") or "")
                    public_url = str(exc.payload.get("url") or "")
                    wp_status = str(exc.payload.get("status") or wp_status)
                if existing_id and not edit_url and not public_url:
                    try:
                        draft = await client.get_wordpress_draft(str(existing_id))
                        edit_url = edit_url or str(draft.get("edit_url") or "")
                        public_url = public_url or str(draft.get("url") or "")
                        wp_status = str(draft.get("status") or wp_status)
                    except Phase1ConnectorError:
                        logger.warning(
                            "Could not fetch existing WordPress draft %s after 409 for job %s",
                            existing_id,
                            job_id,
                        )
                await self.repositories.jobs.update_wordpress_publish_state(
                    job_id,
                    wordpress_post_id=str(existing_id) if existing_id else None,
                    wordpress_edit_url=edit_url or None,
                    wordpress_public_url=public_url or None,
                    wordpress_status=wp_status or "draft",
                    wordpress_draft_created_at=attempted_at,
                    wordpress_connector_site_url=config.get("wordpress_base_url"),
                    wordpress_publish_error=None,
                )
                await self.repositories.jobs.mark_status(job_id, "published_draft")
                return {
                    "job_id": job_id,
                    "status": "duplicate",
                    "message": (
                        f"WordPress draft already exists (post #{existing_id}). "
                        "Use Update WordPress draft to push changes to the linked post."
                        if existing_id
                        else "WordPress draft already exists but post ID was not returned."
                    ),
                    "connector_environment": active_env,
                    "wordpress_post_id": existing_id,
                    "wordpress_edit_url": edit_url,
                    "wordpress_public_url": public_url,
                    "wordpress_status": wp_status or "draft",
                    "can_update": bool(existing_id),
                }
            await self._mark_wordpress_publish_failure(job_id, str(exc))
            raise ValueError(f"WordPress draft creation failed: {exc}") from exc
        except Exception as exc:
            await self._mark_wordpress_publish_failure(job_id, str(exc))
            raise ValueError(f"WordPress draft creation failed: {exc}") from exc

        post_id = response.get("id")
        slug_warning = await self._record_draft_exchange(job_id, job, body_json, response)
        await self._persist_draft_create_success(
            job_id,
            response,
            post_id=post_id,
            attempted_at=attempted_at,
            connector_site_url=str(config.get("wordpress_base_url") or ""),
        )
        result = {
            "job_id": job_id,
            "status": "created",
            "connector_environment": active_env,
            "wordpress_post_id": post_id,
            "wordpress_edit_url": response.get("edit_url"),
            "wordpress_public_url": response.get("url"),
            "wordpress_status": response.get("status") or "draft",
        }
        if slug_warning:
            result["slug_sync_warning"] = slug_warning
        return result

    async def update_wordpress_draft(self, job_id: str) -> dict[str, Any]:
        if self.job_service is None:
            raise ValueError("Job service is not configured.")
        job = await self.repositories.jobs.get_job(job_id)
        if job is None:
            raise ValueError("Job not found.")
        workspace_id = str(job.get("workspace_id") or "").strip()
        if not workspace_id:
            raise ValueError("Job is not linked to a workspace.")

        status = str(job.get("status") or "")
        if status in {"failed_generation", "cancelled"}:
            raise ValueError("Article generation failed; cannot update WordPress draft.")

        post_id = job.get("wordpress_post_id")
        if not post_id:
            raise ValueError("No WordPress draft is linked to this article.")

        wp_status = str(job.get("wordpress_status") or "draft").strip().lower()
        if wp_status in WORDPRESS_PUBLISHED_STATUSES:
            raise ValueError("published_post_rejected: This WordPress post is published and cannot be updated from Trendplot.")

        row = await self._connector_row(workspace_id)
        envs = self._parse_environments(row)
        active_env = self._active_environment(row, envs)
        config = await self._connector_config(workspace_id, environment=active_env)
        if not config.get("connector_enabled"):
            raise ValueError("WordPress connector is not enabled for this workspace.")

        if self.job_service is not None:
            await self.job_service.run_seo_optimization(job_id, respect_manual_seo=True)
            job = await self.repositories.jobs.get_job(job_id) or job

        body_json = await self._build_draft_body_json(job_id, job, workspace_id)
        synced_at = _utc_now()
        await self.repositories.jobs.update_wordpress_publish_state(
            job_id,
            wordpress_publish_attempted_at=synced_at,
            wordpress_publish_error=None,
        )

        client = self._client(config)
        try:
            response = await client.update_draft(str(post_id), body_json)
        except Phase1ConnectorError as exc:
            error_code, message = _map_connector_error(exc)
            await self.repositories.jobs.update_wordpress_publish_state(
                job_id,
                wordpress_publish_error=f"{error_code}: {message}",
            )
            raise ValueError(f"WordPress draft update failed ({error_code}): {message}") from exc
        except Exception as exc:
            await self.repositories.jobs.update_wordpress_publish_state(
                job_id,
                wordpress_publish_error=f"connector_error: {exc}",
            )
            raise ValueError(f"WordPress draft update failed (connector_error): {exc}") from exc

        slug_warning = await self._record_draft_exchange(job_id, job, body_json, response)
        await self._persist_draft_update_success(
            job_id,
            response,
            post_id=post_id,
            synced_at=synced_at,
            connector_site_url=str(config.get("wordpress_base_url") or ""),
        )
        result = {
            "job_id": job_id,
            "status": "updated",
            "connector_environment": active_env,
            "wordpress_post_id": response.get("id") or post_id,
            "wordpress_edit_url": response.get("edit_url") or job.get("wordpress_edit_url"),
            "wordpress_public_url": response.get("url") or job.get("wordpress_public_url"),
            "wordpress_status": response.get("status") or wp_status or "draft",
            "wordpress_draft_updated_at": synced_at,
            "last_wordpress_sync_at": synced_at,
        }
        if slug_warning:
            result["slug_sync_warning"] = slug_warning
        return result

    async def refresh_wordpress_status(self, job_id: str) -> dict[str, Any]:
        job = await self.repositories.jobs.get_job(job_id)
        if job is None:
            raise ValueError("Job not found.")
        workspace_id = str(job.get("workspace_id") or "").strip()
        if not workspace_id:
            raise ValueError("Job is not linked to a workspace.")

        post_id = job.get("wordpress_post_id")
        if not post_id:
            raise ValueError("No WordPress post is linked to this article.")

        row = await self._connector_row(workspace_id)
        envs = self._parse_environments(row)
        active_env = self._active_environment(row, envs)
        config = await self._connector_config(workspace_id, environment=active_env)
        if not config.get("connector_enabled"):
            raise ValueError("WordPress connector is not enabled for this workspace.")

        client = self._client(config)
        synced_at = _utc_now()
        try:
            response = await client.get_wordpress_draft(str(post_id))
        except Phase1ConnectorError as exc:
            error_code, message = _map_connector_error(exc)
            if error_code == "missing_draft":
                await self.repositories.jobs.update_wordpress_publish_state(
                    job_id,
                    wordpress_post_id=None,
                    wordpress_edit_url=None,
                    wordpress_public_url=None,
                    wordpress_status=None,
                    wordpress_publish_error=f"missing_draft: {message}",
                    last_wordpress_sync_at=synced_at,
                )
                return {
                    "job_id": job_id,
                    "status": "missing",
                    "connector_environment": active_env,
                    "wordpress_post_id": None,
                    "wordpress_status": None,
                    "wordpress_edit_url": None,
                    "wordpress_public_url": None,
                    "message": message,
                    "last_wordpress_sync_at": synced_at,
                }
            if error_code == "not_trendplot_draft":
                await self.repositories.jobs.update_wordpress_publish_state(
                    job_id,
                    wordpress_publish_error=f"not_trendplot_draft: {message}",
                    last_wordpress_sync_at=synced_at,
                )
                return {
                    "job_id": job_id,
                    "status": "not_managed",
                    "connector_environment": active_env,
                    "wordpress_post_id": post_id,
                    "wordpress_status": job.get("wordpress_status"),
                    "wordpress_edit_url": job.get("wordpress_edit_url"),
                    "wordpress_public_url": job.get("wordpress_public_url"),
                    "message": message,
                    "last_wordpress_sync_at": synced_at,
                }
            if error_code == "auth_failed":
                await self.repositories.jobs.update_wordpress_publish_state(
                    job_id,
                    wordpress_publish_error=f"auth_failed: {message}",
                    last_wordpress_sync_at=synced_at,
                )
                return {
                    "job_id": job_id,
                    "status": "failed",
                    "error_code": "auth_failed",
                    "connector_environment": active_env,
                    "wordpress_post_id": post_id,
                    "wordpress_status": job.get("wordpress_status"),
                    "wordpress_edit_url": job.get("wordpress_edit_url"),
                    "wordpress_public_url": job.get("wordpress_public_url"),
                    "message": message,
                    "last_wordpress_sync_at": synced_at,
                }
            await self.repositories.jobs.update_wordpress_publish_state(
                job_id,
                wordpress_publish_error=f"{error_code}: {message}",
                last_wordpress_sync_at=synced_at,
            )
            raise ValueError(f"WordPress status refresh failed ({error_code}): {message}") from exc
        except ValueError:
            raise
        except Exception as exc:
            await self.repositories.jobs.update_wordpress_publish_state(
                job_id,
                wordpress_publish_error=f"connector_error: {exc}",
                last_wordpress_sync_at=synced_at,
            )
            raise ValueError(f"WordPress status refresh failed (connector_error): {exc}") from exc

        normalized = _normalize_draft_status_response(response, expected_post_id=str(post_id))
        modified_at = str(normalized.get("modified_at") or synced_at)
        wp_status = str(normalized.get("status") or "draft")
        await self.repositories.jobs.update_wordpress_publish_state(
            job_id,
            wordpress_post_id=str(normalized.get("id") or post_id),
            wordpress_edit_url=str(normalized.get("edit_url") or "") or None,
            wordpress_public_url=str(normalized.get("url") or "") or None,
            wordpress_status=wp_status,
            wordpress_draft_updated_at=modified_at,
            last_wordpress_sync_at=synced_at,
            wordpress_connector_site_url=str(config.get("wordpress_base_url") or "") or None,
            wordpress_publish_error=None,
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "wordpress_connector_draft_status_response",
            _artifact_json(normalized),
        )
        return {
            "job_id": job_id,
            "status": "refreshed",
            "connector_environment": active_env,
            "wordpress_post_id": normalized.get("id") or post_id,
            "wordpress_status": wp_status,
            "wordpress_edit_url": normalized.get("edit_url"),
            "wordpress_public_url": normalized.get("url"),
            "wordpress_draft_updated_at": modified_at,
            "last_wordpress_sync_at": synced_at,
        }

    async def generate_seo_package(self, job_id: str) -> dict[str, Any]:
        job = await self._job(job_id)
        workspace_id = str(job.get("workspace_id") or "").strip()
        if not workspace_id:
            raise ValueError("Job is not linked to a workspace.")
        if self.job_service is None:
            raise ValueError("Article generation service is not available.")

        context = await self._seo_package_context(job_id, job)
        article_content = str(context.get("article_content") or "").strip()
        if not article_content:
            raise ValueError("Article content is not available for SEO generation.")
        target_keyword = str(context.get("target_keyword") or "").strip()
        if not target_keyword:
            raise ValueError("Focus keyword is missing from the article metadata.")

        prompt = build_seo_package_prompt(
            article_title=str(context.get("article_title") or ""),
            article_content=article_content,
            target_keyword=target_keyword,
            product_name=str(context.get("product_name") or ""),
            meta_description=str(context.get("meta_description") or ""),
            related_products=list(context.get("related_products") or []),
            article_type=str(context.get("article_type") or "article"),
        )
        generated = await self.job_service.registry.content_generation.generate_seo_metadata(str(prompt))
        payload = parse_llm_json_payload(generated.content_text, generated.content_json)
        if not payload:
            raise ValueError("SEO generation returned an invalid response.")

        seo_fields = normalize_seo_package_payload(payload)
        seo_fields = apply_focus_keyword_strategy(
            seo_fields,
            primary_fallback=target_keyword,
            product_name=str(context.get("product_name") or ""),
            related_products=list(context.get("related_products") or []),
        )
        validation_errors = validate_seo_fields(seo_fields)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))

        generated_at = _utc_now()
        package = seo_package_response(seo_fields)
        await self.repositories.jobs.update_job_seo(
            job_id,
            **seo_fields,
            seo_generated_at=generated_at,
            seo_last_error=None,
            seo_manually_edited=False,
        )
        if self.job_service is not None:
            await self.job_service.run_seo_optimization(job_id, respect_manual_seo=True)
        await self.repositories.artifacts.create_artifact(
            job_id,
            "job_seo_package_response",
            generated if isinstance(generated, GeneratedContent) else GeneratedContent(content_json=payload),
        )
        return {
            "job_id": job_id,
            "status": "generated",
            "seo_generated_at": generated_at,
            "package": package,
            **seo_fields,
        }

    async def generate_job_seo(self, job_id: str) -> dict[str, Any]:
        return await self.generate_seo_package(job_id)

    async def save_job_seo(self, job_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        job = await self._job(job_id)
        cleaned = sanitize_seo_save_fields(fields)
        if "seo_focus_keyword" in cleaned:
            context = await self._seo_package_context(job_id, job)
            cleaned = apply_focus_keyword_strategy(
                cleaned,
                primary_fallback=str(context.get("target_keyword") or ""),
                product_name=str(context.get("product_name") or ""),
                related_products=list(context.get("related_products") or []),
            )
        validation_errors = validate_seo_fields(cleaned)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
        await self.repositories.jobs.update_job_seo(job_id, **cleaned, seo_manually_edited=True)
        job = await self.repositories.jobs.get_job(job_id)
        return {
            "job_id": job_id,
            "status": "saved",
            **job_seo_snapshot(job),
        }

    async def run_seo_optimization(self, job_id: str, *, respect_manual_seo: bool = False) -> dict[str, Any]:
        if self.job_service is None:
            raise ValueError("Article generation service is not available.")
        return await self.job_service.run_seo_optimization(job_id, respect_manual_seo=respect_manual_seo)

    async def sync_job_seo_to_wordpress(self, job_id: str) -> dict[str, Any]:
        job = await self._job(job_id)
        if self.job_service is not None:
            await self.job_service.run_seo_optimization(job_id, respect_manual_seo=True)
            job = await self.repositories.jobs.get_job(job_id) or job
        workspace_id = str(job.get("workspace_id") or "").strip()
        post_id = job.get("wordpress_post_id")
        if not post_id:
            raise ValueError("No WordPress post is linked to this article.")

        seo_fields = job_seo_snapshot(job)
        validation_errors = validate_seo_fields(seo_fields, require_focus_keyword=True)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))

        row = await self._connector_row(workspace_id)
        envs = self._parse_environments(row)
        active_env = self._active_environment(row, envs)
        config = await self._connector_config(workspace_id, environment=active_env)
        if not config.get("connector_enabled"):
            raise ValueError("WordPress connector is not enabled for this workspace.")

        connector_seo = seo_fields_for_connector(seo_fields)
        if not connector_seo:
            raise ValueError("SEO fields are empty.")

        body_json = json.dumps({"seo": connector_seo}, separators=(",", ":"), ensure_ascii=False)
        client = self._client(config)
        synced_at = _utc_now()
        try:
            response = await client.update_post_seo(str(post_id), body_json)
        except Phase1ConnectorError as exc:
            error_code, message = _map_connector_error(exc)
            error_text = f"{error_code}: {message}"
            await self.repositories.jobs.update_job_seo(job_id, seo_last_error=error_text)
            return {
                **job_seo_snapshot(job),
                "job_id": job_id,
                "status": "failed",
                "error_code": error_code,
                "message": message,
                "seo_last_error": error_text,
                "connector_environment": active_env,
                "wordpress_post_id": post_id,
            }
        except Exception as exc:
            error_text = f"connector_error: {exc}"
            await self.repositories.jobs.update_job_seo(job_id, seo_last_error=error_text)
            return {
                **job_seo_snapshot(job),
                "job_id": job_id,
                "status": "failed",
                "error_code": "connector_error",
                "message": str(exc),
                "seo_last_error": error_text,
                "connector_environment": active_env,
                "wordpress_post_id": post_id,
            }

        normalized = normalize_connector_seo_payload(response)
        await self.repositories.jobs.update_job_seo(
            job_id,
            **normalized,
            seo_synced_at=synced_at,
            seo_last_error=None,
        )
        await self.repositories.jobs.update_wordpress_publish_state(
            job_id,
            last_wordpress_sync_at=synced_at,
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "wordpress_connector_seo_sync_response",
            _artifact_json(response),
        )
        job = await self.repositories.jobs.get_job(job_id)
        return {
            **job_seo_snapshot(job),
            "job_id": job_id,
            "status": "synced",
            "connector_environment": active_env,
            "wordpress_post_id": post_id,
            "seo_synced_at": synced_at,
            "last_wordpress_sync_at": synced_at,
        }

    async def refresh_job_seo_from_wordpress(self, job_id: str) -> dict[str, Any]:
        job = await self._job(job_id)
        workspace_id = str(job.get("workspace_id") or "").strip()
        post_id = job.get("wordpress_post_id")
        if not post_id:
            raise ValueError("No WordPress post is linked to this article.")

        row = await self._connector_row(workspace_id)
        envs = self._parse_environments(row)
        active_env = self._active_environment(row, envs)
        config = await self._connector_config(workspace_id, environment=active_env)
        if not config.get("connector_enabled"):
            raise ValueError("WordPress connector is not enabled for this workspace.")

        client = self._client(config)
        refreshed_at = _utc_now()
        try:
            response = await client.get_post_seo(str(post_id))
        except Phase1ConnectorError as exc:
            error_code, message = _map_connector_error(exc)
            error_text = f"{error_code}: {message}"
            await self.repositories.jobs.update_job_seo(job_id, seo_last_error=error_text)
            return {
                **job_seo_snapshot(job),
                "job_id": job_id,
                "status": "failed",
                "error_code": error_code,
                "message": message,
                "seo_last_error": error_text,
                "connector_environment": active_env,
                "wordpress_post_id": post_id,
            }
        except Exception as exc:
            error_text = f"connector_error: {exc}"
            await self.repositories.jobs.update_job_seo(job_id, seo_last_error=error_text)
            return {
                **job_seo_snapshot(job),
                "job_id": job_id,
                "status": "failed",
                "error_code": "connector_error",
                "message": str(exc),
                "seo_last_error": error_text,
                "connector_environment": active_env,
                "wordpress_post_id": post_id,
            }

        normalized = normalize_connector_seo_payload(response)
        if not normalized:
            raise ValueError("WordPress returned no SEO fields for this post.")

        await self.repositories.jobs.update_job_seo(job_id, **normalized, seo_last_error=None)
        await self.repositories.jobs.update_wordpress_publish_state(
            job_id,
            last_wordpress_sync_at=refreshed_at,
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "wordpress_connector_seo_refresh_response",
            _artifact_json(response),
        )
        job = await self.repositories.jobs.get_job(job_id)
        return {
            "job_id": job_id,
            "status": "refreshed",
            "connector_environment": active_env,
            "wordpress_post_id": post_id,
            "last_wordpress_sync_at": refreshed_at,
            **job_seo_snapshot(job),
        }

    async def _seo_package_context(self, job_id: str, job: dict[str, Any]) -> dict[str, Any]:
        if self.job_service is None:
            return {}
        structured = await self.job_service._latest_artifact_json(job_id, "structured_article_json") or {}  # noqa: SLF001
        request_input = job.get("request_input") or {}
        opportunity = request_input.get("opportunity_context") if isinstance(request_input.get("opportunity_context"), dict) else {}
        publishable_html = await self.job_service._resolve_publishable_html(job_id)  # noqa: SLF001
        if not publishable_html:
            publishable_html = await self.job_service._latest_artifact_text(job_id, "rendered_html")  # noqa: SLF001
        related_products = _string_list(opportunity.get("related_products"))
        if not related_products:
            related_products = _string_list(structured.get("related_products"))
        return {
            "article_title": str(
                structured.get("title")
                or request_input.get("title")
                or opportunity.get("title")
                or ""
            ).strip(),
            "article_content": str(publishable_html or ""),
            "target_keyword": str(
                structured.get("focus_keyword")
                or structured.get("primary_keyword")
                or structured.get("target_keyword")
                or request_input.get("target_keyword")
                or request_input.get("topic")
                or opportunity.get("target_keyword")
                or ""
            ).strip(),
            "product_name": str(
                request_input.get("product_name")
                or opportunity.get("product_name")
                or structured.get("product_name")
                or ""
            ).strip(),
            "meta_description": str(
                structured.get("meta_description")
                or job.get("seo_description")
                or ""
            ).strip(),
            "related_products": related_products,
            "article_type": str(
                request_input.get("article_type")
                or opportunity.get("content_type")
                or opportunity.get("article_type")
                or structured.get("article_type")
                or "article"
            ).strip(),
        }

    async def _job(self, job_id: str) -> dict[str, Any]:
        job = await self.repositories.jobs.get_job(job_id)
        if job is None:
            raise ValueError("Job not found.")
        return job

    async def _build_draft_body_json(self, job_id: str, job: dict[str, Any], workspace_id: str) -> str:
        publishable_html = await self.job_service._resolve_publishable_html(job_id)  # noqa: SLF001
        if not publishable_html:
            raise ValueError("Publishable HTML is missing.")
        structured = await self.job_service._latest_artifact_json(job_id, "structured_article_json") or {}  # noqa: SLF001
        request_input = job.get("request_input") or {}
        opportunity = request_input.get("opportunity_context") if isinstance(request_input.get("opportunity_context"), dict) else {}
        title = str(structured.get("title") or request_input.get("title") or "Untitled").strip()
        excerpt = str(structured.get("excerpt") or structured.get("meta_description") or "").strip()
        related_product_names = _string_list(opportunity.get("related_products"))
        related_products = await self._known_wordpress_product_ids(workspace_id, related_product_names)
        recommended_slug = str(job.get("recommended_slug") or structured.get("recommended_slug") or "").strip()
        body_dict = {
            "title": title,
            "content": publishable_html,
            "excerpt": excerpt,
            "categories": [],
            "tags": [],
            "trendplot_article_id": job_id,
            "trendplot_source": str(opportunity.get("source") or request_input.get("origin_type") or "trendplot"),
            "trendplot_generated": structured.get("generated_at") or job.get("updated_at") or _utc_now(),
            "related_products": related_products,
            "related_articles": [],
        }
        if recommended_slug:
            body_dict["slug"] = recommended_slug
        return json.dumps(body_dict, separators=(",", ":"), ensure_ascii=False)

    async def _record_draft_exchange(
        self,
        job_id: str,
        job: dict[str, Any],
        body_json: str,
        response: dict[str, Any],
    ) -> str | None:
        try:
            payload = json.loads(body_json)
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        await self.repositories.artifacts.create_artifact(
            job_id,
            "wordpress_connector_draft_request",
            _artifact_json(
                {
                    "slug": payload.get("slug"),
                    "recommended_slug": job.get("recommended_slug"),
                    "title": payload.get("title"),
                }
            ),
        )
        warning = evaluate_slug_sync(
            recommended_slug=str(job.get("recommended_slug") or payload.get("slug") or ""),
            request_slug=str(payload.get("slug") or ""),
            response_slug=str(response.get("slug") or ""),
        )
        if not warning:
            public_url = str(response.get("url") or job.get("wordpress_public_url") or "")
            response_slug = slug_from_public_url(public_url)
            warning = evaluate_slug_sync(
                recommended_slug=str(job.get("recommended_slug") or payload.get("slug") or ""),
                request_slug=str(payload.get("slug") or ""),
                response_slug=response_slug,
            )
        if warning:
            await self.repositories.artifacts.create_artifact(
                job_id,
                "wordpress_slug_sync_warning",
                _artifact_json(
                    {
                        "message": warning,
                        "request_slug": payload.get("slug"),
                        "response_slug": response.get("slug"),
                    }
                ),
            )
            logger.warning("WordPress slug sync mismatch for job %s: %s", job_id, warning)
        return warning

    async def _persist_draft_create_success(
        self,
        job_id: str,
        response: dict[str, Any],
        *,
        post_id: Any,
        attempted_at: str,
        connector_site_url: str,
    ) -> None:
        await self.repositories.jobs.update_wordpress_publish_state(
            job_id,
            wordpress_post_id=str(post_id) if post_id is not None else None,
            wordpress_edit_url=str(response.get("edit_url") or "") or None,
            wordpress_public_url=str(response.get("url") or "") or None,
            wordpress_status=str(response.get("status") or "draft"),
            wordpress_draft_created_at=attempted_at,
            wordpress_connector_site_url=connector_site_url or None,
            wordpress_publish_error=None,
            last_wordpress_sync_at=attempted_at,
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "wordpress_connector_draft_response",
            _artifact_json(response),
        )
        await self.repositories.jobs.mark_status(job_id, "published_draft")

    async def _persist_draft_update_success(
        self,
        job_id: str,
        response: dict[str, Any],
        *,
        post_id: Any,
        synced_at: str,
        connector_site_url: str,
    ) -> None:
        modified_at = str(response.get("modified_at") or synced_at)
        await self.repositories.jobs.update_wordpress_publish_state(
            job_id,
            wordpress_post_id=str(response.get("id") or post_id),
            wordpress_edit_url=str(response.get("edit_url") or "") or None,
            wordpress_public_url=str(response.get("url") or "") or None,
            wordpress_status=str(response.get("status") or "draft"),
            wordpress_draft_updated_at=modified_at,
            last_wordpress_sync_at=synced_at,
            wordpress_connector_site_url=connector_site_url or None,
            wordpress_publish_error=None,
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "wordpress_connector_draft_update_response",
            _artifact_json(response),
        )
        await self.repositories.jobs.mark_status(job_id, "published_draft")

    async def _mark_wordpress_publish_failure(self, job_id: str, error: str) -> None:
        await self.repositories.jobs.update_wordpress_publish_state(
            job_id,
            wordpress_publish_error=error,
        )
        job = await self.repositories.jobs.get_job(job_id)
        if job and not job.get("wordpress_post_id"):
            await self.repositories.jobs.mark_status(job_id, "failed_publish", error)

    async def _known_wordpress_product_ids(self, workspace_id: str, product_names: list[str]) -> list[int]:
        if not product_names:
            return []
        inventory = await self.repositories.workspace_content_inventory.list_for_workspace(workspace_id, limit=500)
        ids: list[int] = []
        seen: set[int] = set()
        wanted = {name.strip().lower() for name in product_names if name.strip()}
        for item in inventory:
            if str(item.get("content_type") or "").lower() != "product":
                continue
            post_id = item.get("wordpress_post_id")
            if not post_id:
                continue
            title = str(item.get("title") or "").strip().lower()
            if title not in wanted:
                continue
            try:
                numeric_id = int(post_id)
            except (TypeError, ValueError):
                continue
            if numeric_id in seen:
                continue
            seen.add(numeric_id)
            ids.append(numeric_id)
        return ids

    async def _connector_row(self, workspace_id: str) -> dict[str, Any] | None:
        return await self.repositories.workspace_wordpress_connector.get(workspace_id)

    async def _connector_config(self, workspace_id: str, *, environment: str | None = None) -> dict[str, Any]:
        row = await self._connector_row(workspace_id)
        envs = self._parse_environments(row)
        target_env = self._normalize_environment(environment) or self._active_environment(row, envs)
        profile = self._resolved_environment_profile(envs.get(target_env) or self._empty_environment_profile())
        if profile.get("wordpress_base_url") and profile.get("trendplot_site_id") and profile.get("trendplot_shared_secret"):
            return {
                "connector_enabled": bool((row or {}).get("connector_enabled", self.settings.wordpress_connector_enabled)),
                "active_environment": target_env,
                **profile,
            }
        if not row:
            raise ValueError("WordPress connector is not configured for this workspace.")
        missing = [
            label
            for label, key in (
                ("wordpress_base_url", "wordpress_base_url"),
                ("trendplot_site_id", "trendplot_site_id"),
                ("trendplot_shared_secret", "trendplot_shared_secret"),
            )
            if not profile.get(key)
        ]
        env_label = ENVIRONMENT_LABELS.get(target_env, target_env)
        raise ValueError(f"WordPress connector ({env_label}) missing: {', '.join(missing)}.")

    def _client(self, config: dict[str, Any]) -> TrendplotPhase1ConnectorClient:
        return TrendplotPhase1ConnectorClient(
            base_url=str(config["wordpress_base_url"]),
            site_id=str(config["trendplot_site_id"]),
            shared_secret=str(config["trendplot_shared_secret"]),
            timeout_seconds=self.settings.wordpress_connector_timeout_seconds,
        )

    def _public_settings(self, row: dict[str, Any] | None) -> dict[str, Any]:
        envs = self._parse_environments(row)
        active = self._active_environment(row, envs)
        active_profile = envs[active]
        environments_public = {
            env_name: self._public_environment_profile(envs[env_name], env_name, is_active=env_name == active)
            for env_name in CONNECTOR_ENVIRONMENTS
        }
        if not row:
            return {
                "connector_enabled": False,
                "active_environment": active,
                "environments": environments_public,
                "wordpress_base_url": "",
                "trendplot_site_id": "",
                "shared_secret_configured": False,
                "last_connection_status": None,
                "last_connection_checked_at": None,
                "last_connection_error": None,
                "connector_plugin_version": None,
                "connector_api_version": None,
            }
        return {
            "connector_enabled": bool(row.get("connector_enabled")),
            "active_environment": active,
            "environments": environments_public,
            "wordpress_base_url": active_profile.get("wordpress_base_url") or "",
            "trendplot_site_id": active_profile.get("trendplot_site_id") or "",
            "shared_secret_configured": bool(active_profile.get("trendplot_shared_secret")),
            "last_connection_status": active_profile.get("last_connection_status"),
            "last_connection_checked_at": active_profile.get("last_connection_checked_at"),
            "last_connection_error": active_profile.get("last_connection_error"),
            "connector_plugin_version": active_profile.get("connector_plugin_version"),
            "connector_api_version": active_profile.get("connector_api_version"),
        }

    def _public_environment_profile(
        self,
        profile: dict[str, Any],
        environment: ConnectorEnvironment,
        *,
        is_active: bool,
    ) -> dict[str, Any]:
        return {
            "label": ENVIRONMENT_LABELS[environment],
            "is_active": is_active,
            "wordpress_base_url": profile.get("wordpress_base_url") or "",
            "trendplot_site_id": profile.get("trendplot_site_id") or "",
            "shared_secret_configured": bool(profile.get("trendplot_shared_secret")),
            "last_connection_status": profile.get("last_connection_status"),
            "last_connection_checked_at": profile.get("last_connection_checked_at"),
            "last_connection_error": profile.get("last_connection_error"),
            "connector_plugin_version": profile.get("connector_plugin_version"),
            "connector_api_version": profile.get("connector_api_version"),
        }

    def _parse_environments(self, row: dict[str, Any] | None) -> dict[ConnectorEnvironment, dict[str, Any]]:
        envs = {env_name: self._empty_environment_profile() for env_name in CONNECTOR_ENVIRONMENTS}
        if row and row.get("environments_json"):
            stored = row.get("environments_json")
            if isinstance(stored, str):
                try:
                    stored = json.loads(stored)
                except json.JSONDecodeError:
                    stored = {}
            if isinstance(stored, dict):
                for env_name in CONNECTOR_ENVIRONMENTS:
                    payload = stored.get(env_name)
                    if isinstance(payload, dict):
                        envs[env_name] = self._merge_environment_profile(envs[env_name], payload)
        elif row and (
            row.get("wordpress_base_url") or row.get("trendplot_site_id") or row.get("trendplot_shared_secret")
        ):
            envs["staging"] = self._merge_environment_profile(
                envs["staging"],
                {
                    "wordpress_base_url": row.get("wordpress_base_url"),
                    "trendplot_site_id": row.get("trendplot_site_id"),
                    "trendplot_shared_secret": row.get("trendplot_shared_secret"),
                    "last_connection_status": row.get("last_connection_status"),
                    "last_connection_checked_at": row.get("last_connection_checked_at"),
                    "last_connection_error": row.get("last_connection_error"),
                    "connector_plugin_version": row.get("connector_plugin_version"),
                    "connector_api_version": row.get("connector_api_version"),
                },
            )
        return envs

    def _resolved_environment_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        return self._merge_environment_profile(self._empty_environment_profile(), profile)

    def _merge_environment_profile(self, profile: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        merged = dict(profile)
        for key, value in updates.items():
            if value is None:
                continue
            if key == "wordpress_base_url":
                merged[key] = str(value).strip().rstrip("/")
            elif key == "trendplot_site_id":
                merged[key] = str(value).strip()
            elif key == "trendplot_shared_secret":
                secret = str(value).strip()
                if secret:
                    merged[key] = secret
            else:
                merged[key] = value
        return merged

    def _legacy_fields_for_environment(self, profile: dict[str, Any], environment: ConnectorEnvironment) -> dict[str, Any]:
        return {
            "active_environment": environment,
            "wordpress_base_url": profile.get("wordpress_base_url"),
            "trendplot_site_id": profile.get("trendplot_site_id"),
            "trendplot_shared_secret": profile.get("trendplot_shared_secret"),
            "last_connection_status": profile.get("last_connection_status"),
            "last_connection_checked_at": profile.get("last_connection_checked_at"),
            "last_connection_error": profile.get("last_connection_error"),
            "connector_plugin_version": profile.get("connector_plugin_version"),
            "connector_api_version": profile.get("connector_api_version"),
        }

    def _active_environment(self, row: dict[str, Any] | None, envs: dict[ConnectorEnvironment, dict[str, Any]]) -> ConnectorEnvironment:
        configured = self._normalize_environment((row or {}).get("active_environment"))
        if configured:
            return configured
        configured = self._normalize_environment(self.settings.wordpress_connector_active_environment)
        return configured or "staging"

    def _normalize_environment(self, value: Any) -> ConnectorEnvironment | None:
        normalized = str(value or "").strip().lower()
        if normalized in CONNECTOR_ENVIRONMENTS:
            return normalized  # type: ignore[return-value]
        return None

    def _empty_environment_profile(self) -> dict[str, Any]:
        return {
            "wordpress_base_url": "",
            "trendplot_site_id": "",
            "trendplot_shared_secret": "",
            "last_connection_status": None,
            "last_connection_checked_at": None,
            "last_connection_error": None,
            "connector_plugin_version": None,
            "connector_api_version": None,
        }

    async def _workspace(self, workspace_id: str) -> dict[str, Any]:
        workspace = await self.repositories.autopilot_workspaces.get(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace not found: {workspace_id}")
        return workspace


def _wordpress_draft_is_editable(job: dict[str, Any]) -> bool:
    if not job.get("wordpress_post_id"):
        return False
    wp_status = str(job.get("wordpress_status") or "draft").strip().lower()
    return wp_status not in WORDPRESS_PUBLISHED_STATUSES


def _normalize_draft_status_response(response: dict[str, Any], *, expected_post_id: str) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise ValueError("WordPress status refresh failed (connector_error): Invalid connector response.")
    post_id = response.get("id")
    status = response.get("status")
    if post_id is None or not str(status or "").strip():
        raise ValueError("WordPress status refresh failed (connector_error): Malformed connector response.")
    if str(post_id) != str(expected_post_id):
        raise ValueError("WordPress status refresh failed (connector_error): Post ID mismatch in connector response.")
    return response


def _map_connector_error(exc: Phase1ConnectorError) -> tuple[str, str]:
    code = str(exc.code or "").strip().lower()
    if exc.status_code == 401:
        return "auth_failed", str(exc)
    mapped = _CONNECTOR_ERROR_CODES.get(code, "connector_error")
    return mapped, str(exc)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _extract_post_id(payload: Any) -> str | int | None:
    if not isinstance(payload, dict):
        return None
    for key in ("id", "existing_id", "post_id", "wordpress_post_id"):
        if payload.get(key) is not None:
            return payload.get(key)
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("id", "existing_id", "post_id", "wordpress_post_id"):
            if data.get(key) is not None:
                return data.get(key)
    return None


def _artifact_json(payload: dict[str, Any]) -> Any:
    from app.providers.base import GeneratedContent

    return GeneratedContent(content_json=payload, provider="trendplot-connector-phase1")
