from app.services.geo.analysis import detect_citation, detect_competitor_mentions


def test_cited_via_matching_citation_url():
    result = detect_citation(
        domain="seorepairkit.com",
        brand_name=None,
        text="Some other tool is best.",
        citation_urls=["https://competitor.com/", "https://seorepairkit.com/pricing"],
    )
    assert result.cited is True
    assert result.cited_via_url is True
    assert result.position == 2


def test_cited_via_brand_name_mention_only():
    result = detect_citation(
        domain="seorepairkit.com",
        brand_name="SEO Repair Kit",
        text="I'd recommend SEO Repair Kit for developers.",
        citation_urls=[],
    )
    assert result.cited is True
    assert result.cited_via_url is False
    assert result.mentioned_in_text is True
    assert result.position is None


def test_not_cited_at_all():
    result = detect_citation(
        domain="seorepairkit.com",
        brand_name="SEO Repair Kit",
        text="Screaming Frog and Sitebulb are popular choices.",
        citation_urls=["https://screamingfrog.co.uk/"],
    )
    assert result.cited is False


def test_www_prefix_is_normalized_both_directions():
    result = detect_citation(
        domain="www.seorepairkit.com",
        brand_name=None,
        text="",
        citation_urls=["https://seorepairkit.com/"],
    )
    assert result.cited_via_url is True


def test_domain_mention_in_text_without_brand_name():
    result = detect_citation(
        domain="seorepairkit.com",
        brand_name=None,
        text="Check out seorepairkit.com for a free audit.",
        citation_urls=[],
    )
    assert result.mentioned_in_text is True
    assert result.cited is True


def test_detect_competitor_mentions_mixed_results():
    # Competitor matching is domain-based only (no per-competitor brand
    # name in the data model) -- a narrative brand mention like "Semrush"
    # without the domain string or a citation URL doesn't count.
    mentions = detect_competitor_mentions(
        competitor_domains=["ahrefs.com", "semrush.com", "screamingfrog.co.uk"],
        text="Ahrefs and semrush.com are the two biggest names in this space.",
        citation_urls=["https://ahrefs.com/blog"],
    )
    assert mentions == {"ahrefs.com": True, "semrush.com": True, "screamingfrog.co.uk": False}
