from __future__ import annotations

import re

from app.internal_links.product_linker import (
    MAX_LINKS_PER_PRODUCT,
    build_article_product_url_map,
    link_first_unlinked_mention,
    link_products_in_article,
)

TB500_URL = "https://www.example.com/product/tb-500/"
BPC157_URL = "https://www.example.com/product/bpc-157/"
CATALOG_URLS = [
    "https://www.example.com/",
    TB500_URL,
    BPC157_URL,
]


def _comparison_article() -> dict:
    return {
        "title": "TB-500 vs BPC-157 in model contexts",
        "excerpt": "TB-500 and BPC-157 are often compared in soft tissue models.",
        "key_takeaways": [
            "TB-500 and BPC-157 are common comparison targets.",
            "Readers should compare endpoints before choosing a model probe.",
        ],
        "sections": [
            {
                "heading": "Common model contexts",
                "content_markdown": (
                    "TB-500 and BPC-157 are often compared because they appear in overlapping model categories. "
                    "TB-500 is discussed for motility readouts while BPC-157 appears in angiogenesis assays."
                ),
            },
            {
                "heading": "Soft tissue models",
                "content_markdown": (
                    "In soft tissue discussions, TB-500 may appear alongside BPC-157 when endpoints include recovery timing. "
                    "TB-500 again shows up in tendon-oriented protocols."
                ),
            },
            {
                "heading": "Interpretation",
                "content_markdown": (
                    "BPC-157 and TB-500 should not be treated as interchangeable mechanistic probes. "
                    "BPC-157 literature often emphasizes different sampling windows than TB-500."
                ),
            },
        ],
        "faq": [
            {
                "question": "Is TB-500 the same as BPC-157?",
                "answer": "TB-500 and BPC-157 are distinct research materials with different literature framing.",
            }
        ],
    }


def _count_product_links(text: str, product_name: str, url: str) -> int:
    pattern = re.compile(rf"\[[^\]]*{re.escape(product_name)}[^\]]*\]\({re.escape(url)}\)", re.IGNORECASE)
    return len(pattern.findall(text))


def _article_blob(article: dict) -> str:
    parts = [str(article.get("excerpt") or "")]
    for section in article.get("sections") or []:
        parts.append(str(section.get("content_markdown") or ""))
    for item in article.get("faq") or []:
        parts.append(str(item.get("answer") or ""))
    return "\n".join(parts)


def test_build_article_product_url_map_resolves_related_products() -> None:
    url_map = build_article_product_url_map(
        product_name="TB-500",
        product_url="https://www.example.com/",
        related_products=["BPC-157"],
        catalog_urls=CATALOG_URLS,
    )
    assert url_map["TB-500"] == TB500_URL
    assert url_map["BPC-157"] == BPC157_URL


def test_comparison_article_editorial_link_density() -> None:
    url_map = {"TB-500": TB500_URL, "BPC-157": BPC157_URL}
    updated, report = link_products_in_article(_comparison_article(), url_map)
    blob = _article_blob(updated)

    tb_links = _count_product_links(blob, "TB-500", TB500_URL)
    bpc_links = _count_product_links(blob, "BPC-157", BPC157_URL)
    total = tb_links + bpc_links

    assert 2 <= total <= 4
    assert tb_links <= MAX_LINKS_PER_PRODUCT
    assert bpc_links <= MAX_LINKS_PER_PRODUCT
    assert report.total_links == total


def test_max_two_links_per_product() -> None:
    article = {
        "sections": [
            {"heading": "A", "content_markdown": "TB-500 appears in section one."},
            {"heading": "B", "content_markdown": "TB-500 appears in section two."},
            {"heading": "C", "content_markdown": "TB-500 appears in section three."},
        ]
    }
    updated, _report = link_products_in_article(article, {"TB-500": TB500_URL})
    blob = _article_blob(updated)
    assert _count_product_links(blob, "TB-500", TB500_URL) == 2
    assert blob.count("TB-500 appears in section three.") == 1


def test_max_one_link_per_section() -> None:
    article = {
        "sections": [
            {
                "heading": "A",
                "content_markdown": "TB-500 and TB-500 again in the same section.",
            }
        ]
    }
    updated, _report = link_products_in_article(article, {"TB-500": TB500_URL})
    blob = updated["sections"][0]["content_markdown"]
    assert _count_product_links(blob, "TB-500", TB500_URL) == 1


