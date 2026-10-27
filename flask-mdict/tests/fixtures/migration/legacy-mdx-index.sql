CREATE TABLE MDX_INDEX(
    key_text TEXT NOT NULL,
    file_pos INTEGER,
    compressed_size INTEGER,
    decompressed_size INTEGER,
    record_block_type INTEGER,
    record_start INTEGER,
    record_end INTEGER,
    offset INTEGER
);
CREATE INDEX key_index ON MDX_INDEX(key_text);
CREATE TABLE META(key TEXT, value TEXT);

INSERT INTO MDX_INDEX VALUES ('right', 0, 64, 128, 2, 0, 32, 0);
INSERT INTO META VALUES ('encoding', 'UTF-8');
INSERT INTO META VALUES ('stylesheet', '{}');
INSERT INTO META VALUES ('title', 'Synthetic legacy index');
INSERT INTO META VALUES ('description', '<p>Synthetic</p>');
INSERT INTO META VALUES ('version', '1.2');
INSERT INTO META VALUES ('m_time', '1722733200.0');
