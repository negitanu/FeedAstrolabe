"""Schema 18: durable feed positions and immutable provider identity."""
import json


def migrate(db):
    db.execute('''CREATE TABLE IF NOT EXISTS feed_positions (
        feed_id INTEGER PRIMARY KEY REFERENCES feeds(id) ON DELETE CASCADE,
        position INTEGER NOT NULL CHECK(position>=0))''')
    db.execute('''INSERT OR IGNORE INTO feed_positions SELECT id,
        row_number() OVER(PARTITION BY folder ORDER BY title,id)-1 FROM feeds''')
    db.execute('''CREATE TRIGGER IF NOT EXISTS feed_position_insert AFTER INSERT ON feeds BEGIN
        INSERT INTO feed_positions(feed_id,position) VALUES(NEW.id,
        coalesce((SELECT max(p.position)+1 FROM feed_positions p JOIN feeds f ON f.id=p.feed_id WHERE f.folder=NEW.folder),0));
    END''')
    if 'provider' not in {r[1] for r in db.execute('PRAGMA table_info(social_ai_config)')}:
        db.execute("ALTER TABLE social_ai_config ADD COLUMN provider TEXT NOT NULL DEFAULT 'openrouter' CHECK(provider IN ('openrouter','orcarouter'))")
    db.execute('CREATE TABLE IF NOT EXISTS ai_provider_settings(provider TEXT PRIMARY KEY, settings TEXT NOT NULL)')
    cfg = dict(db.execute('SELECT * FROM social_ai_config').fetchone())
    db.execute('INSERT OR IGNORE INTO ai_provider_settings VALUES(?,?)', ('openrouter',json.dumps(cfg)))
    columns = {r[1] for r in db.execute('PRAGMA table_info(social_ai_jobs)')}
    db.execute('''CREATE TRIGGER IF NOT EXISTS feed_position_insert AFTER INSERT ON feeds BEGIN
        INSERT INTO feed_positions(feed_id,position) VALUES(NEW.id,
        coalesce((SELECT max(p.position)+1 FROM feed_positions p JOIN feeds f ON f.id=p.feed_id WHERE f.folder=NEW.folder),0));
    END''')
    if 'provider' not in columns:
        db.execute("ALTER TABLE social_ai_jobs ADD COLUMN provider TEXT NOT NULL DEFAULT 'openrouter'")
    if 'config_snapshot' not in columns:
        db.execute("ALTER TABLE social_ai_jobs ADD COLUMN config_snapshot TEXT NOT NULL DEFAULT '{}'")
