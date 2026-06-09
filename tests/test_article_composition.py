from app.article_schema import normalize_article
from app.rendering.article_renderer import render_article
from app.rendering.render_surface import ArticleRenderSurface
from app.review.article_composition import (
    apply_article_composition_refinement,
    compress_repeated_concepts,
    count_concept_repetitions,
    prose_word_count,
)
from app.review.compliance_redundancy import apply_editorial_post_processing


def _comparison_fixture() -> dict:
    return {
        "title": "CJC-1295 No DAC + IPA vs CJC-1295: what changes in research framing",
        "primary_keyword": "cjc-1295 no dac ipa vs cjc-1295",
        "secondary_keywords": ["CJC-1295 No DAC + IPA", "CJC-1295", "GHRH signaling"],
        "key_takeaways": [
            "Timing and pulse kinetics shape how researchers compare exposure profiles.",
            "Endpoint selection matters when contrasting DAC and No DAC framing.",
        ],
        "research_context": "Kinetics and timing are central when reading growth-hormone secretagogue literature.",
        "sections": [
            {
                "heading": "Exposure profile",
                "content_markdown": (
                    "Timing matters because DAC-modified CJC-1295 is discussed through prolonged exposure logic. "
                    "Sampling windows must match the kinetic question being asked."
                ),
            },
            {
                "heading": "Receptor framing",
                "content_markdown": (
                    "A key distinction is that No DAC + IPA pairs GHRH-side and ghrelin-side signaling. "
                    "Timing still matters when comparing receptor engagement across formats."
                ),
            },
            {
                "heading": "Experimental models",
                "content_markdown": (
                    "Endpoint selection matters in preclinical models because pulse readouts differ by assay design. "
                    "Sampling cadence should follow the exposure profile under study."
                ),
            },
            {
                "heading": "Research summary",
                "content_markdown": (
                    "In summary, timing, sampling, and endpoint selection all shape interpretation. "
                    "The literature is not asking which label is stronger, but which biological question is isolated."
                ),
            },
        ],
        "internal_links": [
            {
                "anchor_text": "CJC-1295 No DAC + IPA",
                "url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
                "reason": "Primary product",
            }
        ],
    }


def test_compress_repeated_concepts_reduces_word_count() -> None:
    before = _comparison_fixture()
    before_words = prose_word_count(before)
    after = compress_repeated_concepts(before)
    after_words = prose_word_count(after)
    assert after_words < before_words
    assert after_words >= int(before_words * 0.75)
    assert sum(count_concept_repetitions(after).values()) <= sum(count_concept_repetitions(before).values())


def test_comparison_matrix_is_derived_from_sections() -> None:
    refined = apply_article_composition_refinement(
        _comparison_fixture(),
        opportunity_context={"content_type": "comparison", "science_focus": True},
        defaults={
            "title": "CJC-1295 No DAC + IPA vs CJC-1295: what changes in research framing",
            "target_keyword": "cjc-1295 no dac ipa vs cjc-1295",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        },
    )
    assert refined["comparison_tables"]
    matrix = refined["comparison_tables"][0]
    assert matrix["title"] == "Comparison Matrix"
    assert len(matrix["rows"]) >= 3
    assert "CJC-1295 No DAC + IPA" in matrix["headers"][1]


def test_callout_promoted_for_key_distinction() -> None:
    refined = apply_article_composition_refinement(
        _comparison_fixture(),
        opportunity_context={"content_type": "comparison", "science_focus": True},
        defaults={
            "title": "CJC-1295 No DAC + IPA vs CJC-1295: what changes in research framing",
            "target_keyword": "cjc-1295 no dac ipa vs cjc-1295",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        },
    )
    titles = [box["title"] for box in refined.get("callout_boxes") or []]
    assert "Key Distinction" in titles


