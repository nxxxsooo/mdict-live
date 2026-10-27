CREATE TABLE MDX_INDEX(
    key_text TEXT NOT NULL UNIQUE,
    file_pos INTEGER,
    compressed_size INTEGER,
    decompressed_size INTEGER,
    record_block_type INTEGER,
    record_start INTEGER,
    record_end INTEGER,
    offset INTEGER
);
CREATE UNIQUE INDEX key_index ON MDX_INDEX(key_text);
CREATE TABLE META(key TEXT, value TEXT);

INSERT INTO MDX_INDEX VALUES ('images/fixture.png', 0, 32, 48, 2, 0, 16, 0);
INSERT INTO META VALUES ('m_time', '1722733200.0');
