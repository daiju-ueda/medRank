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


def test_career_start_skips_misattributed_tail():
    counts = ([{"year": y, "works_count": 1, "cited_by_count": 0} for y in (1903, 1911, 1950)]
              + [{"year": y, "works_count": 200, "cited_by_count": 500} for y in range(2015, 2025)])
    # 早期の1本エントリは無視し、本格稼働年を返す
    assert scores.career_start(counts) >= 2015


def test_career_start_none_for_empty():
    assert scores.career_start([]) is None


def test_rising_requires_recent_volume():
    # 直近3年で急伸していても絶対量が小さければ 0(新規参入ノイズ除去)
    tiny = [{"year": y, "cited_by_count": c}
            for y, c in zip(range(2020, 2027), [0, 0, 0, 1, 5, 20, 50])]
    assert scores.rising_score(tiny) == 0.0
    big = [{"year": y, "cited_by_count": c}
           for y, c in zip(range(2020, 2027), [50, 60, 80, 100, 300, 500, 800])]
    assert scores.rising_score(big) > 0
