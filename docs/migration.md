# v1 to v2 storage migration

## Back up first

Before first v2 startup, stop the old container and back up:

- the legacy `flask_mdict.db` containing history, wordbooks, and settings;
- the old configuration directory;
- the token file location, without copying its value into notes or logs;
- any hand-maintained dictionary source files that are not backed up elsewhere.

Generated MDX/MDD indexes are disposable and do not need to be treated as the
system of record.

## First start

The old layout commonly mounted one host directory at `/app/content`, mixing
the dictionary corpus, `flask_mdict.db`, and generated indexes. For the first v2
start, mount that same host directory read-only at `/library` and mount a new
writable directory at `/data`:

```yaml
volumes:
  - /path/to/old-content:/library:ro
  - /path/to/new-appdata:/data
  - /path/to/new-index:/data/index
```

When `/data/mdict-live.db` does not exist and `/library/flask_mdict.db` does,
startup copies the legacy database to a temporary data-path file, checks SQLite
integrity, runs schema migrations, and atomically adopts it. The source database
is never modified or deleted. Once `/data/mdict-live.db` exists, it is
authoritative and subsequent starts do not merge the legacy database again.

For the current home Unraid corpus, use:

```text
/mnt/user/media/Dicts                  → /library (read-only)
/mnt/user/appdata/mdict-live/data     → /data
/mnt/user/appdata/mdict-live/index    → /data/index
/mnt/user/appdata/mdict-live/config   → /config
```

If the old database is not already beside `/mnt/user/media/Dicts`, copy a
verified backup into the corpus root for the one-time adoption or migrate it in
a temporary read-only library directory. Do not make the permanent corpus
writable merely to simplify migration.

## Source identity and citations

Each discovery cycle hashes complete MDX/MDD bytes. Moving unchanged files
retains source identity; replacing or changing bytes creates a new revision.
Duplicate copies remain distinct registered sources. Citations bind source ID,
revision, representation version, entry identity, and optional text block. A
correctly signed citation becomes unavailable when its source revision is no
longer present; the service returns `410 Gone` rather than silently resolving it
against different text.

## Rollback

The old image can be restarted with its original `/app/content` mapping because
v2 leaves the legacy corpus and database untouched. Changes made to history or
wordbooks after v2 adoption live only in `/data/mdict-live.db`; there is no
automatic reverse synchronization. Export or copy those changes deliberately
before a long-term rollback.

If first-start migration fails, preserve both the original database and the
failure logs, remove only the incomplete temporary destination identified by
the application, correct permissions or corruption, and retry. Never overwrite
the source database with a partially migrated file.

## Backup after cutover

Back up `/data/mdict-live.db` with SQLite's online backup mechanism or while the
container is stopped. Back up `/config` separately. `/data/index` can be
excluded and rebuilt from the read-only corpus. Test a restore into a separate
data directory before relying on it.