def test_headings_never_linked() -> None:
    text = "## TB-500 overview\nTB-500 is used in tendon models.\n### BPC-157 notes\nBPC-157 appears in angiogenesis assays."
    updated, linked = link_first_unlinked_mention(text, "TB-500", TB500_URL)
    assert linked
    assert "## TB-500 overview" in updated
    assert "### BPC-157 notes" in updated
    updated2, linked2 = link_first_unlinked_mention(updated, "BPC-157", BPC157_URL)
    assert linked2
    assert "### BPC-157 notes" in updated2


def test_faq_questions_never_linked() -> None:
    article = {
        "sections": [],
        "faq": [
            {
                "question": "Should I compare TB-500 with BPC-157?",
                "answer": "TB-500 and BPC-157 are discussed in different assay contexts.",
            }
        ],
    }
    updated, _report = link_products_in_article(
        article,
        {"TB-500": TB500_URL, "BPC-157": BPC157_URL},
    )
    assert updated["faq"][0]["question"] == "Should I compare TB-500 with BPC-157?"
    answer = updated["faq"][0]["answer"]
    assert _count_product_links(answer, "TB-500", TB500_URL) <= 1


def test_existing_links_not_duplicated() -> None:
    article = {
        "sections": [
            {
                "heading": "Intro",
                "content_markdown": f"[TB-500]({TB500_URL}) appears again as TB-500 in later text.",
            },
            {"heading": "Later", "content_markdown": "TB-500 is mentioned again here."},
        ]
    }
    updated, report = link_products_in_article(article, {"TB-500": TB500_URL})
    blob = _article_blob(updated)
    assert _count_product_links(blob, "TB-500", TB500_URL) == 2
    assert blob.count(f"[TB-500]({TB500_URL})") == 2
    assert report.products["TB-500"]["link_count"] == 2


def test_primary_link_does_not_block_related_product() -> None:
    article = {
        "sections": [
            {
                "heading": "Intro",
                "content_markdown": f"[TB-500]({TB500_URL}) and BPC-157 are often compared.",
            }
        ]
    }
    updated, report = link_products_in_article(
        article,
        {"TB-500": TB500_URL, "BPC-157": BPC157_URL},
    )
    blob = updated["sections"][0]["content_markdown"]
    assert _count_product_links(blob, "TB-500", TB500_URL) == 1
    assert _count_product_links(blob, "BPC-157", BPC157_URL) == 1
    assert report.products["BPC-157"]["link_count"] == 1


def test_body_first_placement_avoids_takeaways() -> None:
    article = {
        "key_takeaways": ["TB-500 and BPC-157 are common comparison targets."],
        "sections": [
            {"heading": "Body", "content_markdown": "TB-500 and BPC-157 appear in repair literature."},
        ],
    }
    updated, _report = link_products_in_article(
        article,
        {"TB-500": TB500_URL, "BPC-157": BPC157_URL},
    )
    takeaway = updated["key_takeaways"][0]
    body = updated["sections"][0]["content_markdown"]
    assert _count_product_links(body, "TB-500", TB500_URL) >= 1
    assert _count_product_links(takeaway, "TB-500", TB500_URL) == 0


def test_missing_inventory_url_left_plain() -> None:
    article = {"sections": [{"heading": "A", "content_markdown": "GHK-Cu appears in cosmetic literature."}]}
    updated, report = link_products_in_article(article, {"TB-500": TB500_URL})
    assert "GHK-Cu appears" in updated["sections"][0]["content_markdown"]
    assert report.total_links == 0


def test_rerun_idempotency() -> None:
    url_map = {"TB-500": TB500_URL, "BPC-157": BPC157_URL}
    first, _ = link_products_in_article(_comparison_article(), url_map)
    second, report = link_products_in_article(first, url_map)
    assert _article_blob(first) == _article_blob(second)
    assert report.total_links == sum(item["link_count"] for item in report.products.values())


def test_no_section_repeated_links_for_same_product() -> None:
    url_map = {"TB-500": TB500_URL, "BPC-157": BPC157_URL}
    updated, report = link_products_in_article(_comparison_article(), url_map)
    for section in updated.get("sections") or []:
        content = str(section.get("content_markdown") or "")
        assert _count_product_links(content, "TB-500", TB500_URL) <= 1
        assert _count_product_links(content, "BPC-157", BPC157_URL) <= 1
    for placement in report.placements:
        assert placement["section_key"]


def test_longest_name_match_wins_in_helper() -> None:
    text = "BPC-157 is distinct from other BPC shorthand uses."
    updated, linked = link_first_unlinked_mention(text, "BPC-157", BPC157_URL)
    assert linked
    assert f"[BPC-157]({BPC157_URL})" in updated
