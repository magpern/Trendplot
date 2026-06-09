import json
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.providers.model_router import ModelTask
from app.wordpress import normalize_template_key


@dataclass(slots=True)
class PublishDecisionResult:
    metadata: dict[str, Any]
    report: dict[str, Any]
    artifacts: dict[str, dict[str, Any]]


class PublishDecisionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def decide(
        self,
        *,
        content_provider: Any | None,
        request_input: dict[str, Any],
        structured_article: dict[str, Any],
        initial_metadata: dict[str, Any],
        featured_image: dict[str, Any] | None,
        available_templates: list[dict[str, Any]],
        available_categories: list[dict[str, Any]],
        publish_policy: str,
        quality_passed: bool,
        sanity_passed: bool,
        unattended_mode: bool,
    ) -> PublishDecisionResult:
        ai = await self._ai_suggestion(
            content_provider=content_provider,
            request_input=request_input,
            structured_article=structured_article,
            available_templates=available_templates,
            available_categories=available_categories,
            featured_image=featured_image or {},
            enabled=bool(unattended_mode and self.settings.unattended_mode_enabled),
        )
        template = self._decide_template(initial_metadata, available_templates, ai)
        category = self._decide_category(initial_metadata, available_categories, ai)
        tags = self._decide_tags(initial_metadata, structured_article, request_input, ai)
        featured = self._decide_featured_image(initial_metadata, featured_image or {}, ai)
        publish = self._decide_publish_status(
            publish_policy=publish_policy,
            quality_passed=quality_passed,
            sanity_passed=sanity_passed,
            unattended_mode=unattended_mode,
        )

        metadata = {
            "wordpress_template": template["selected_value"],
            "wordpress_category_id": category["selected_value"].get("id"),
            "wordpress_category_slug": category["selected_value"].get("slug"),
            "wordpress_category_name": category["selected_value"].get("name"),
            "wordpress_tags": tags["selected_value"],
            "featured_image_id": featured["selected_value"].get("id"),
            "featured_image_url": featured["selected_value"].get("url"),
            "featured_image_alt": featured["selected_value"].get("alt_text"),
            "publish_status": publish["selected_value"],
        }
        report = {
            "unattended_mode": unattended_mode,
            "publish_policy": publish_policy,
            "quality_passed": quality_passed,
            "sanity_passed": sanity_passed,
            "template": template,
            "category": category,
            "tags": tags,
            "featured_image": featured,
            "publish": publish,
            "safety_notes": publish["safety_notes"],
        }
        return PublishDecisionResult(
            metadata=metadata,
            report=report,
            artifacts={
                "ai_category_decision": ai.get("category") or {"used": False, "reason": "No AI category decision used."},
                "ai_tag_decision": ai.get("tags") or {"used": False, "reason": "No AI tag decision used."},
                "ai_template_decision": ai.get("template") or {"used": False, "reason": "No AI template decision used."},
                "unattended_policy_result": publish,
                "final_publish_metadata": metadata,
            },
        )

    async def _ai_suggestion(
        self,
        *,
        content_provider: Any | None,
        request_input: dict[str, Any],
        structured_article: dict[str, Any],
        available_templates: list[dict[str, Any]],
        available_categories: list[dict[str, Any]],
        featured_image: dict[str, Any],
        enabled: bool,
    ) -> dict[str, Any]:
        if not enabled or content_provider is None:
            return {}
        templates = [item for item in available_templates if self._template_allowed(str(item.get("key") or ""))]
        prompt = (
            "Choose safe WordPress presentation defaults for an unattended SEO article publish. "
            "Return strict JSON with template_key, category_id, tags, use_featured_image, and reasons. "
            "Choose template/category only from the supplied lists. Do not choose Elementor Canvas unless allowed.\n\n"
            f"Request:\n{json.dumps(request_input, ensure_ascii=False, indent=2)}\n\n"
            f"Article metadata:\n{json.dumps(_article_metadata(structured_article), ensure_ascii=False, indent=2)}\n\n"
            f"Available templates:\n{json.dumps(templates, ensure_ascii=False, indent=2)}\n\n"
            f"Available categories:\n{json.dumps(available_categories, ensure_ascii=False, indent=2)}\n\n"
            f"Featured image artifact:\n{json.dumps(featured_image, ensure_ascii=False, indent=2)}"
        )
        try:
            generated = await content_provider.generate_article(prompt, task_type=ModelTask.CLASSIFICATION)
        except Exception as exc:
            return {"error": str(exc)}
        payload = generated.content_json or {}
        return {
            "template": {
                "selected_value": str(payload.get("template_key") or ""),
                "reason": str(payload.get("template_reason") or payload.get("reason") or "AI template suggestion."),
            },
            "category": {
                "selected_value": payload.get("category_id"),
                "reason": str(payload.get("category_reason") or payload.get("reason") or "AI category suggestion."),
            },
            "tags": {
                "selected_value": _clean_tags(payload.get("tags"), self.settings.wordpress_max_tags),
                "reason": str(payload.get("tag_reason") or payload.get("reason") or "AI tag suggestion."),
            },
            "featured_image": {
                "selected_value": bool(payload.get("use_featured_image")),
                "reason": str(payload.get("featured_image_reason") or payload.get("reason") or "AI featured image suggestion."),
            },
            "model": generated.model,
            "task_type": generated.task_type,
        }

    def _decide_template(
        self,
        metadata: dict[str, Any],
        available_templates: list[dict[str, Any]],
        ai: dict[str, Any],
    ) -> dict[str, Any]:
        allowed = {normalize_template_key(str(item.get("key") or "")): item for item in available_templates}
        configured = normalize_template_key(self.settings.wordpress_default_template or "elementor_full_width")
        choices = [
            ("user", metadata.get("wordpress_template"), "User-selected template."),
            ("site_default", configured, "Configured default template."),
            ("ai", (ai.get("template") or {}).get("selected_value"), (ai.get("template") or {}).get("reason")),
            ("safe_fallback", "elementor_header_footer", "Safe Elementor Full Width fallback."),
            ("safe_fallback", "", "Default theme template fallback."),
        ]
        alternatives = [item.get("key") for item in available_templates]
        for source, value, reason in choices:
            key = normalize_template_key(str(value or ""))
            if not key and source != "safe_fallback":
                continue
            if key == "elementor_canvas" and not self.settings.wordpress_allow_elementor_canvas:
                continue
            if key in allowed or key == "":
                return _decision(key, source, alternatives, reason or "")
        return _decision("", "safe_fallback", alternatives, "No supported template matched; using default theme template.")

    def _decide_category(
        self,
        metadata: dict[str, Any],
        available_categories: list[dict[str, Any]],
        ai: dict[str, Any],
    ) -> dict[str, Any]:
        alternatives = [{"id": item.get("id"), "name": item.get("name"), "slug": item.get("slug")} for item in available_categories]
        user = self._category_by_id_or_text(
            available_categories,
            metadata.get("wordpress_category_id"),
            metadata.get("wordpress_category_slug"),
            metadata.get("wordpress_category_name"),
        )
        if user:
            return _decision(user, "user", alternatives, "User-selected category.")
        ai_category = self._category_by_id_or_text(available_categories, (ai.get("category") or {}).get("selected_value"), None, None)
        if ai_category:
            return _decision(ai_category, "ai", alternatives, (ai.get("category") or {}).get("reason", "AI category suggestion."))
        configured = self._category_by_id_or_text(
            available_categories,
            self.settings.wordpress_default_category_id,
            self.settings.wordpress_default_category_slug,
            None,
        )
        if configured:
            return _decision(configured, "site_default", alternatives, "Configured default category.")
        return _decision({}, "safe_fallback", alternatives, "No category selected; WordPress will use its default/uncategorized behavior.")

    def _decide_tags(
        self,
        metadata: dict[str, Any],
        structured_article: dict[str, Any],
        request_input: dict[str, Any],
        ai: dict[str, Any],
    ) -> dict[str, Any]:
        alternatives = [
            "user-provided tags",
            "configured default tags",
            "AI suggested tags",
            "keyword/product fallback tags",
        ]
        user_tags = _clean_tags(metadata.get("wordpress_tags"), self.settings.wordpress_max_tags)
        if user_tags:
            return _decision(user_tags, "user", alternatives, "User-provided tags.")
        ai_tags = _clean_tags((ai.get("tags") or {}).get("selected_value"), self.settings.wordpress_max_tags)
        if ai_tags:
            return _decision(ai_tags, "ai", alternatives, (ai.get("tags") or {}).get("reason", "AI tag suggestion."))
        configured_tags = _clean_tags(self.settings.wordpress_default_tags, self.settings.wordpress_max_tags)
        if configured_tags:
            return _decision(configured_tags, "site_default", alternatives, "Configured default tags.")
        fallback = _clean_tags(
            [
                structured_article.get("primary_keyword"),
                request_input.get("target_keyword"),
                request_input.get("product_name"),
                *(structured_article.get("secondary_keywords") or []),
            ],
            self.settings.wordpress_max_tags,
        )
        return _decision(fallback, "safe_fallback", alternatives, "Keyword/product fallback tags.")

    def _decide_featured_image(
        self,
        metadata: dict[str, Any],
        featured_image: dict[str, Any],
        ai: dict[str, Any],
    ) -> dict[str, Any]:
        alternatives = ["provided media ID", "real image artifact", "provided URL", "omit image"]
        if metadata.get("featured_image_id"):
            return _decision({"id": metadata.get("featured_image_id"), "url": "", "alt_text": metadata.get("featured_image_alt")}, "user", alternatives, "User-provided media ID.")
        artifact_url = str((featured_image or {}).get("url") or "").strip()
        if artifact_url and "placehold.co" not in artifact_url.lower():
            use_image = True
            if ai.get("featured_image"):
                use_image = bool(ai["featured_image"].get("selected_value"))
            if use_image:
                return _decision(
                    {"id": None, "url": artifact_url, "alt_text": featured_image.get("alt_text") or metadata.get("featured_image_alt") or ""},
                    "image_artifact",
                    alternatives,
                    "Real featured image artifact is available.",
                )
        provided_url = str(metadata.get("featured_image_url") or "").strip()
        if provided_url and "placehold.co" not in provided_url.lower():
            return _decision({"id": None, "url": provided_url, "alt_text": metadata.get("featured_image_alt") or ""}, "user", alternatives, "User-provided image URL.")
        reason = "No real featured image available; omitting image."
        if self.settings.wordpress_require_featured_image:
            reason = "Featured image is required by config but no real image is available; publishing should be reviewed."
        return _decision({"id": None, "url": "", "alt_text": ""}, "safe_fallback", alternatives, reason)

    def _decide_publish_status(
        self,
        *,
        publish_policy: str,
        quality_passed: bool,
        sanity_passed: bool,
        unattended_mode: bool,
    ) -> dict[str, Any]:
        safety_notes = []
        if self.settings.unattended_require_quality_pass and not quality_passed:
            safety_notes.append("Quality gate did not pass; unattended publish blocked.")
        if self.settings.unattended_require_sanity_pass and not sanity_passed:
            safety_notes.append("Sanity gate did not pass; unattended publish blocked.")
        gates_passed = (quality_passed or not self.settings.unattended_require_quality_pass) and (
            sanity_passed or not self.settings.unattended_require_sanity_pass
        )
        if publish_policy == "auto_draft" and gates_passed:
            return _decision("draft", "publish_policy", ["none", "draft", "publish"], "auto_draft selected.", safety_notes)
        if publish_policy == "manual_draft" and gates_passed:
            return _decision("draft", "user", ["none", "draft", "publish"], "User explicitly requested draft publishing.", safety_notes)
        if publish_policy == "manual_publish" and gates_passed:
            return _decision("publish", "user", ["none", "draft", "publish"], "User explicitly confirmed live publishing.", safety_notes)
        if publish_policy == "auto_live" and gates_passed:
            live_allowed = all(
                [
                    unattended_mode,
                    self.settings.unattended_mode_enabled,
                    self.settings.unattended_allow_auto_live,
                    self.settings.allow_auto_live,
                    self.settings.allow_live_publish,
                ]
            )
            if live_allowed:
                return _decision("publish", "publish_policy", ["none", "draft", "publish"], "All unattended live flags are enabled.", safety_notes)
            safety_notes.append("auto_live blocked because one or more live publishing flags are disabled.")
        return _decision("none", "safe_fallback", ["none", "draft", "publish"], "No automatic publish will be attempted.", safety_notes)

    def _category_by_id_or_text(
        self,
        categories: list[dict[str, Any]],
        category_id: Any,
        slug: Any,
        name: Any,
    ) -> dict[str, Any] | None:
        slug_text = str(slug or "").strip().lower()
        name_text = str(name or "").strip().lower()
        id_text = str(category_id or "").strip()
        for category in categories:
            if id_text and str(category.get("id") or "") == id_text:
                return {"id": category.get("id"), "name": category.get("name"), "slug": category.get("slug")}
            if slug_text and str(category.get("slug") or "").strip().lower() == slug_text:
                return {"id": category.get("id"), "name": category.get("name"), "slug": category.get("slug")}
            if name_text and str(category.get("name") or "").strip().lower() == name_text:
                return {"id": category.get("id"), "name": category.get("name"), "slug": category.get("slug")}
        return None

    def _template_allowed(self, key: str) -> bool:
        return normalize_template_key(key) != "elementor_canvas" or self.settings.wordpress_allow_elementor_canvas


def _decision(
    selected_value: Any,
    source: str,
    alternatives: list[Any],
    reason: str,
    safety_notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "selected_value": selected_value,
        "decision_source": source,
        "alternatives_considered": alternatives,
        "reason": reason,
        "safety_notes": safety_notes or [],
    }


def _article_metadata(article: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": article.get("title"),
        "primary_keyword": article.get("primary_keyword"),
        "secondary_keywords": article.get("secondary_keywords", []),
        "excerpt": article.get("excerpt"),
        "sections": [section.get("heading") for section in article.get("sections", []) if isinstance(section, dict)],
    }


def _clean_tags(value: Any, max_tags: int) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, list):
        values = value
    else:
        values = [value]
    cleaned = []
    seen: set[str] = set()
    for item in values:
        tag = " ".join(str(item).replace("#", "").split()).strip(" ,;")
        if not tag or len(tag) > 60:
            continue
        key = tag.lower()
        if key in seen:
            continue
        if len(tag.split()) > 5 and any(len(existing.split()) > 5 for existing in cleaned):
            continue
        seen.add(key)
        cleaned.append(tag)
        if len(cleaned) >= max(1, max_tags):
            break
    return cleaned
