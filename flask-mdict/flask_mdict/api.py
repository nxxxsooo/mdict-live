"""JSON API blueprint for the React SPA frontend."""

import re
import io
import os.path
import datetime
import sqlite3

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    make_response,
    request,
    send_file,
    url_for,
)

from legacy_rendering import render_legacy_records, resolve_legacy_links
from . import get_mdict, get_db, get_cache, Config
from . import helper


api = Blueprint("api", __name__)

regex_word_link = re.compile(r"^(@@@LINK=)(.+)$")
regex_src_schema = re.compile(r'([ "]src=["\'])(/|file:///)?(?!data:)(.+?["\'])')
regex_href_end_slash = re.compile(r'([ "]href=["\'].+?)(/)(["\'])')
regex_href_schema_sound = re.compile(r'([ "]href=["\'])(sound://)([^#].+?["\'])')
regex_href_schema_entry = re.compile(r'([ "]href=["\'])(entry://)([^#].+?["\'])')
regex_href_no_schema = re.compile(
    r'([ "]href=["\'])(?!http://|https://|sound://|entry://)([^#].+?["\'])'
)
regex_css = re.compile(r'(<link.*? )(href)(=".+?>)')
regex_js = re.compile(r'(<script.*? )(src)(=".+?>)')


def _v2_dependencies():
    return current_app.extensions.get("mdict_v2_dependencies")


def _shared_source(uuid):
    dependencies = _v2_dependencies()
    if dependencies is None:
        return None, None
    source_id = dependencies.legacy_source_ids.get(uuid)
    if source_id is None:
        return dependencies, None
    return dependencies, dependencies.catalog.adapter(source_id)


def _lookup_records(uuid, item, word):
    _dependencies, adapter = _shared_source(uuid)
    if adapter is not None:
        return [record.html for record in adapter.lookup(word)], lambda target: [
            record.html for record in adapter.lookup(target)
        ]
    query = item["query"]
    if item["type"] == "app":
        return list(query(word, item)), lambda target: list(query(target, item))

    def lookup(target):
        return list(query.mdx_lookup(get_db(uuid), target, ignorecase=True))

    return lookup(word), lookup


def _legacy_html(records, link_lookup, uuid):
    resolved = resolve_legacy_links(records, link_lookup)
    prefix_resource = url_for("mdict.query_resource", uuid=uuid, resource="")
    reset_css_url = url_for(
        "mdict.query_resource", uuid=uuid, resource="css/reset.css"
    )
    return render_legacy_records(
        resolved,
        prefix_resource=prefix_resource,
        reset_css_url=reset_css_url,
        fix_html=helper.fix_html,
    )


def _shared_source_record(uuid):
    dependencies = _v2_dependencies()
    if dependencies is None:
        return None
    source_id = dependencies.legacy_source_ids.get(uuid)
    return next(
        (
            source
            for source in dependencies.catalog.list_sources()
            if source.source_id == source_id
        ),
        None,
    )


@api.after_request
def add_cors_headers(response):
    """Add CORS headers for development (Vite dev server on different port)."""
    origin = request.headers.get("Origin", "")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@api.route("/dicts")
def list_dicts():
    """List all loaded dictionaries with metadata."""
    dicts = []
    for uuid, item in get_mdict().items():
        shared_source = _shared_source_record(uuid)
        dicts.append(
            {
                "uuid": uuid,
                "title": item["title"],
                "logo": url_for(
                    "mdict.query_resource", uuid=uuid, resource=item["logo"]
                ),
                "type": item["type"],
                "enabled": (
                    shared_source.enabled if shared_source is not None else item["enable"]
                ),
            }
        )
    return jsonify(dicts)


@api.route("/dicts/<uuid>/lookup/<word>")
def lookup_word(uuid, word):
    """Lookup a word in a specific dictionary. Returns raw HTML content."""
    word = word.strip()
    item = get_mdict().get(uuid)
    if not item:
        abort(404)

    # Cache check: per-dict lookup
    cache = get_cache()
    cache_key = "l:%s:%s" % (uuid[:8], word.lower())
    if cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)

    records, link_lookup = _lookup_records(uuid, item, word)

    if not records:
        result = {"word": word, "uuid": uuid, "found": False, "html": ""}
        return jsonify(result)

    html_content = _legacy_html(records, link_lookup, uuid)

    result = {
        "word": word,
        "uuid": uuid,
        "title": item["title"],
        "found": True,
        "html": html_content,
    }

    if cache:
        cache.set(cache_key, result)

    return jsonify(result)


