from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Nav-label blocklist
# ---------------------------------------------------------------------------

NAV_LABEL_BLOCKLIST = frozenset(
    {
        # Original structural nav labels
        "shop",
        "store",
        "home",
        "about",
        "about us",
        "contact",
        "contact us",
        "why us",
        "product variations",
        "products",
        "cart",
        "checkout",
        "privacy",
        "terms",
        "blog",
        "menu",
        "login",
        "sign in",
        "sign up",
        "faq",
        "services",
        "portfolio",
        "gallery",
        # Commerce / ecommerce navigation
        "shopping bag",
        "shopping cart",
        "best sellers",
        "best-selling",
        "bundle and save",
        "collection",
        "collections",
        "essentials",
        "new arrivals",
        "all products",
        "search results",
        "on sale",
        "clearance",
        "gift cards",
        "apparel",
        "accessories",
        # UI / meta / site-chrome
        "about me",
        "what we do",
        "what we don't",
        "read me first",
        "our story",
        "our mission",
        "our team",
        "meet the team",
        "our values",
        "our work",
        "press",
        "trending",
        "trending now",
        "popular posts",
        "recent posts",
        "featured",
        "latest",
        "most read",
        "editor's pick",
        # Account / platform
        "my account",
        "account",
        "dashboard",
        "settings",
        "notifications",
        "inbox",
        # Pass 2 additions
        "frequently asked questions",  # long form of "faq"
        "about the author",            # competitor/blog bio navigation
        "about the team",
    }
)

GENERIC_PAGE_PATTERNS = re.compile(
    r"^(page|section|block|widget|footer|header|nav|sidebar|about\s+the)\b",
    re.IGNORECASE,
)

# Patterns that identify FAQ meta-labels regardless of trailing text
_NAV_FAQ_PREFIX_RE = re.compile(
    r"^(?:frequently\s+asked|common\s+questions?|faqs?)\b",
    re.IGNORECASE,
)


