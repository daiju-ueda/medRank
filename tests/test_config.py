from medrank import config


def test_thresholds_and_port():
    assert config.MIN_WORKS == 5
    assert config.MIN_H == 2
    assert config.PORT == 8110


def test_strip_oa_id():
    assert config.strip_oa_id("https://openalex.org/A5023888391") == "A5023888391"
    assert config.strip_oa_id("A123") == "A123"
    assert config.strip_oa_id(None) is None


def test_medical_domains():
    assert config.HEALTH_DOMAIN == "domains/4"
    assert config.BIOMED_FIELDS == {"fields/13", "fields/24", "fields/28"}
