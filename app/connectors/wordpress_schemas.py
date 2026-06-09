from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


CONNECTOR_API_VERSION = "v1"
CONNECTOR_BASE_PATH = "/wp-json/trendplot/v1"


class ConnectorError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ConnectorEnvelope(BaseModel):
    ok: bool
    api_version: str = CONNECTOR_API_VERSION
    plugin_version: str | None = None
    site_id: str | None = None
    data: dict[str, Any] | list[Any] | None = None
    warnings: list[str | dict[str, Any]] = Field(default_factory=list)
    error: ConnectorError | None = None
    request_id: str | None = None


class ConnectorSite(BaseModel):
    home_url: str
    name: str = ""
    timezone: str = "UTC"
    locale: str = "en_US"


class ConnectorBuilder(BaseModel):
    id: str
    name: str
    version: str | None = None
    supported_publish_modes: list[str] = Field(default_factory=list)
    supported_templates: list[str] = Field(default_factory=list)


class ConnectorCapabilities(BaseModel):
    api_version: str = CONNECTOR_API_VERSION
    plugin_version: str | None = None
    site_id: str | None = None
    site: ConnectorSite | None = None
    capabilities: dict[str, bool] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)
    builders: list[ConnectorBuilder] = Field(default_factory=list)


class ConnectorTemplate(BaseModel):
    key: str
    label: str
    builder: str | None = None
    supported: bool = True
    recommended_for_posts: bool = False
    notes: str | None = None


class ConnectorTaxonomyTerm(BaseModel):
    id: int
    name: str
    slug: str
    count: int | None = None


class ConnectorBuilderTemplate(BaseModel):
    key: str
    builder: str | None = None
    mode: str | None = None


class ConnectorSeoMetadata(BaseModel):
    meta_title: str = ""
    meta_description: str = ""
    canonical_url: str = ""


class ConnectorSourceMetadata(BaseModel):
    backend: str = "trendplot"
    workspace_id: str | None = None
    quality_status: str | None = None
    sanity_status: str | None = None
    compliance_status: str | None = None
    backend_version: str | None = None


class ConnectorDraftPostRequest(BaseModel):
    external_job_id: str | None = None
    external_plan_item_id: str | None = None
    title: str
    slug: str | None = None
    excerpt: str | None = None
    content_html: str
    status_policy: Literal["draft"] = "draft"
    author_id: int | None = None
    categories: list[int] = Field(default_factory=list)
    tags: list[str | int] = Field(default_factory=list)
    featured_media_id: int | None = None
    template: ConnectorBuilderTemplate | None = None
    seo: ConnectorSeoMetadata = Field(default_factory=ConnectorSeoMetadata)
    source: ConnectorSourceMetadata = Field(default_factory=ConnectorSourceMetadata)


class ConnectorPublishPostRequest(BaseModel):
    external_job_id: str | None = None
    confirm_live_publish: bool = False
    quality_status: str = "unknown"
    sanity_status: str = "unknown"
    compliance_status: str = "unknown"


class ConnectorSchedulePostRequest(BaseModel):
    publish_at: str
    timezone: str = "UTC"


class ConnectorMediaFromUrlRequest(BaseModel):
    url: HttpUrl
    filename: str | None = None
    alt_text: str = ""
    caption: str = ""
    usage: Literal["featured", "inline", "social"] = "featured"
    external_job_id: str | None = None


class ConnectorContentInventoryQuery(BaseModel):
    post_type: str = "post,page,product"
    updated_after: str | None = None
    limit: int = 100
    cursor: str | None = None


class ConnectorEventPost(BaseModel):
    id: int | str
    url: str | None = None
    status: str | None = None


class ConnectorEventRequest(BaseModel):
    site_id: str
    event_id: str
    event_type: Literal[
        "post_created",
        "post_updated",
        "post_published",
        "post_deleted",
        "media_uploaded",
        "plugin_connected",
        "plugin_disconnected",
        "capabilities_changed",
        "content_inventory_changed",
    ]
    occurred_at: str
    post: ConnectorEventPost | None = None
    source: str = "wordpress-plugin"
    payload: dict[str, Any] = Field(default_factory=dict)


STABLE_ERROR_CODES = {
    "unauthorized",
    "forbidden",
    "capability_not_supported",
    "validation_failed",
    "post_not_found",
    "template_not_supported",
    "builder_not_supported",
    "media_upload_failed",
    "taxonomy_not_found",
    "live_publish_disabled",
    "rate_limited",
    "internal_error",
}
