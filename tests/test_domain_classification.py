from app.config import Settings
from app.domain_classification import classify_domain, partition_candidates_by_classification


def test_pubmed_classified_as_academic() -> None:
    profile = classify_domain("pubmed.ncbi.nlm.nih.gov", "https://pubmed.ncbi.nlm.nih.gov/")
    assert profile["classification"] == "academic_source"


def test_ncbi_root_domain_classified_as_academic() -> None:
    profile = classify_domain("ncbi.nlm.nih.gov", "https://www.ncbi.nlm.nih.gov/books/NBK56227/")
    assert profile["classification"] == "academic_source"


def test_nature_classified_as_authority() -> None:
    profile = classify_domain("nature.com", "https://www.nature.com/articles/example")
    assert profile["classification"] == "authority_source"


def test_reddit_classified_as_community() -> None:
    profile = classify_domain("reddit.com", "https://www.reddit.com/r/example")
    assert profile["classification"] == "community"


def test_telegram_classified_as_social_or_owned() -> None:
    profile = classify_domain("t.me", "https://t.me/example-lab")
    assert profile["classification"] == "social_or_owned"


def test_commercial_domain_classified_as_competitor() -> None:
    profile = classify_domain(
        "glowingpeptides.com",
        "https://glowingpeptides.com/",
        website_url="https://example.com",
    )
    assert profile["classification"] == "competitor"


def test_partition_keeps_only_competitors_in_pool() -> None:
    candidates = [
        {"url": "https://glowingpeptides.com", "origin": "web_search"},
        {"url": "https://pubmed.ncbi.nlm.nih.gov/", "origin": "web_search"},
        {"url": "https://www.ncbi.nlm.nih.gov/books/NBK56227/", "origin": "competitor_snapshot"},
        {"url": "https://reddit.com/r/test", "origin": "web_search"},
    ]
    pool, other, counts = partition_candidates_by_classification(
        candidates,
        website_url="https://example.com",
    )
    assert len(pool) == 1
    assert pool[0]["url"].startswith("https://glowingpeptides.com")
    assert len(other) == 3
    assert counts["competitor"] == 1
    assert counts["academic_source"] == 2
    assert counts["community"] == 1
