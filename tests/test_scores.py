from medrank.etl import scores


def test_rising_high_when_recent_growth():
    flat = [{"year": y, "cited_by_count": 10} for y in range(2016, 2026)]
    rising = [{"year": y, "cited_by_count": c}
              for y, c in zip(range(2016, 2026), [1, 1, 2, 2, 3, 5, 20, 40, 80, 160])]
    assert scores.rising_score(rising) > scores.rising_score(flat)


def test_rising_zero_for_empty():
    assert scores.rising_score([]) == 0.0


def test_consistency_high_for_steady():
    steady = [{"year": y, "cited_by_count": 50} for y in range(2016, 2026)]
    spiky = [{"year": y, "cited_by_count": c}
             for y, c in zip(range(2016, 2026), [0, 0, 0, 0, 0, 0, 0, 0, 0, 500])]
    assert scores.consistency_score(steady) > scores.consistency_score(spiky)