@api.route("/lookup/<word>")
def lookup_all(word):
    """Lookup a word across all enabled dictionaries."""
    word = word.strip()

    # Cache check: aggregated lookup across all enabled dicts
    cache = get_cache()
    cache_key = "la:%s" % word.lower()
    if cache:
        cached = cache.get(cache_key)
        if cached is not None:
            # Still record history on cache hit
            helper.add_history(word)
            return jsonify(cached)

    results = []

    for uuid, item in get_mdict().items():
        if not item["enable"]:
            continue

        records, link_lookup = _lookup_records(uuid, item, word)

        if not records:
            continue

        html_content = _legacy_html(records, link_lookup, uuid)

        results.append(
            {
                "uuid": uuid,
                "title": item["title"],
                "logo": url_for(
                    "mdict.query_resource", uuid=uuid, resource=item["logo"]
                ),
                "found": True,
                "html": html_content,
            }
        )

    # Record history
    if results:
        helper.add_history(word)

    response_data = {
        "word": word,
        "results": results,
        "total": len(results),
    }

    # Cache the response (only if there were results)
    if cache and results:
        cache.set(cache_key, response_data)

    return jsonify(response_data)


@api.route("/suggest/<query>")
def suggest(query):
    """Autocomplete suggestions across all enabled dictionaries."""
    limit = request.args.get("limit", 20, type=int)

    # Cache check: suggestions by prefix
    cache = get_cache()
    cache_key = "s:%s:%d" % (query.lower(), limit)
    if cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)

    dependencies = _v2_dependencies()
    if dependencies is not None and dependencies.legacy_source_ids:
        result = dependencies.suggestion_service.suggest(query, limit=limit)
        suggestions = [suggestion.headword for suggestion in result.suggestions]
    else:
        contents = set()
        for uuid, item in get_mdict().items():
            if item["type"] == "app":
                continue
            if item["enable"]:
                content = item["query"].get_mdx_keys(get_db(uuid), query)
                contents |= set(content)
                if len(contents) >= limit * 3:
                    break
        suggestions = sorted(contents)[:limit]

    if cache:
        cache.set(cache_key, suggestions, ttl=3600)

    return jsonify(suggestions)


@api.route("/history")
def get_history():
    """Get search history."""
    limit = request.args.get("limit", 100, type=int)
    history = helper.get_history(max_num=limit)
    if not history:
        return jsonify([])
    items = []
    for row in history:
        items.append(
            {
                "word": row["word"],
                "count": row["count"],
                "last_time": row["last_time"],
            }
        )
    return jsonify(items)


@api.route("/history/clear", methods=["POST"])
def clear_history():
    """Clear search history."""
    helper.clear_history()
    return jsonify({"ok": True})


@api.route("/meta/<word>")
def word_meta(word):
    """Get word metadata (frequency, tags, etc.) as structured data."""
    # Cache check: word frequency metadata (static data)
    cache = get_cache()
    cache_key = "m:%s" % word.lower()
    if cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)

    dependencies = _v2_dependencies()
    if dependencies is not None:
        metadata = dependencies.metadata_service.lookup(word)
        if not metadata.available:
            return jsonify({"error": "Word Frequency Database not found"})
        if not metadata.records:
            result = {"word": word, "found": False}
            if cache:
                cache.set(cache_key, result)
            return jsonify(result)
        record = metadata.records[0]
        legacy_fields = dict(record.legacy_fields)
        result = {
            "word": word,
            "found": True,
            "phonetic": record.phonetic or "",
            "definition": record.definition or "",
            "translation": record.translation or "",
            "oxford": bool(legacy_fields.get("oxford")),
            "collins": int(legacy_fields.get("collins") or 0),
            "tags": list(record.tags),
            "bnc": legacy_fields.get("bnc"),
            "frq": legacy_fields.get("frq"),
            "exchanges": dict(record.inflections),
        }
        if cache:
            cache.set(cache_key, result)
        return jsonify(result)

    db = get_db("wfd_db")
    if not db:
        return jsonify({"error": "Word Frequency Database not found"})

    sql = "SELECT * FROM ecdict WHERE WORD = ?"
    cursor = db.execute(sql, (word.lower(),))
    row = next(cursor, None)
    if not row:
        result = {"word": word, "found": False}
        if cache:
            cache.set(cache_key, result)
        return jsonify(result)

    row = dict(row)
    EXCHANGE = {
        "p": "past_tense",
        "d": "past_participle",
        "i": "present_participle",
        "3": "third_person",
        "r": "comparative",
        "t": "superlative",
        "s": "plural",
        "0": "root",
        "1": "root_variant",
    }
    exchanges = {}
    if row.get("exchange"):
        for e in row["exchange"].split("/"):
            if e:
                t, w = e.split(":")
                exchanges[EXCHANGE.get(t, t)] = w

    tags = row.get("tag", "").split() if row.get("tag") else []

    result = {
        "word": word,
        "found": True,
        "phonetic": row.get("phonetic", ""),
        "definition": row.get("definition", ""),
        "translation": row.get("translation", ""),
        "oxford": bool(row.get("oxford")),
        "collins": int(row["collins"]) if row.get("collins") else 0,
        "tags": tags,
        "bnc": row.get("bnc"),
        "frq": row.get("frq"),
        "exchanges": exchanges,
    }

    if cache:
        cache.set(cache_key, result)

    return jsonify(result)


