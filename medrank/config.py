from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshot"                  # S3 同期先
DB_PATH = DATA_DIR / "researchers.db"                 # 本番 DB
DB_BUILD_PATH = DATA_DIR / "researchers.build.db"     # 構築中 DB

PORT = 8110
MIN_WORKS = 5
MIN_H = 2
CURRENT_YEAR = 2026          # ランキング・年次クリーニングの基準年(月次 ETL で更新)
RISING_MIN_RECENT = 200      # Rising Stars: 直近3年の被引用がこれ未満なら対象外(新規参入ノイズ除去)
RANKING_SIZE = 500           # 各ランキングの収録人数(表示は100件ずつページング)

HEALTH_DOMAIN = "domains/4"
BIOMED_DOMAIN = "domains/1"
BIOMED_FIELDS = {"fields/13", "fields/24", "fields/28"}

# 表示・URL 用の医療関連 field(id 短形 -> (slug, 表示名))
MEDICAL_FIELDS = {
    "fields/27": ("medicine", "Medicine"),
    "fields/29": ("nursing", "Nursing"),
    "fields/30": ("pharmacology", "Pharmacology, Toxicology & Pharmaceutics"),
    "fields/35": ("dentistry", "Dentistry"),
    "fields/36": ("health-professions", "Health Professions"),
    "fields/13": ("biochem-genetics", "Biochemistry, Genetics & Molecular Biology"),
    "fields/24": ("immunology-microbiology", "Immunology & Microbiology"),
    "fields/28": ("neuroscience", "Neuroscience"),
    "fields/32": ("psychology", "Psychology"),
}


# slug -> 正式表示名(UI・タイトル・パンくずで生 slug を出さない)
FIELD_NAMES = {slug: name for slug, name in MEDICAL_FIELDS.values()}

# slug -> 短縮表示名(ランキング行など幅の狭い場所用)
FIELD_SHORT = {
    "medicine": "Medicine",
    "nursing": "Nursing",
    "pharmacology": "Pharmacology",
    "dentistry": "Dentistry",
    "health-professions": "Health Professions",
    "biochem-genetics": "Biochemistry & Genetics",
    "immunology-microbiology": "Immunology & Microbiology",
    "neuroscience": "Neuroscience",
    "psychology": "Psychology",
}


def strip_oa_id(url):
    if url is None:
        return None
    return url.rsplit("/", 1)[-1]
