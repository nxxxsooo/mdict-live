"""JSON API blueprint for the React SPA frontend."""

import re
import io
import os.path
import datetime
import sqlite3

from flask import Blueprint, jsonify, request, abort, make_response, send_file, url_for

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
        dicts.append(
            {
                "uuid": uuid,
                "title": item["title"],
                "logo": url_for(
                    "mdict.query_resource", uuid=uuid, resource=item["logo"]
                ),
                "type": item["type"],
                "enabled": item["enable"],
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

    q = item["query"]
    if item["type"] == "app":
        records = q(word, item)
    else:
        records = q.mdx_lookup(get_db(uuid), word, ignorecase=True)
        # resolve @@@LINK references
        for idx, record in enumerate(records):
            mo = regex_word_link.match(record)
            if mo:
                link = mo.group(2).strip()
                link_records = q.mdx_lookup(get_db(uuid), link, ignorecase=True)
                records[idx] = "\n\n".join(link_records)

    if not records:
        result = {"word": word, "uuid": uuid, "found": False, "html": ""}
        return jsonify(result)

    # Build resource URL prefix for this dict
    prefix_resource = url_for("mdict.query_resource", uuid=uuid, resource="")

    html_parts = []
    count = 1
    record_num = len(records)
    for record in records:
        if record.startswith("@@@LINK="):
            record_num -= 1

    for record in records:
        record = helper.fix_html(record)
        mo = regex_word_link.match(record)
        if mo:
            link = mo.group(2).strip()
            html_parts.append(
                f'<p>See also: <a href="entry://{link}" '
                f'data-entry-word="{link}">{link}</a></p>'
            )
        else:
            # Rewrite resource URLs to point to Flask backend
            record = regex_src_schema.sub(r"\g<1>%s/\3" % prefix_resource, record)
            record = regex_href_no_schema.sub(r"\g<1>%s/\2" % prefix_resource, record)
            record = regex_href_end_slash.sub(r"\1\3", record)
            # Mark sound/entry links with data attributes for JS handling
            record = regex_href_schema_sound.sub(
                r' data-sound-url="%s/\3" \1\2\3' % prefix_resource, record
            )
            record = regex_href_schema_entry.sub(
                r' data-entry-word="\3" \1\2\3', record
            )

            # Keep first CSS, keep last JS
            if count > 1:
                record = regex_css.sub(r"\1data-\2\3", record)
            if count < record_num:
                record = regex_js.sub(r"\1data-\2\3", record)
            count += 1

        html_parts.append(record)

    # Prepend reset CSS
    reset_css_url = url_for("mdict.query_resource", uuid=uuid, resource="css/reset.css")
    html_content = f'<link rel="stylesheet" href="{reset_css_url}">' + "<hr />".join(
        html_parts
    )

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

        q = item["query"]
        if item["type"] == "app":
            records = q(word, item)
        else:
            records = q.mdx_lookup(get_db(uuid), word, ignorecase=True)
            for idx, record in enumerate(records):
                mo = regex_word_link.match(record)
                if mo:
                    link = mo.group(2).strip()
                    link_records = q.mdx_lookup(get_db(uuid), link, ignorecase=True)
                    records[idx] = "\n\n".join(link_records)

        if not records:
            continue

        prefix_resource = url_for("mdict.query_resource", uuid=uuid, resource="")

        html_parts = []
        count = 1
        record_num = len(records)
        for record in records:
            if record.startswith("@@@LINK="):
                record_num -= 1

        for record in records:
            record = helper.fix_html(record)
            mo = regex_word_link.match(record)
            if mo:
                link = mo.group(2).strip()
                html_parts.append(
                    f'<p>See also: <a href="entry://{link}" '
                    f'data-entry-word="{link}">{link}</a></p>'
                )
            else:
                record = regex_src_schema.sub(r"\g<1>%s/\3" % prefix_resource, record)
                record = regex_href_no_schema.sub(
                    r"\g<1>%s/\2" % prefix_resource, record
                )
                record = regex_href_end_slash.sub(r"\1\3", record)
                record = regex_href_schema_sound.sub(
                    r' data-sound-url="%s/\3" \1\2\3' % prefix_resource, record
                )
                record = regex_href_schema_entry.sub(
                    r' data-entry-word="\3" \1\2\3', record
                )
                if count > 1:
                    record = regex_css.sub(r"\1data-\2\3", record)
                if count < record_num:
                    record = regex_js.sub(r"\1data-\2\3", record)
                count += 1

            html_parts.append(record)

        reset_css_url = url_for(
            "mdict.query_resource", uuid=uuid, resource="css/reset.css"
        )
        html_content = (
            f'<link rel="stylesheet" href="{reset_css_url}">'
            + "<hr />".join(html_parts)
        )

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
