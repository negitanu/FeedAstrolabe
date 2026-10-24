"""Public social topic research, bounded successful-run history."""

SCHEMA = '''
CREATE TABLE social_topics (
 feed_id INTEGER PRIMARY KEY REFERENCES feeds(id) ON DELETE CASCADE,
 window_hours INTEGER NOT NULL DEFAULT 24 CHECK(window_hours BETWEEN 1 AND 168)
);
CREATE TABLE social_runs (
 id INTEGER PRIMARY KEY,
 feed_id INTEGER NOT NULL REFERENCES social_topics(feed_id) ON DELETE CASCADE,
 collected_at TEXT NOT NULL,
 window_start TEXT NOT NULL,
 sample_count INTEGER NOT NULL CHECK(sample_count BETWEEN 0 AND 200),
 new_count INTEGER NOT NULL CHECK(new_count BETWEEN 0 AND sample_count),
 hashtags TEXT NOT NULL
);
CREATE INDEX social_runs_feed ON social_runs(feed_id,id DESC);
CREATE TABLE social_results (
 run_id INTEGER NOT NULL REFERENCES social_runs(id) ON DELETE CASCADE,
 article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
 rank INTEGER NOT NULL CHECK(rank BETWEEN 1 AND 40),
 score INTEGER NOT NULL CHECK(score>=0),
 likes INTEGER NOT NULL CHECK(likes>=0),
 reposts INTEGER NOT NULL CHECK(reposts>=0),
 replies INTEGER NOT NULL CHECK(replies>=0),
 CHECK(score=likes+2*reposts+replies),
 PRIMARY KEY(run_id,article_id),
 UNIQUE(run_id,rank)
);
CREATE INDEX social_results_article ON social_results(article_id);
'''
