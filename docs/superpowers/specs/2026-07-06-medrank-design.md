# MedRank — 世界の医療研究者データベース & ランキング

**Status:** Design approved (2026-07-06)
**Owner:** d-ueda
**Repo:** `/srv/apps/researchers`

## 1. 目的

世界中の医療系研究者を網羅したデータベースを構築し、それを軸に多様なランキングを
Webサイトとして公開する。ゴールは「沢山の人に見てもらい、研究者を知ってもらう」こと。
主役は個々の研究者であり、サイトは「医療研究という営みの実像を、こぼさず・薄めず映す地図」を目指す。

### 世界観の確定事項
- **地図路線(網羅)** を採用。トップ数十万人の「名鑑」ではなく、各国・各分野の現場研究者まで拾う数百万人規模。
- 対象読者: グローバル(研究者・医療関係者・知的関心層)。**サイトの表示言語は英語のみ**。UIの日英切替はしない。
- 公開: 既存 Cloudflare Tunnel 相乗り。`researchers.med-ai.tech`(サブドメイン)。
- 更新: 月次(OpenAlex スナップショットに追随)。

## 2. データソースと「医療研究者」の定義

### ソース
- **OpenAlex authors parquet snapshot**(`s3://openalex/data/parquet/authors/`)。
  - 総容量 約 52.8GB、列指向、CC0、月次更新。公開バケット(`--no-sign-request`)。
  - works スナップショット(300GB超)は **不要**。著者レコードに必要な指標が全て含まれる。
- 著者レコードに含まれる利用フィールド:
  `id, orcid, display_name, works_count, cited_by_count,`
  `summary_stats(h_index, i10_index, 2yr_mean_citedness),`
  `affiliations, last_known_institutions, topics, x_concepts, counts_by_year(年別), updated_date`
- 補助スナップショット: `institutions/`, `countries/`, `fields/`, `domains/`, `topics/`(名称・階層の解決用)。

### 「医療研究者」の線引き(定義の心 = 臨床から実験台まで、人の健康に効く研究をしている人)
**含める:**
- 主要トピックのドメインが **Health Sciences (domain 4)** の著者(臨床医学・公衆衛生・看護・薬学・歯学 等)。
- **Life Sciences (domain 1)** のうち、主分野が以下の著者(=バイオメディカル基礎研究):
  - Biochemistry, Genetics and Molecular Biology (field 13)
  - Immunology and Microbiology (field 24)
  - Neuroscience (field 28)

**除外:** Life Sciences でも農学・植物生態・進化生物など人の健康から遠い分野。

**実在フィルタ(足切り):** `works_count >= 5` かつ `h_index >= 2`。
- 論文1〜2本の一時的著者・名寄せ残骸を落とす。「プロフィールページを持つ実質的研究者」に絞る。
- 閾値は意図的に低め。上げると先進国の年配研究者に偏り、途上国の若手・新興分野が消えるため。
- 想定規模: 概ね 200〜400万人。

### 既知のトレードオフ(初版は割り切る)
- 分野粒度で分類するため神経科学等に医療から遠いトピックが混入しうる。トピック単位の厳密分類は将来課題。
- 主分野は「その著者のトップトピックが属する field」で決定する。

## 3. アーキテクチャ

```
[月次 ETL]
  OpenAlex authors parquet (S3, 53GB)
       │  DuckDB: 医療ドメイン × 閾値でフィルタ、必要列のみ投影
       ▼
  researchers.db (SQLite)  ── researchers / institutions / countries
       │  ランキングを全て事前計算
       ▼
  rankings テーブル(順位を焼き込み済み) + FTS5 検索インデックス
       │
[配信]
  FastAPI + Jinja2 (SSR)  ── port 81xx (未使用ポートを選定, 例 8110)
       │  Cloudflare Tunnel ingress 追記
       ▼
  https://researchers.med-ai.tech
```

- **案A: SQLite + FastAPI SSR** を採用(依存最小・SEO最適・既存サーバー運用と親和)。
- **設計の肝:** リクエスト時に集計しない。ランキングは月次ETLで `rankings` テーブルに
  (ランキング種別, 順位, 研究者ID, 値)として全焼き込み。表示は
  `WHERE ranking_key=? ORDER BY rank LIMIT N` の単純読み取り。数百万人でもミリ秒応答。
- JSフレームワークは使わない。SSR HTML + 最小バニラJS(検索サジェスト・地図・スパークライン)。

## 4. データモデル(SQLite)

