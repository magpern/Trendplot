from app.article_schema import normalize_article
from app.review.compliance_redundancy import apply_editorial_post_processing, reduce_compliance_repetition


def test_reduce_compliance_repetition_keeps_one_uncertainty_warning() -> None:
    payload = {
        "title": "BPC-157 overview",
        "sections": [
            {
                "heading": "Mechanisms",
                "content_markdown": (
                    "Evidence remains limited in preclinical models. "
                    "BPC-157 is discussed in repair literature."
                ),
            }
        ],
        "research_context": "Mechanism remains unsettled across model systems.",
        "limitations_and_safety": (
            "For research use only. Not intended for human consumption, therapeutic, or diagnostic use. "
            "Evidence remains limited and readers should be cautious when extrapolating findings."
        ),
    }
    cleaned = reduce_compliance_repetition(payload)
    blob = " ".join(
        [
            cleaned.get("research_context", ""),
            cleaned.get("limitations_and_safety", ""),
            cleaned["sections"][0]["content_markdown"],
        ]
    ).lower()
    assert blob.count("evidence remains limited") == 1
    assert "for research use only" in blob


def test_strip_buyer_language_for_comparison_article() -> None:
    article = normalize_article(
        {
            "title": "CJC-1295 vs Ipamorelin comparison",
            "sections": [
                {
                    "heading": "Mechanisms",
                    "content_markdown": (
                        "Buyers often compare catalog listings before selecting a peptide. "
                        "CJC-1295 No DAC and Ipamorelin differ in receptor engagement."
                    ),
                }
            ],
        },
        defaults={
            "title": "CJC-1295 vs Ipamorelin comparison",
            "target_keyword": "cjc-1295 vs ipamorelin",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://example.com/product/cjc-1295-no-dac-ipa/",
        },
    )
    processed = apply_editorial_post_processing(
        article,
        defaults={
            "title": "CJC-1295 vs Ipamorelin comparison",
            "target_keyword": "cjc-1295 vs ipamorelin",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://example.com/product/cjc-1295-no-dac-ipa/",
        },
        opportunity_context={"content_type": "comparison", "science_focus": True},
    )
    blob = processed.sections[0].content_markdown.lower()
    assert "buyer" not in blob
    assert "catalog" not in blob
    assert "receptor engagement" in blob


def test_strip_buyer_language_for_mechanism_article() -> None:
    article = normalize_article(
        {
            "title": "How CJC-1295 engages GHRH signaling",
            "sections": [
                {
                    "heading": "Signaling",
                    "content_markdown": (
                        "Shoppers evaluating supplier options should note preclinical models. "
                        "CJC-1295 No DAC modulates GHRH receptor pathways in vitro."
                    ),
                }
            ],
            "research_context": "Purchasing language should not appear in mechanism explainers.",
        },
        defaults={
            "title": "How CJC-1295 engages GHRH signaling",
            "target_keyword": "cjc-1295 mechanism",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://example.com/product/cjc-1295-no-dac-ipa/",
        },
    )
    processed = apply_editorial_post_processing(
        article,
        defaults={
            "title": "How CJC-1295 engages GHRH signaling",
            "target_keyword": "cjc-1295 mechanism",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://example.com/product/cjc-1295-no-dac-ipa/",
        },
        opportunity_context={"search_intent": "mechanism", "science_focus": True},
    )
    blob = " ".join(
        [
            processed.sections[0].content_markdown,
            processed.research_context,
        ]
    ).lower()
    assert "shopper" not in blob
    assert "supplier" not in blob
    assert "purchasing" not in blob
    assert "ghrh receptor pathways" in blob


def test_buyer_guide_article_keeps_commerce_language() -> None:
    article = normalize_article(
        {
            "title": "How to evaluate peptide suppliers",
            "sections": [
                {
                    "heading": "Evaluation",
                    "content_markdown": "Buyers should compare supplier evaluation checklists before purchasing.",
                }
            ],
        },
        defaults={
            "title": "How to evaluate peptide suppliers",
            "target_keyword": "peptide supplier evaluation",
            "product_name": "BPC-157",
            "product_url": "https://example.com/product/bpc-157/",
        },
    )
    processed = apply_editorial_post_processing(
        article,
        defaults={
            "title": "How to evaluate peptide suppliers",
            "target_keyword": "peptide supplier evaluation",
            "product_name": "BPC-157",
            "product_url": "https://example.com/product/bpc-157/",
        },
        opportunity_context={"content_type": "buyer_guide"},
    )
    assert "buyer" in processed.sections[0].content_markdown.lower()
    assert "supplier evaluation" in processed.sections[0].content_markdown.lower()


def test_strip_supplier_language_for_science_articles() -> None:
    article = normalize_article(
        {
            "title": "BPC-157 overview",
            "sections": [
                {
                    "heading": "Context",
                    "content_markdown": "Some writers focus on catalog language instead of biology.",
                }
            ],
            "research_context": "Signaling overview.",
        },
        defaults={"title": "BPC-157 overview", "target_keyword": "bpc-157", "product_name": "BPC-157", "product_url": "https://example.com/"},
    )
    processed = apply_editorial_post_processing(
        article,
        defaults={"title": "BPC-157 overview", "target_keyword": "bpc-157", "product_name": "BPC-157", "product_url": "https://example.com/"},
        opportunity_context={"science_focus": True, "content_type": "research_overview"},
    )
    assert "catalog language" not in processed.sections[0].content_markdown.lower()
