CREATE TABLE researchers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  orcid TEXT,
  h_index INTEGER NOT NULL,
  cited_by_count INTEGER NOT NULL,
  works_count INTEGER NOT NULL,
  i10_index INTEGER NOT NULL,
  two_year_mean_citedness REAL,
  country_code TEXT,
  institution_id TEXT,
  institution_name TEXT,
  primary_field TEXT,       -- field slug
  primary_topic TEXT,
  first_pub_year INTEGER,
  last_pub_year INTEGER,
  counts_by_year TEXT,      -- JSON
  rising_score REAL DEFAULT 0,
  consistency_score REAL DEFAULT 0
);
CREATE INDEX idx_res_country ON researchers(country_code);
CREATE INDEX idx_res_field ON researchers(primary_field);
CREATE INDEX idx_res_inst ON researchers(institution_id);

CREATE TABLE institutions (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, country_code TEXT, type TEXT,
  researcher_count INTEGER DEFAULT 0, total_citations INTEGER DEFAULT 0, top_field TEXT
);

CREATE TABLE countries (
  code TEXT PRIMARY KEY, name TEXT NOT NULL,
  researcher_count INTEGER DEFAULT 0, median_h_index REAL, total_citations INTEGER DEFAULT 0
);

CREATE TABLE rankings (
  ranking_key TEXT NOT NULL,
  rank INTEGER NOT NULL,
  researcher_id TEXT NOT NULL,
  value REAL NOT NULL,
  extra TEXT,
  PRIMARY KEY (ranking_key, rank)
);
CREATE INDEX idx_rankings_res ON rankings(researcher_id);

CREATE TABLE ranking_meta (
  ranking_key TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  category TEXT NOT NULL,   -- 'classic' | 'trend' | 'story'
  field TEXT, country TEXT, metric TEXT, size INTEGER
);

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