```sql
researchers            -- 1行=1研究者(ランキングの主役)
  id TEXT PK           -- OpenAlex A-id
  name, orcid
  h_index, cited_by_count, works_count, i10_index INTEGER
  two_year_mean_citedness REAL
  country_code, institution_id, institution_name
  primary_field, primary_topic
  first_pub_year, last_pub_year INTEGER
  counts_by_year TEXT  -- JSON: 年別 works / citations(トレンド計算元)
  rising_score, consistency_score, ... REAL  -- 事前計算した派生指標

institutions
  id PK, name, country_code, type
  researcher_count, total_citations INTEGER, top_field

countries
  code PK, name, researcher_count, median_h_index, total_citations

rankings               -- サイトが読むのは主にこれ
  ranking_key TEXT     -- 例 'h_index__global', 'citations__field=oncology__country=JP'
  rank INTEGER, researcher_id TEXT, value REAL, extra TEXT(JSON)
  PRIMARY KEY (ranking_key, rank)

researchers_fts        -- FTS5: name / institution / field の横断検索
```

派生指標の定義:
- `rising_score`: 直近3年の被引用増加率。キャリア年数で正規化。
- `consistency_score`: 毎年コンスタントに高被引用を出しているか(年次分散の逆)。
- 欠損機関の研究者は表示上 `Unaffiliated` とし、収録から落とさない。

## 5. ランキングカタログ(3系統)

**王道系**(分野 × 国でマトリクス展開 = SEO主戦力)
- h-index / 総被引用数 / 論文数 の 世界 × 国別 × 分野別。
- 例: 「Oncology 世界トップ100」「日本の循環器 h-index トップ50」。

**トレンド・勢い系**(`counts_by_year` から算出)
- Rising Stars: 直近3年の被引用増加率トップ(キャリア年数で正規化)。
- Momentum: 急上昇トピック × その牽引者。
- Young Guns: 初論文から10年以内で高インパクト。

**意外性・読み物系**(データジャーナリズム)
- 継続力ランキング(一発屋でない継続的高被引用)。
- グローバル・コラボレーター(所属遍歴・共著国数から近似する国際性)。
- 機関の隆盛(研究者輩出数・総インパクトで見る世界の研究拠点)。

各研究者に個別プロフィールページを持たせ、「その人が載る全ランキング」への内部リンクで
回遊性とSEOを両立する。

## 6. サイト構成(URL設計)

```
/                       トップ: 主要ランキングのハイライト + 検索窓 + 世界地図
/rankings               ランキング一覧(カタログのハブ)
/rankings/h-index                    世界トップ
/rankings/h-index/oncology           分野別
/rankings/h-index/oncology/jp        分野 × 国
/rankings/rising-stars , /consistency , ...
/researcher/A5023888391-jun-wang     個別プロフィール(数百万ページ = ロングテールSEO)
/institutions , /institutions/harvard-university-I136199984
/countries , /countries/jp           国別ダッシュボード
/search?q=...                        名前・機関・分野の横断検索(FTS5)
/about , /methodology                データ出所と指標定義(信頼性の担保)
```

- 全URLは静的・意味の読める形。canonical / 分割 sitemap.xml / 構造化データ(schema.org Person・
  ScholarlyArticle)/ OGP画像自動生成 を含む。
- `/methodology` を初版から用意。ランキングの根拠(OpenAlex CC0 データ、各指標の計算式)を公開し、
  リンクされ・信頼されるサイトにする。

## 7. デザイン方針

- **世界観:** 学術DBの無味乾燥さではなく、データジャーナリズム(FT / Economist / Our World in Data 系)の
  品格。信頼感が第一、その上で数字が動き出す楽しさ。
- **ビジュアル:** 紙のような落ち着いた背景 + 深いティール/クリムゾンのアクセント、セリフ見出し ×
  サンセリフ本文。ランキングは表ではなく「順位カード + ミニ年次スパークライン」で人に焦点。
  国別ページに塗り分け世界地図。
- **軽さ:** JSフレームワークなし。SSR + 最小バニラJS。モバイルファースト。Lighthouse 90点台維持
  (表示速度自体をSEO資産にする)。
- 実装時に `frontend-design` と `dataviz` スキルを使い、テンプレ感を排す。

## 8. エラー処理・運用

- ETLは冪等。新DBを別ファイルに構築 → 検証クエリ(件数・NULL率・重複)通過後にアトミック差し替え。
  失敗時は旧DBのまま無停止継続。
- 月次 cron + ログ。GPU/他パイプラインとは独立(CPU・I/Oのみ)。
- 権限: 既存方針に倣い d-ueda 編集・agent 実行が両立するよう setgid + group + umask を設定。

## 9. スコープ外(初版でやらないこと / YAGNI)
- 論文本文・全 works の取り込み(著者集計指標で足りる)。
- 日本語UI・多言語UI(英語のみ)。
- ユーザーアカウント・お気に入り・API公開。
- リアルタイム更新(月次で十分)。
- トピック単位の厳密な医療分類(初版は分野粒度)。

## 10. 成功基準
- 数百万人の医療研究者が収録され、全員に到達可能なプロフィールページがある。
- 3系統・分野 × 国のランキングが破綻なく表示され、ページ表示がミリ秒級。
- Lighthouse(パフォーマンス/SEO/アクセシビリティ)90点台。
- `/methodology` で全指標の根拠が説明されている。
- 月次 ETL が冪等で、失敗しても無停止。