@api.route("/dicts/<uuid>/toggle", methods=["POST"])
def toggle_dict(uuid):
    """Toggle a dictionary on/off."""
    item = get_mdict().get(uuid)
    if not item:
        abort(404)
    item["enable"] = not item["enable"]
    dependencies = _v2_dependencies()
    if dependencies is not None:
        source_id = dependencies.legacy_source_ids.get(uuid)
        if source_id is not None and dependencies.source_updater is not None:
            dependencies.source_updater(source_id, item["enable"], None)
    helper.mdict_enable(uuid, item["enable"])

    # Invalidate lookup_all cache (depends on which dicts are enabled)
    cache = get_cache()
    if cache:
        cache.delete_prefix("la:")

    return jsonify({"uuid": uuid, "enabled": item["enable"]})


@api.route("/wordbooks", methods=["GET"])
def list_wordbooks():
    """List all wordbooks."""
    db = get_db("app_db")
    rows = db.execute("SELECT * FROM wordbook ORDER BY created_at DESC").fetchall()
    return jsonify([dict(row) for row in rows])


@api.route("/wordbooks", methods=["POST"])
def create_wordbook():
    """Create a new wordbook."""
    name = request.json.get("name")
    if not name:
        return jsonify({"error": "Name is required"}), 400
    db = get_db("app_db")
    cursor = db.execute("INSERT INTO wordbook (name) VALUES (?)", (name,))
    db.commit()
    return jsonify({"id": cursor.lastrowid, "name": name})


@api.route("/wordbooks/<int:wb_id>", methods=["DELETE"])
def delete_wordbook(wb_id):
    """Delete a wordbook."""
    db = get_db("app_db")
    db.execute("DELETE FROM wordbook WHERE id = ?", (wb_id,))
    db.commit()
    return jsonify({"ok": True})


@api.route("/wordbooks/<int:wb_id>", methods=["PUT"])
def update_wordbook(wb_id):
    """Rename a wordbook."""
    name = request.json.get("name")
    if not name:
        return jsonify({"error": "Name is required"}), 400
    db = get_db("app_db")
    db.execute("UPDATE wordbook SET name = ? WHERE id = ?", (name, wb_id))
    db.commit()
    return jsonify({"ok": True})


@api.route("/wordbooks/<int:wb_id>/entries", methods=["GET"])
def list_wordbook_entries(wb_id):
    """List entries in a wordbook."""
    db = get_db("app_db")
    rows = db.execute(
        "SELECT * FROM wordbook_entry WHERE wordbook_id = ? ORDER BY created_at DESC",
        (wb_id,),
    ).fetchall()
    return jsonify([dict(row) for row in rows])


@api.route("/wordbooks/<int:wb_id>/entries", methods=["POST"])
def add_wordbook_entry(wb_id):
    """Add a word to a wordbook."""
    word = request.json.get("word")
    if not word:
        return jsonify({"error": "Word is required"}), 400
    db = get_db("app_db")
    try:
        cursor = db.execute(
            "INSERT INTO wordbook_entry (wordbook_id, word) VALUES (?, ?)",
            (wb_id, word),
        )
        db.commit()
        return jsonify({"id": cursor.lastrowid, "word": word})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Word already exists in this wordbook"}), 409


@api.route("/wordbooks/<int:wb_id>/entries/<int:entry_id>", methods=["DELETE"])
def delete_wordbook_entry(wb_id, entry_id):
    """Remove a word from a wordbook."""
    db = get_db("app_db")
    db.execute(
        "DELETE FROM wordbook_entry WHERE id = ? AND wordbook_id = ?", (entry_id, wb_id)
    )
    db.commit()
    return jsonify({"ok": True})


@api.route("/wordbooks/entries", methods=["GET"])
def check_word_in_wordbooks():
    """Check which wordbooks contain a specific word."""
    word = request.args.get("word")
    if not word:
        return jsonify([])
    db = get_db("app_db")
    rows = db.execute(
        "SELECT wordbook_id, id FROM wordbook_entry WHERE word = ?", (word,)
    ).fetchall()
    return jsonify([dict(row) for row in rows])


@api.route("/cache/info")
def cache_info():
    """Get cache backend info and stats."""
    cache = get_cache()
    if not cache:
        return jsonify({"backend": "none"})
    return jsonify(cache.info())


@api.route("/cache/clear", methods=["POST"])
def cache_clear():
    """Clear all cached data."""
    cache = get_cache()
    if cache:
        cache.clear()
    return jsonify({"ok": True})
