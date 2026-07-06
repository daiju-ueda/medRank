import json

from medrank.config import CURRENT_YEAR


def _series(counts, now_year=CURRENT_YEAR, span=11):
    if isinstance(counts, str):
        counts = json.loads(counts) if counts else []
    by_year = {c["year"]: c.get("cited_by_count", 0) for c in (counts or [])}
    years = list(range(now_year - span + 1, now_year + 1))
    return [by_year.get(y, 0) for y in years]


def sparkline(counts, width=104, height=28, now_year=CURRENT_YEAR):
    """counts_by_year(JSON か list)から年次被引用のインライン SVG を返す。"""
    vals = _series(counts, now_year)
    if not any(vals):
        return ""
    hi = max(vals) or 1
    n = len(vals)
    dx = width / (n - 1) if n > 1 else width
    pad = 3
    usable = height - pad * 2
    pts = [(i * dx, pad + usable - (v / hi) * usable) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"0,{height} " + line + f" {width},{height}"
    cx, cy = pts[-1]
    # 傾向で色分け: 直近3年 vs その前3年(1年目は不完全なことが多いので比較から除外)
    recent, prior = sum(vals[-4:-1]), sum(vals[-7:-4])
    trend = "spark-up" if recent >= prior else "spark-down"
    return (
        f'<svg class="spark {trend}" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'preserveAspectRatio="none" aria-hidden="true">'
        f'<polygon class="spark-area" points="{area}"/>'
        f'<polyline class="spark-line" points="{line}"/>'
        f'<circle class="spark-dot" cx="{cx:.1f}" cy="{cy:.1f}" r="2"/>'
        f'</svg>'
    )