def test_product_reference_integrated_without_standalone_cta() -> None:
    from app.internal_links.product_linker import build_article_product_url_map, link_products_in_article

    fixture = _comparison_fixture()
    fixture["sections"][0]["content_markdown"] += (
        " CJC-1295 No DAC + IPA materials are often referenced when comparing pulse assays."
    )
    article = normalize_article(
        fixture,
        defaults={
            "title": "CJC-1295 No DAC + IPA vs CJC-1295: what changes in research framing",
            "target_keyword": "cjc-1295 no dac ipa vs cjc-1295",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        },
    )
    processed = apply_editorial_post_processing(
        article,
        defaults={
            "title": "CJC-1295 No DAC + IPA vs CJC-1295: what changes in research framing",
            "target_keyword": "cjc-1295 no dac ipa vs cjc-1295",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        },
        opportunity_context={"content_type": "comparison", "science_focus": True},
    )
    url_map = build_article_product_url_map(
        product_name="CJC-1295 No DAC + IPA",
        product_url="https://www.example.com/product/cjc-1295-no-dac-ipa/",
        related_products=[],
        catalog_urls=["https://www.example.com/product/cjc-1295-no-dac-ipa/"],
    )
    linked, _report = link_products_in_article(processed.model_dump(), url_map)
    processed = normalize_article(
        linked,
        defaults={
            "title": "CJC-1295 No DAC + IPA vs CJC-1295: what changes in research framing",
            "target_keyword": "cjc-1295 no dac ipa vs cjc-1295",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        },
    )
    html = render_article(processed, surface=ArticleRenderSurface.PUBLISHABLE).html
    assert "Researchers interested in" not in html
    assert "https://www.example.com/product/cjc-1295-no-dac-ipa/" in html
    assert "Comparison Matrix" in html or "bp-ai-comparison-table" in html


def test_mechanism_summary_table_for_mechanism_article() -> None:
    payload = {
        "title": "How CJC-1295 No DAC engages GHRH signaling",
        "sections": [
            {
                "heading": "Receptor entry point",
                "content_markdown": "CJC-1295 No DAC binds the GHRH receptor and activates cAMP-linked signaling in pituitary models.",
            },
            {
                "heading": "Downstream biology",
                "content_markdown": "Downstream effects include growth hormone pulse initiation in preclinical endocrine assays.",
            },
            {
                "heading": "Evidence limits",
                "content_markdown": "Human translation remains uncertain because most evidence is preclinical and model-dependent.",
            },
        ],
    }
    refined = apply_article_composition_refinement(
        payload,
        opportunity_context={"content_type": "mechanism", "science_focus": True},
        defaults={
            "title": "How CJC-1295 No DAC engages GHRH signaling",
            "target_keyword": "cjc-1295 mechanism",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://example.com/product/",
        },
    )
    assert any(table.get("title") == "Mechanism Summary Table" for table in refined.get("comparison_tables") or [])


def test_relationship_summary_table_for_relationship_article() -> None:
    payload = {
        "title": "BPC-157 and TB-500: shared repair literature themes",
        "sections": [
            {
                "heading": "Shared themes",
                "content_markdown": "Both peptides are discussed together in tissue repair literature and preclinical recovery models.",
            },
            {
                "heading": "Key distinction",
                "content_markdown": "The key distinction is that BPC-157 and TB-500 are not interchangeable mechanistic probes.",
            },
            {
                "heading": "Paired studies",
                "content_markdown": "Some papers study the combination when investigators want paired angiogenic and motility readouts.",
            },
        ],
    }
    refined = apply_article_composition_refinement(
        payload,
        opportunity_context={"content_type": "relationship", "science_focus": True},
        defaults={
            "title": "BPC-157 and TB-500: shared repair literature themes",
            "target_keyword": "bpc-157 tb-500 relationship",
            "product_name": "BPC-157",
            "product_url": "https://example.com/product/bpc-157/",
        },
    )
    assert any(table.get("title") == "Relationship Summary Table" for table in refined.get("comparison_tables") or [])


def test_repeated_concept_count_drops_after_refinement() -> None:
    before = _comparison_fixture()
    before_counts = count_concept_repetitions(before)
    after = apply_article_composition_refinement(
        before,
        opportunity_context={"content_type": "comparison", "science_focus": True},
        defaults={
            "title": before["title"],
            "target_keyword": before["primary_keyword"],
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        },
    )
    after_counts = count_concept_repetitions(after)
    assert sum(after_counts.values()) < sum(before_counts.values())
