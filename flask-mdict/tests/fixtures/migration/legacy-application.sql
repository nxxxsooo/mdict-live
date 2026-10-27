CREATE TABLE history(word TEXT PRIMARY KEY, count INT, last_time DATETIME);
CREATE TABLE setting(name TEXT PRIMARY KEY, value TEXT);
CREATE TABLE wordbook(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE wordbook_entry(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wordbook_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(wordbook_id) REFERENCES wordbook(id) ON DELETE CASCADE
);
CREATE INDEX idx_wordbook_entry_word ON wordbook_entry(word);
CREATE UNIQUE INDEX idx_wordbook_entry_unique ON wordbook_entry(wordbook_id, word);

INSERT INTO history(word, count, last_time)
VALUES ('right', 7, '2026-08-04 09:00:00');
INSERT INTO setting(name, value) VALUES ('legacy-source-uuid', '1');
INSERT INTO wordbook(id, name) VALUES (1, 'Fixture words');
INSERT INTO wordbook_entry(id, wordbook_id, word) VALUES (1, 1, 'right');