def normalize_topic_label(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").strip())
    return cleaned.strip(" -_|/")


def is_navigation_label(value: str) -> bool:
    raw = normalize_topic_label(value)
    label = raw.lower()
    if not label or len(label) < 3:
        return True
    if label in NAV_LABEL_BLOCKLIST:
        return True
    if GENERIC_PAGE_PATTERNS.match(label):
        return True
    if _NAV_FAQ_PREFIX_RE.match(label):
        return True
    words = label.split()
    if len(words) == 1 and len(label) <= 5:
        # Exempt all-uppercase acronyms (API, SEO, AWS, SQL …) from the short-token gate.
        if raw.isupper():
            return False
        return True
    return False


# ---------------------------------------------------------------------------
# Generic structural / ops / meta tokens
# ---------------------------------------------------------------------------

GENERIC_STRUCTURAL_TERMS = frozenset(
    {
        # Original ops/meta tokens
        "customer",
        "customers",
        "client",
        "clients",
        "user",
        "users",
        "fulfillment",
        "fulfilment",
        "ordering",
        "order",
        "orders",
        "checkout",
        "shipping",
        "delivery",
        "returns",
        "refund",
        "refunds",
        "payment",
        "payments",
        "account",
        "login",
        "register",
        "signup",
        "wishlist",
        "newsletter",
        "subscribe",
        "glossary",
        "comparison",
        "comparisons",
        "overview",
        "introduction",
        "product",
        "products",
        "variation",
        "variations",
        "research",
        "compound",
        "compounds",
        "practical",
        "bookshelf",
        "characteristics",
        "laboratory",
        "lab",
        "focused",
        "european",
        "popular",
        "professional",
        "professionals",
        "trusted",
        "tested",
        "secure",
        "service",
        "services",
        "support",
        "quality",
        "selection",
        "variety",
        "options",
        "general",
        "misc",
        "question",
        "questions",
        "discussion",
        "discussions",
        "info",
        "information",
        # New: common English words that are never article topics alone
        "according",
        "available",
        "builder",
        "content",
        "everyday",
        "experience",
        "implementation",
        "media",
        "official",
        "provider",
        "providers",
        "sourcing",
        "trending",
        "typical",
        "various",
        # Structural/ops additions
        "category",
        "categories",
        "feature",
        "features",
        "benefit",
        "benefits",
        "solution",
        "solutions",
        "approach",
        "process",
        "method",
        "methods",
        "platform",
        "platforms",
        "system",
        "systems",
        "number",
        "data",
        "tool",
        "tools",
        # Pass 2 additions: observed single-word junk across all new verticals
        "articles",
        "company",
        "enterprise",
        "generic",
        "manager",
        "measure",
        "others",
        "presentations",
        "understand",
        "website",
        "beginner",
        # Pass 3 additions: single-word generic adjectives, verbs, and adverbs
        "alternative",
        "analytics",    # standalone — too broad; compound "web analytics" still valid
        "arrivals",
        "award-winning",
        "domain-specific",
        "frequently",
        "individual",
        "interview",
        "languages",
        "premium",
        "protect",
        "shopping",
        "topic",
        "topics",
        "visitors",
        # Pass 4 additions: final micro-pass based on cross-vertical validation evidence
        # Generic verbs / adjectives observed as standalone topics
        "additional",   # adjective, not a topic
        "capacity",     # too broad alone; "backpack capacity" / "storage capacity" remain valid
        "complete",     # adjective
        "development",  # too broad alone; "software development" / "web development" remain valid
        "follow",       # generic verb (social-media follow context)
        "government",   # too broad alone; "government compliance" etc. remain valid
        "interface",    # too broad alone; "user interface" / "API interface" remain valid
        # NOTE: "security" deliberately NOT added — legitimately relevant on software/privacy sites
        # NOTE: "management" deliberately NOT added — legitimate for engineering leadership content
    }
)

# Trailing meta/structural words that mark a label rather than an article topic.
META_SUFFIX_PATTERN = re.compile(
    r"\b(discussions?|questions?|page|section|overview|labels?|"
    r"comparison\s+table|comparison\s+guide|comparison\s+chart)\s*$",
    re.IGNORECASE,
)

# SKU / variant / dosage labels (generic, niche-agnostic).
VARIANT_PATTERN = re.compile(
    r"\bno\s+dac\b"
    r"|\+\s*ipa\b"
    r"|\bdosages?\b"
    r"|\bvariants?\b"
    r"|\bconcentrations?\b"
    r"|\b\d+\s*(?:mg|mcg|ug|µg|iu|ml|%)\b"
    r"|\s\d+\s*$",  # SKU/version suffix: "TRAVEL 4", "PACK 30"
    re.IGNORECASE,
)


def is_implausible_token(value: str) -> bool:
    """Conservative orthographic gate for clearly malformed single tokens.

    Niche-agnostic and intentionally narrow: it flags gibberish-like tokens (no vowels,
    pathological character repetition) without a dictionary, because a general English
    lexicon would wrongly reject valid domain entities (e.g. ``angiogenesis``,
    ``BPC-157``). It does NOT catch plausible-looking misspellings (e.g. ``bactriostatic``
    vs ``bacteriostatic``); reliable detection of those needs a domain lexicon or an LLM
    and is a documented deterministic limitation."""
    label = normalize_topic_label(value)
    if not label or " " in label:
        return False
    letters = [c for c in label.lower() if c.isalpha()]
    if len(letters) < 5:
        return False  # short tokens / acronyms handled by other gates
    if not any(c in "aeiouy" for c in letters):
        return True  # no vowel in a 5+ letter token
    if re.search(r"(.)\1\1", label.lower()):
        return True  # 3+ identical characters in a row
    return False


def is_generic_fragment(value: str) -> bool:
    """True for generic structural/ops/meta tokens, variant/SKU labels, all-generic
    phrases, and clearly malformed tokens. Niche-agnostic; used to keep junk out of the
    seed pool upstream of EOG."""
    label = normalize_topic_label(value)
    if not label:
        return True
    lower = label.lower()
    if VARIANT_PATTERN.search(lower):
        return True
    if META_SUFFIX_PATTERN.search(lower):
        return True
    if is_implausible_token(label):
        return True
    words = lower.split()
    if len(words) == 1 and lower in GENERIC_STRUCTURAL_TERMS:
        return True
    if words and all(word in GENERIC_STRUCTURAL_TERMS for word in words):
        return True
    return False


# ---------------------------------------------------------------------------
# Price / promotional value filter (new in Entity Quality Hardening Pass 1)
# ---------------------------------------------------------------------------

_PRICE_OR_PROMO_RE = re.compile(
    r"""
    (?:
        [\$€£¥]\s*\d              # $15, €9
      | \d[\$€£¥]                 # 15$
      | \d+\s*/\s*(?:month|year|week|day)s?   # 15/month, 150/year
      | \d+\s*(?:months?|years?|weeks?|days?)\s+free  # 2 months free
      | \d+\s*%\s*(?:off|discount|savings?)           # 20% off
      | free\s+(?:shipping|trial|plan|access)         # free shipping
      | \bsave\s+\d                                    # save 30
      | \bdiscount\s+codes?\b                         # discount code
      | \bpromo\s+codes?\b                            # promo code
      | \bcoupon\s+codes?\b                           # coupon code
      | \bspecial\s+offer\b                           # special offer
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def is_price_or_promo(value: str) -> bool:
    """True for price points, monetary values, promo phrases, and percentage-off strings.

    Catches fragments like '15/month', '€150/year', '2 MONTHS FREE', '20% OFF', and
    'free shipping' that are crawled from SaaS pricing pages and ecommerce banners."""
    label = normalize_topic_label(value)
    if not label:
        return False
    return bool(_PRICE_OR_PROMO_RE.search(label))


# ---------------------------------------------------------------------------
# CTA / marketing sentence filter (new in Entity Quality Hardening Pass 1)
# ---------------------------------------------------------------------------

_CTA_IMPERATIVE_START_RE = re.compile(
    r"^(?:"
    r"get\s+started|sign\s+up|sign\s+in|log\s+in|login|register\b|subscribe\b|"
    r"read\s+more|learn\s+more|click\s+here|find\s+out\s+more|"
    r"contact\s+us|start\s+(?:here|now|today|free)|"
    r"try\s+(?:it\s+)?(?:free|now|today)|"
    r"buy\s+now|shop\s+now|order\s+now|add\s+to\s+(?:cart|bag)|"
    r"request\s+(?:a\s+)?demo|book\s+(?:a\s+)?(?:demo|call|consultation)|"
    r"get\s+in\s+touch|schedule\s+(?:a\s+)?(?:call|demo)|"
    r"unlock\b|explore\s+(?:our\s+|the\s+)?(?:features|plans|pricing)|"
    r"join\s+(?:us\b|now\b|free\b|today\b)|"
    r"create\s+(?:an?\s+)?account|don'?t\s+have\s+an?\s+|"
    r"new\s+to\s+.{1,40}[?]\s*start\s+here|"
    r"read\s+me\s+first|see\s+all\s+|"
    # Pass 2: broader negative imperative ("Don't replace your X", "Don't overfit")
    r"don'?t\s+[a-z]|"
    # Pass 2: numbered list items scraped from competitor pages ("1. Terms", "2. Privacy")
    r"\d+\.\s+"
    r")",
    re.IGNORECASE,
)

_CTA_QUESTION_RE = re.compile(
    r"^(?:unsure|not\s+sure|ready\s+to|looking\s+to|need\s+help\s+with|"
    r"wondering\s+(?:if|how|what|why)|want\s+to\s+know|"
    r"have\s+(?:a\s+)?question)\b.{3,}\?$",
    re.IGNORECASE,
)

# Phrases that are clearly marketing taglines / non-topics
_MARKETING_TAGLINE_RE = re.compile(
    r"^(?:different\b.*\bgood\s+way|"
    r"simple\b.*\bpowerful|"
    r"all-in-one\s+solution|"
    r"the\s+(?:easiest|fastest|best|simplest)\s+way\s+to\b|"
    r"works\s+(?:with|for)\s+(?:all|any|your)|"
    r"built\s+(?:for|with)\s+(?:teams|developers|creators)|"
    r"(?:trusted|used|loved)\s+by\s+(?:thousands|millions|\d+)|"
    r"(?:no\s+(?:credit\s+card|contract|setup)\s+required)"
    r")",
    re.IGNORECASE,
)


def is_cta_phrase(value: str) -> bool:
    """True for CTA buttons, marketing imperatives, leading-question sentences, and
    taglines that are crawled from landing pages but are not editorial topics.

    Catches fragments like 'Ready to simplify your analytics?', 'Get started',
    'Don't have an account?', and 'Different. In a good way.'"""
    label = normalize_topic_label(value)
    if not label:
        return False
    if _CTA_IMPERATIVE_START_RE.match(label):
        return True
    if _CTA_QUESTION_RE.match(label):
        return True
    if _MARKETING_TAGLINE_RE.match(label):
        return True
    return False


# ---------------------------------------------------------------------------
# Competitor UI / taxonomy text filter (new in Entity Quality Hardening Pass 1)
# ---------------------------------------------------------------------------

_COMPETITOR_TAXONOMY_RE = re.compile(
    r"^(?:articles?|posts?|podcasts?|presentations?|news|videos?|webinars?|"
    r"tutorials?|courses?|books?|resources?|events?|guides?|talks?|"
    r"case\s+studies?|white\s*papers?)\s+about\b",
    re.IGNORECASE,
)

_COMPETITOR_ACCOUNT_RE = re.compile(
    r"(?:don'?t\s+have|create|need)\s+.{0,20}(?:account|login|profile)\b"
    r"|unlock\s+.{0,30}(?:experience|access|content|platform)\b"
    r"|(?:sign\s+up|register)\s+to\s+(?:read|access|get|view)\b"
    r"|\bto\s+read\s+this\s+(?:article|post|story)\b"
    r"|\bpaid\s+subscribers?\s+only\b"
    r"|\bsubscribe\s+to\s+(?:read|access|unlock)\b",
    re.IGNORECASE,
)


def is_competitor_ui_text(value: str) -> bool:
    """True for competitor taxonomy navigation labels and account/login/paywall prompts.

    Catches fragments like 'Articles about Microservices', 'Podcasts about Service Mesh',
    'Don't have an InfoQ account?', and 'Unlock the full InfoQ experience' that are
    scraped from competitor pages and should never become article recommendations."""
    label = normalize_topic_label(value)
    if not label:
        return False
    if _COMPETITOR_TAXONOMY_RE.match(label):
        return True
    if _COMPETITOR_ACCOUNT_RE.search(label):
        return True
    return False


# ---------------------------------------------------------------------------
# Sentence-fragment / possessive-pronoun fragment filter (new Pass 1)
# ---------------------------------------------------------------------------

_POSSESSIVE_FRAGMENT_RE = re.compile(
    r"^(?:your|our|my|their|its|this|that|these|those|others)\s+\S",
    re.IGNORECASE,
)

_CONJUNCTION_FRAGMENT_RE = re.compile(
    r"^(?:and|or|but|so|yet|for|nor|although|however|therefore)\s+",
    re.IGNORECASE,
)


def is_possessive_or_conjunction_fragment(value: str) -> bool:
    """True for short fragments that start with a possessive pronoun or coordinating
    conjunction — these are typically scraped sentence fragments, not article topics.

    Catches 'your time', 'and your visitors'', 'this is how the gap shows up',
    but only when the phrase is short (≤5 words) to avoid blocking longer topics
    that legitimately start with these words."""
    label = normalize_topic_label(value)
    if not label:
        return False
    words = label.split()
    if len(words) > 5:
        return False  # longer phrases may legitimately start with these words
    if _POSSESSIVE_FRAGMENT_RE.match(label):
        return True
    if _CONJUNCTION_FRAGMENT_RE.match(label):
        return True
    return False


# ---------------------------------------------------------------------------
# Overly-long entity filter (new Pass 1)
# ---------------------------------------------------------------------------

MAX_ENTITY_LABEL_LENGTH = 55


def is_overly_long_entity(value: str) -> bool:
    """True for labels exceeding the practical maximum for an article topic.

    Long labels (>90 chars) are typically scraped product titles, pulled page titles,
    or multi-sentence fragments — not coherent article topics.

    Example caught: 'Travel Backpack Pro 40L by Tortuga Award-Winning Carry On Bag'"""
    label = normalize_topic_label(value)
    return len(label) > MAX_ENTITY_LABEL_LENGTH


# ---------------------------------------------------------------------------
# Question-entity filter (new in Entity Quality Hardening Pass 3)
# ---------------------------------------------------------------------------


def is_question_entity(value: str) -> bool:
    """True for entities that end with ``?``, indicating they are questions or headlines
    rather than noun-phrase article topics.

    Source entities should be noun phrases. Strings like ``'Firebase?'`` or
    ``'Is High Quality Software Worth the Cost?'`` are questions scraped from
    FAQ sections or competitor pages, not domain concepts."""
    label = normalize_topic_label(value)
    return bool(label) and label.endswith("?")


# ---------------------------------------------------------------------------
# Marketing comparison fragment filter (new in Entity Quality Hardening Pass 3)
# ---------------------------------------------------------------------------

_MARKETING_COMPARISON_END_RE = re.compile(
    r"(?:"
    r"\s+(?:does|is|are|was|were)\s*$"           # bare present/past verb: "X does", "X is"
    r"|\s+a\s+better\s+(?:choice|alternative|option|pick|fit)\s*$"  # "a better choice"
    r"|\s+the\s+best\s*$"                          # "the best"
    r"|\s+(?:beats?|wins?)\s*$"                    # "beats", "wins"
    r")",
    re.IGNORECASE,
)


def is_marketing_comparison_fragment(value: str) -> bool:
    """True for entities that are marketing comparison sentence fragments scraped
    from competitor comparison/review pages.

    Catches ``'Simple Analytics does'``, ``'Matomo is a better choice'``,
    ``'Competitor beats the rest'`` — incomplete comparative sentences that end
    with a bare verb or comparative phrase rather than a noun."""
    label = normalize_topic_label(value)
    if not label:
        return False
    return bool(_MARKETING_COMPARISON_END_RE.search(label))


# ---------------------------------------------------------------------------
# Site-title separator / emoji filter (new in Entity Quality Hardening Pass 2)
# ---------------------------------------------------------------------------

_SITE_TITLE_SEPARATOR_RE = re.compile(
    r"\s+[|]\s+|\s+—\s+|\s+–\s+",  # " | ", " — ", " – "
    re.UNICODE,
)


def _has_emoji(value: str) -> bool:
    for char in value:
        cp = ord(char)
        if (
            0x1F000 <= cp <= 0x1FAFF  # All main emoji planes (incl. 🆕 U+1F195, 🔧 U+1F527)
            or 0x2600 <= cp <= 0x27BF  # Misc Symbols and Dingbats
            or 0xFE00 <= cp <= 0xFE0F  # Variation Selectors
        ):
            return True
    return False


def is_site_title_string(value: str) -> bool:
    """True for competitor site titles and page headers scraped as entities.

    Detects pipe separators (``Aer | The best travel gear …``), spaced em/en-dashes
    (``Best Sellers — Aer``), and emoji labels (``New Arrivals 🆕 Aer``).  These are
    page/site chrome strings, not editorial topics."""
    label = normalize_topic_label(value)
    if not label:
        return False
    if _SITE_TITLE_SEPARATOR_RE.search(label):
        return True
    if _has_emoji(label):
        return True
    return False


# ---------------------------------------------------------------------------
# Sentence-fragment filter (new in Entity Quality Hardening Pass 2)
# ---------------------------------------------------------------------------

# Questions using personal pronouns or interrogative-aux constructs
_PERSONAL_QUESTION_START_RE = re.compile(
    r"^(?:"
    r"(?:can|could|should|would|do|does|did)\s+(?:i|you|we|they|it|he|she|my|your|our|us)\b"
    r"|(?:is|are|was|were)\s+(?:this|that|there|it|my|your|our|their|he|she)\b"
    r"|where\s+(?:is|are|was|were|do|does|did|can|your|my|our|their)\b"
    r")",
    re.IGNORECASE,
)

# "This is …", "That was …" — demonstrative-verb sentence openers
_DEMONSTRATIVE_SENTENCE_RE = re.compile(
    r"^(?:this|that|these|those)\s+(?:is|are|was|were|has|have|had|will|would|can)\b",
    re.IGNORECASE,
)

# "How [CapitalisedProperNoun…] [past-tense-narrative-verb]" — competitor case study titles
_COMPETITOR_HOW_STORY_RE = re.compile(
    r"^[Hh]ow\s+[A-Z]\w+(?:\s+[A-Z]\w+)*\s+"
    r"(?:helped|used|built|created|made|achieved|improved|solved|"
    r"transformed|grew|scaled|reduced|increased|became|went|got|launched|shipped)\b",
)

# "[text]: The/A/An [text]" — article subtitle / book headline structure
_ARTICLE_SUBTITLE_RE = re.compile(
    r":\s+(?:the|a|an)\s+\w",
    re.IGNORECASE,
)

# Ends with "?" AND contains a personal pronoun → support/FAQ question, not an entity
_PERSONAL_QUESTION_END_RE = re.compile(
    r"\b(?:i|me|my|you|your|we|our|they|their)\b.*\?\s*$",
    re.IGNORECASE,
)


def is_sentence_fragment(value: str) -> bool:
    """True for sentence-like phrases that are not editorial topic noun-phrases.

    Catches: interrogative support questions (``Can I downgrade at any time?``),
    demonstrative sentence starts (``This is how the gap shows up …``), competitor
    case-study article titles (``How Matomo helped Concrete CMS achieve …``), article
    subtitle headline patterns (``The Root Cause: The Perceptual Gap``), multi-sentence
    fragments (internal period followed by capital letter), and phrases ending with
    a ``?`` that contain personal pronouns."""
    label = normalize_topic_label(value)
    if not label:
        return False
    # Personal-pronoun questions and interrogative sentence structures
    if _PERSONAL_QUESTION_START_RE.match(label):
        return True
    # "This is how …" / "That was when …"
    if _DEMONSTRATIVE_SENTENCE_RE.match(label):
        return True
    # Ends with "?" and contains a personal pronoun → support FAQ question
    if label.endswith("?") and _PERSONAL_QUESTION_END_RE.search(label):
        return True
    # "How [NamedEntity] [past_narrative_verb] …" — competitor case study title
    if _COMPETITOR_HOW_STORY_RE.match(label):
        return True
    # "[Noun Phrase]: The/A/An [Noun Phrase]" — article subtitle/headline
    if _ARTICLE_SUBTITLE_RE.search(label):
        return True
    # Multi-sentence scrape (contains ". " followed by uppercase letter)
    if re.search(r"\.\s+[A-Z]", label):
        return True
    return False


# ---------------------------------------------------------------------------
# Generic science / template-fragment entities (business alignment tier 5)
# ---------------------------------------------------------------------------

GENERIC_SCIENCE_CONCEPT_TERMS = frozenset(
    {
        "bookshelf",
        "practical",
        "characteristics",
        "introduction",
        "internet",
        "facebook",
        "adhesives",
        "analysis",
        "understanding scientific",
        "understanding the scientific interest",
        "experimental design",
        "lab reproducibility",
        "reproducibility",
        "new readers",
        "focused",
        "fulfillment",
        "information",
        "according",
        "questions answered",
    }
)

_GENERIC_SCIENCE_PHRASE_RE = re.compile(
    r"\b(understanding the scientific interest|introduction to|how researchers approach|"
    r"a practical guide to|for new readers)\b",
    re.I,
)


def is_generic_science_concept_entity(value: str) -> bool:
    """Tier-5 junk: template fragments, generic science meta-concepts, not catalog topics."""
    label = normalize_topic_label(value)
    if not label:
        return True
    lower = label.lower()
    if lower in GENERIC_SCIENCE_CONCEPT_TERMS:
        return True
    if _GENERIC_SCIENCE_PHRASE_RE.search(lower):
        return True
    if lower.startswith("what is what is "):
        return True
    return False


# ---------------------------------------------------------------------------
# Combined top-level entity quality check (new Pass 1)
# ---------------------------------------------------------------------------

def is_entity_quality_junk(value: str) -> bool:
    """Combined entity quality gate. Returns True for any value that should never
    become an article topic seed, regardless of niche or vertical.

    Replaces ad-hoc calls to individual predicates with a single authoritative check.
    All individual predicates remain public for targeted use."""
    if is_price_or_promo(value):
        return True
    if is_cta_phrase(value):
        return True
    if is_competitor_ui_text(value):
        return True
    if is_question_entity(value):
        return True
    if is_marketing_comparison_fragment(value):
        return True
    if is_site_title_string(value):
        return True
    if is_sentence_fragment(value):
        return True
    if is_possessive_or_conjunction_fragment(value):
        return True
    if is_overly_long_entity(value):
        return True
    if is_navigation_label(value):
        return True
    if is_generic_fragment(value):
        return True
    if is_generic_science_concept_entity(value):
        return True
    return False


# ---------------------------------------------------------------------------
# Orphan-fragment and nav-reframe helpers (unchanged)
# ---------------------------------------------------------------------------

def filter_orphan_fragments(labels: list[str]) -> list[str]:
    """Drop single-token labels that are only a *modifier* of a longer multi-word entity.

    Generic, deterministic, dictionary-free: if ``"cellular stress"`` is present, the
    orphan token ``"cellular"`` (a non-final modifier) is dropped while the full phrase is
    kept. Head nouns and standalone entities are preserved (e.g. ``"inflammation"`` is kept
    even if ``"chronic inflammation"`` exists, because it is the final/head token)."""
    normalized = [normalize_topic_label(item) for item in labels]
    normalized = [item for item in normalized if item]
    modifier_tokens: set[str] = set()
    for label in normalized:
        tokens = label.lower().split()
        if len(tokens) >= 2:
            modifier_tokens.update(tokens[:-1])  # non-final positions are modifiers
    kept: list[str] = []
    for label in normalized:
        tokens = label.lower().split()
        if len(tokens) == 1 and tokens[0] in modifier_tokens:
            continue
        kept.append(label)
    return kept


def audience_topic_from_nav(niche: str, label: str) -> str | None:
    """Reframe weak nav labels into audience-facing topics when possible."""
    niche_clean = normalize_topic_label(niche)
    label_clean = normalize_topic_label(label)
    lower = label_clean.lower()
    if lower == "shop":
        return f"how to choose {niche_clean} products" if niche_clean else "buying guide for niche products"
    if lower in {"why us", "about us", "about"}:
        return f"what to look for in a {niche_clean} provider" if niche_clean else None
    if lower == "product variations":
        return f"{niche_clean} types and comparisons" if niche_clean else "product types and comparisons"
    return None
