from flask import Flask, render_template, request, jsonify
import requests
import sqlite3

app = Flask(__name__)
RAWG_KEY = "a99438f82df045e29ac53588ae56daf1"

def init_db():
    conn = sqlite3.connect("games.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        cover TEXT,
        rating INTEGER,
        status TEXT,
        genre TEXT,
        year TEXT
    )''')
    # Migrate: add new columns if they don't exist yet
    for col, coltype in [("description", "TEXT"), ("rawg_id", "TEXT"), ("platform", "TEXT")]:
        try:
            c.execute(f"ALTER TABLE games ADD COLUMN {col} {coltype}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()
    conn.close()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search")
def search():
    query = request.args.get("q", "")
    response = requests.get(
        "https://api.rawg.io/api/games",
        params={"key": RAWG_KEY, "search": query, "page_size": 6}
    )
    data = response.json()
    results = []
    for game in data.get("results", []):
        results.append({
            "rawg_id": str(game.get("id", "")),
            "name": game.get("name"),
            "cover": game.get("background_image"),
            "year": game.get("released", "")[:4] if game.get("released") else "Unknown",
            "genre": ", ".join([g["name"] for g in game.get("genres", [])])
        })
    return jsonify(results)

@app.route("/add", methods=["POST"])
def add():
    data = request.get_json()
    rawg_id = data.get("rawg_id", "")
    description = ""
    if rawg_id:
        try:
            detail_resp = requests.get(
                f"https://api.rawg.io/api/games/{rawg_id}",
                params={"key": RAWG_KEY},
                timeout=5
            )
            description = detail_resp.json().get("description_raw", "")
        except Exception:
            pass
    conn = sqlite3.connect("games.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO games (name, cover, rating, status, genre, year, description, rawg_id, platform) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data["name"], data["cover"], data["rating"], data["status"], data["genre"], data["year"], description, rawg_id, data.get("platform", ""))
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/library")
def library():
    conn = sqlite3.connect("games.db")
    c = conn.cursor()
    c.execute("SELECT id, name, cover, rating, status, genre, year, description, rawg_id, platform FROM games ORDER BY rating DESC")
    rows = c.fetchall()
    conn.close()
    games = [{
        "id": r[0], "name": r[1], "cover": r[2], "rating": r[3],
        "status": r[4], "genre": r[5], "year": r[6],
        "description": r[7] or "", "rawg_id": r[8] or "", "platform": r[9] or ""
    } for r in rows]
    return jsonify(games)

@app.route("/description/<int:game_id>")
def get_description(game_id):
    """Lazy-fetch a game's description from RAWG and cache it in the DB."""
    conn = sqlite3.connect("games.db")
    c = conn.cursor()
    c.execute("SELECT name, description, rawg_id FROM games WHERE id = ?", (game_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"description": ""})

    name, description, rawg_id = row

    if description:
        conn.close()
        return jsonify({"description": description})

    fetched_desc = ""
    fetched_rawg_id = rawg_id
    try:
        if not fetched_rawg_id:
            search_resp = requests.get(
                "https://api.rawg.io/api/games",
                params={"key": RAWG_KEY, "search": name, "page_size": 1},
                timeout=5
            )
            results = search_resp.json().get("results", [])
            if results:
                fetched_rawg_id = str(results[0]["id"])
        if fetched_rawg_id:
            detail_resp = requests.get(
                f"https://api.rawg.io/api/games/{fetched_rawg_id}",
                params={"key": RAWG_KEY},
                timeout=5
            )
            fetched_desc = detail_resp.json().get("description_raw", "")
    except Exception:
        pass

    if fetched_desc or fetched_rawg_id:
        c.execute(
            "UPDATE games SET description = ?, rawg_id = ? WHERE id = ?",
            (fetched_desc, fetched_rawg_id, game_id)
        )
        conn.commit()

    conn.close()
    return jsonify({"description": fetched_desc})

@app.route("/update/<int:game_id>", methods=["PUT"])
def update(game_id):
    data = request.get_json()
    conn = sqlite3.connect("games.db")
    c = conn.cursor()
    c.execute(
        "UPDATE games SET status = ?, rating = ?, platform = ? WHERE id = ?",
        (data["status"], int(data["rating"]), data.get("platform", ""), game_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/delete/<int:game_id>", methods=["DELETE"])
def delete(game_id):
    conn = sqlite3.connect("games.db")
    c = conn.cursor()
    c.execute("DELETE FROM games WHERE id = ?", (game_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
