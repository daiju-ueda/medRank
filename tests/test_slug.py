from medrank.web import slug


def test_researcher_slug():
    assert slug.researcher_slug("A123", "Jun Wang") == "A123-jun-wang"
    assert slug.researcher_slug("A9", "José Å. Ñoño").startswith("A9-")


def test_id_from_slug_roundtrip():
    s = slug.researcher_slug("A5023888391", "Kazuo Tanaka")
    assert slug.id_from_slug(s) == "A5023888391"
    assert slug.id_from_slug("A9") == "A9"
