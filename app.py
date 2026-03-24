from flask import Flask, jsonify, render_template, session, request, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import random
from datetime import datetime
import uuid
import threading
import time
import json
import urllib.request
import os
import sqlite3
from html.parser import HTMLParser

app = Flask(__name__, instance_relative_config=True)
app.secret_key = os.environ.get('SECRET_KEY', 'yin_tradesim_secret_2025_change_me')

# ─────────────────────────────────────────────
# Persistent user storage (SQLite Database)
# ─────────────────────────────────────────────
def get_db_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "trading_platform.db")

DB_FILE = get_db_path()

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                data TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

def get_setting(key, default=None):
    with sqlite3.connect(DB_FILE) as conn:
        res = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if res:
            return res[0]
    return default

def set_setting(key, value):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))

def sync_market_open():
    global market_open
    val = get_setting('market_open')
    if val is not None:
        market_open = (val == 'true')
    return market_open



def load_users():
    loaded_users = {}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute("SELECT username, data FROM users")
            for row in cursor:
                loaded_users[row[0]] = json.loads(row[1])
        print(f"[INFO] Loaded {len(loaded_users)} users from SQLite DB {DB_FILE}")
        return loaded_users
    except Exception as e:
        print(f"[WARN] Could not load users from database: {e}")
    return {}

def save_users():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM users")
            for username, data_dict in users.items():
                conn.execute("INSERT INTO users (username, data) VALUES (?, ?)", 
                             (username, json.dumps(data_dict)))
        return True
    except Exception as e:
        print(f"[ERROR] Could not save users to database: {e}")
        return False

init_db()
users = load_users()
admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')

# ─────────────────────────────────────────────
# GSE stock universe (updated prices March 2026)
# ─────────────────────────────────────────────
stocks = [
    {"symbol": "ACCESS", "name": "Access Bank Ghana PLC",           "price": 17.80, "sector": "Financial Services", "history": []},
    {"symbol": "ADB",    "name": "Agricultural Development Bank PLC","price": 5.06,  "sector": "Financial Services", "history": []},
    {"symbol": "ASG",    "name": "Asante Gold Corporation",          "price": 8.89,  "sector": "Mining",            "history": []},
    {"symbol": "ALLGH",  "name": "Atlantic Lithium Ltd",             "price": 6.12,  "sector": "Mining",            "history": []},
    {"symbol": "BOPP",   "name": "Benso Palm Plantation PLC",        "price": 26.31, "sector": "Agriculture",       "history": []},
    {"symbol": "CAL",    "name": "Cal Bank PLC",                     "price": 0.64,  "sector": "Financial Services", "history": []},
    {"symbol": "EGH",    "name": "Ecobank Ghana PLC",                "price": 6.30,  "sector": "Financial Services", "history": []},
    {"symbol": "EGL",    "name": "Enterprise Group PLC",             "price": 2.05,  "sector": "Insurance",         "history": []},
    {"symbol": "ETI",    "name": "Ecobank Transnational Inc.",        "price": 2.45,  "sector": "Financial Services", "history": []},
    {"symbol": "FML",    "name": "Fan Milk PLC",                     "price": 3.70,  "sector": "Consumer Goods",    "history": []},
    {"symbol": "GCB",    "name": "GCB Bank PLC",                     "price": 6.51,  "sector": "Financial Services", "history": []},
    {"symbol": "GGBL",   "name": "Guinness Ghana Breweries PLC",     "price": 8.45,  "sector": "Consumer Goods",    "history": []},
    {"symbol": "GOIL",   "name": "Ghana Oil Company PLC",            "price": 1.60,  "sector": "Energy",            "history": []},
    {"symbol": "MAC",    "name": "Mega African Capital PLC",         "price": 5.20,  "sector": "Financial Services", "history": []},
    {"symbol": "MTNGH",  "name": "Scancom PLC (MTN Ghana)",          "price": 3.10,  "sector": "Telecom",           "history": []},
    {"symbol": "RBGH",   "name": "Republic Bank (Ghana) PLC",        "price": 0.65,  "sector": "Financial Services", "history": []},
    {"symbol": "SCB",    "name": "Standard Chartered Bank Gh. PLC",  "price": 25.02, "sector": "Financial Services", "history": []},
    {"symbol": "SIC",    "name": "SIC Insurance Company PLC",        "price": 0.37,  "sector": "Insurance",         "history": []},
    {"symbol": "SOGEGH", "name": "Societe Generale Ghana PLC",       "price": 1.50,  "sector": "Financial Services", "history": []},
    {"symbol": "TOTAL",  "name": "TotalEnergies Marketing Ghana PLC","price": 16.47, "sector": "Energy",            "history": []},
    {"symbol": "TLW",    "name": "Tullow Oil PLC",                   "price": 11.92, "sector": "Energy",            "history": []},
    {"symbol": "UNIL",   "name": "Unilever Ghana PLC",               "price": 19.50, "sector": "Consumer Goods",    "history": []},
]

stock_lock  = threading.Lock()
user_lock   = threading.Lock()
market_open = False

app.recent_alerts = {'stop_loss': [], 'price_target': []}

# ─────────────────────────────────────────────
# HTML parser for AFX scraping
# ─────────────────────────────────────────────
class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_tbody = self.in_row = self.in_cell = False
        self.current_row = []
        self.current_cell = ""
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if   tag == 'tbody':                    self.in_tbody = True
        elif self.in_tbody and tag == 'tr':     self.in_row = True;  self.current_row = []
        elif self.in_row   and tag == 'td':     self.in_cell = True; self.current_cell = ""

    def handle_endtag(self, tag):
        if   tag == 'tbody':                    self.in_tbody = False
        elif self.in_row   and tag == 'tr':
            self.in_row = False
            if self.current_row: self.rows.append(self.current_row)
        elif self.in_cell  and tag == 'td':
            self.in_cell = False
            self.current_row.append(self.current_cell.strip())

    def handle_data(self, data):
        if self.in_cell: self.current_cell += data

# ─────────────────────────────────────────────
# Portfolio helpers
# ─────────────────────────────────────────────
def init_portfolio():
    return {
        "cash": 1000000.00,
        "holdings": {},
        "total_value": 1000000.00,
        "transactions": []
    }


def calculate_portfolio_value(portfolio):
    total = portfolio["cash"]
    for symbol, holding in portfolio["holdings"].items():
        stock = next((s for s in stocks if s["symbol"] == symbol), None)
        if stock:
            total += holding["shares"] * stock["price"]
    return round(total, 2)


def check_price_targets():
    alerts = []
    with user_lock:
        for username, user in users.items():
            for symbol, holding in user["portfolio"]["holdings"].items():
                pt = holding.get("price_target")
                if pt is None or holding["shares"] <= 0:
                    continue
                stock = next((s for s in stocks if s["symbol"] == symbol), None)
                if stock and stock["price"] >= pt:
                    alerts.append({
                        "username": username, "symbol": symbol,
                        "current_price": stock["price"], "price_target": pt,
                        "shares": holding["shares"]
                    })
    return alerts


def apply_stop_losses():
    now   = datetime.now().isoformat()
    execs = []
    changed = False
    with user_lock:
        for username, user in users.items():
            portfolio = user["portfolio"]
            to_close  = []
            for symbol, holding in list(portfolio["holdings"].items()):
                sl = holding.get("stop_loss")
                if sl is None or holding["shares"] <= 0:
                    continue
                stock = next((s for s in stocks if s["symbol"] == symbol), None)
                if not stock:
                    continue
                if stock["price"] <= sl:
                    qty   = holding["shares"]
                    total = round(qty * stock["price"], 2)
                    portfolio["cash"] = round(portfolio["cash"] + total, 2)
                    portfolio["transactions"].append({
                        "type": "stop_loss_sell", "symbol": symbol,
                        "shares": qty, "price": stock["price"],
                        "total": total, "timestamp": now, "username": username,
                    })
                    to_close.append(symbol)
                    execs.append({
                        "username": username, "symbol": symbol,
                        "shares": qty, "price": stock["price"], "total": total
                    })
                    changed = True
            for sym in to_close:
                portfolio["holdings"].pop(sym, None)
            portfolio["total_value"] = calculate_portfolio_value(portfolio)
    if changed:
        save_users()
    return execs

# ─────────────────────────────────────────────
# GSE real data fetching
# ─────────────────────────────────────────────
def fetch_gse_afx():
    try:
        req = urllib.request.Request(
            'https://afx.kwayisi.org/gse/',
            headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8')
        parser = TableParser()
        parser.feed(html)
        data = []
        for row in parser.rows:
            if len(row) >= 4:
                sym  = row[1] if len(row) > 1 else ""
                pstr = row[3].replace('?', '').replace(',', '').strip()
                if sym and pstr:
                    try:
                        data.append({'symbol': sym, 'price': float(pstr)})
                    except ValueError:
                        pass
        return data or None
    except Exception as e:
        print(f"[AFX] {e}")
        return None


def fetch_gse_api():
    try:
        req = urllib.request.Request(
            'https://dev.kwayisi.org/apis/gse/live',
            headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode('utf-8'))
        result = []
        if isinstance(data, list):
            for item in data:
                if 'name' in item and 'price' in item:
                    try:
                        result.append({'symbol': item['name'], 'price': float(item['price'])})
                    except (ValueError, TypeError):
                        pass
        return result or None
    except Exception as e:
        print(f"[GSE API] {e}")
        return None


def update_prices_with_real_data():
    real = fetch_gse_afx() or fetch_gse_api()
    if not real:
        return False
    with stock_lock:
        updated = 0
        for stock in stocks:
            match = next((r for r in real if r['symbol'] == stock['symbol']), None)
            if match:
                stock['price'] = match['price']
                stock['history'].append({"time": datetime.now().isoformat(), "price": stock['price']})
                if len(stock['history']) > 100:
                    stock['history'].pop(0)
                updated += 1
    print(f"[INFO] Updated {updated} stocks from real GSE data")
    return True


def update_prices():
    last_real = 0
    real_interval = 30
    while True:
        time.sleep(10)
        if sync_market_open():
            now = time.time()
            if now - last_real >= real_interval:
                if update_prices_with_real_data():
                    last_real = now
                    sl = apply_stop_losses()
                    pt = check_price_targets()
                    app.recent_alerts['stop_loss'].extend(sl)
                    app.recent_alerts['price_target'].extend(pt)
                    app.recent_alerts['stop_loss']    = app.recent_alerts['stop_loss'][-50:]
                    app.recent_alerts['price_target'] = app.recent_alerts['price_target'][-50:]
                    continue

            # Simulated ±2% tick
            with stock_lock:
                ts = datetime.now().isoformat()
                for stock in stocks:
                    if stock["price"] > 0:
                        stock["price"] = max(0.01, round(
                            stock["price"] * (1 + random.uniform(-0.02, 0.02)), 2))
                        stock["history"].append({"time": ts, "price": stock["price"]})
                        if len(stock["history"]) > 100:
                            stock["history"].pop(0)

            sl = apply_stop_losses()
            pt = check_price_targets()
            app.recent_alerts['stop_loss'].extend(sl)
            app.recent_alerts['price_target'].extend(pt)
            app.recent_alerts['stop_loss']    = app.recent_alerts['stop_loss'][-50:]
            app.recent_alerts['price_target'] = app.recent_alerts['price_target'][-50:]

# ─────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────
def get_current_user():
    if "user_id" not in session:
        return None
    username = session.get("username")
    if username and username in users:
        return users[username]
    return None


def is_admin():
    return session.get("is_admin", False)

# ─────────────────────────────────────────────
# Page routes
# ─────────────────────────────────────────────
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", username=session.get("username"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Check admin login
        if username == "admin" and password == admin_password:
            session["user_id"]  = "admin"
            session["username"] = "admin"
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))

        if not username or not password:
            return render_template("login.html", error="Please enter both username and password")

        # Sync users for multi-worker deployments
        global users
        users = load_users()

        user = users.get(username)
        if not user:
            return render_template("login.html", error="Invalid username or password")

        # Get the stored password
        stored_pw = user["password"]
        
        # Check if it's a hashed password or plain text
        valid = False
        try:
            # Try to verify as hash
            valid = check_password_hash(stored_pw, password)
        except ValueError:
            # If it fails, treat as plain text
            valid = (stored_pw == password)
        
        if not valid:
            return render_template("login.html", error="Invalid username or password")

        # If login successful with plain text, upgrade to hash
        if not stored_pw.startswith("pbkdf2:") and not stored_pw.startswith("scrypt:"):
            with user_lock:
                user["password"] = generate_password_hash(password)
                save_users()

        session["user_id"]  = user["id"]
        session["username"] = username
        session["is_admin"] = False
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        try:
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirm  = request.form.get("confirm_password", "")

            # ── Validation ──────────────────────────────────────
            if not username:
                return render_template("signup.html", error="Username is required")

            if not password:
                return render_template("signup.html", error="Password is required")

            if len(username) < 3:
                return render_template("signup.html", error="Username must be at least 3 characters")

            if len(username) > 20:
                return render_template("signup.html", error="Username must be 20 characters or fewer")

            # Only allow letters, numbers, underscores, hyphens
            allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')
            if not all(c in allowed for c in username):
                return render_template("signup.html",
                    error="Username can only contain letters, numbers, underscores (_) and hyphens (-)")

            if len(password) < 6:
                return render_template("signup.html", error="Password must be at least 6 characters")

            if password != confirm:
                return render_template("signup.html", error="Passwords do not match")

            if username.lower() == "admin":
                return render_template("signup.html", error="That username is reserved")

            if username in users:
                return render_template("signup.html",
                    error=f"Username '{username}' is already taken — please choose another")

            # ── Create account ───────────────────────────────────
            user_id = str(uuid.uuid4())
            new_user = {
                "id": user_id,
                "username": username,
                "password": generate_password_hash(password),
                "registered_at": datetime.now().isoformat(),
                "portfolio": init_portfolio(),
            }

            with user_lock:
                users[username] = new_user
                saved = save_users()

            if not saved:
                print(f"[WARN] Could not persist user {username} to disk")

            session["user_id"]  = user_id
            session["username"] = username
            session["is_admin"] = False
            return redirect(url_for("index"))

        except Exception as e:
            print(f"[ERROR] Signup error: {e}")
            return render_template("signup.html",
                error="An unexpected error occurred. Please try again.")

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin")
def admin_dashboard():
    if not is_admin():
        return redirect(url_for("login"))
    return render_template("admin.html")


@app.route("/manual")
def manual():
    return render_template("manual.html")

# ─────────────────────────────────────────────
# API — stocks & portfolio
# ─────────────────────────────────────────────
@app.route("/api/stocks")
def get_stocks():
    with stock_lock:
        data = [s.copy() for s in stocks]
    for s in data:
        s['market_open'] = sync_market_open()
    return jsonify(data)


@app.route("/api/portfolio")
def get_portfolio():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    portfolio = user["portfolio"]
    portfolio["total_value"] = calculate_portfolio_value(portfolio)
    portfolio["market_open"] = sync_market_open()
    return jsonify(portfolio)


@app.route("/api/history/<symbol>")
def get_stock_history(symbol):
    with stock_lock:
        stock = next((s for s in stocks if s["symbol"] == symbol), None)
    if not stock:
        return jsonify({"error": "Stock not found"}), 404
    return jsonify(stock["history"])


@app.route("/api/alerts")
def get_recent_alerts():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    uname = user["username"]
    return jsonify({
        'stop_loss':    [a for a in app.recent_alerts['stop_loss']    if a['username'] == uname],
        'price_target': [a for a in app.recent_alerts['price_target'] if a['username'] == uname],
    })


@app.route("/api/reset", methods=["POST"])
def reset_portfolio():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    with user_lock:
        user["portfolio"] = init_portfolio()
        save_users()
    return jsonify({"success": True, "portfolio": user["portfolio"]})

# ─────────────────────────────────────────────
# API — trading
# ─────────────────────────────────────────────
@app.route("/api/buy", methods=["POST"])
def buy_stock():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    if not sync_market_open():
        return jsonify({"error": "Market is currently closed. Trading is not allowed."}), 400

    data   = request.json or {}
    symbol = data.get("symbol", "").strip().upper()

    try:
        shares = int(data.get("shares", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Shares must be a whole number"}), 400

    if not symbol or shares <= 0:
        return jsonify({"error": "Invalid symbol or number of shares"}), 400

    with stock_lock:
        stock = next((s for s in stocks if s["symbol"] == symbol), None)
    if not stock:
        return jsonify({"error": f"Stock '{symbol}' not found"}), 404

    order_type   = (data.get("order_type") or "market").lower()
    limit_price  = data.get("limit_price")
    stop_loss    = data.get("stop_loss")
    price_target = data.get("price_target")

    def to_float(val, name):
        if val is None or val == "":
            return None, None
        try:
            return float(val), None
        except (TypeError, ValueError):
            return None, f"Invalid {name}"

    limit_price,  err = to_float(limit_price,  "limit price")
    if err: return jsonify({"error": err}), 400
    stop_loss,    err = to_float(stop_loss,    "stop-loss price")
    if err: return jsonify({"error": err}), 400
    price_target, err = to_float(price_target, "price target")
    if err: return jsonify({"error": err}), 400

    current_price = stock["price"]

    if order_type == "limit":
        if limit_price is None:
            return jsonify({"error": "Limit price required for limit orders"}), 400
        if current_price > limit_price:
            return jsonify({
                "error": f"Limit not reached. Current GHS {current_price:.2f} is above your limit of GHS {limit_price:.2f}",
                "current_price": current_price,
                "limit_price": limit_price,
            }), 400

    total_cost = shares * current_price

    with user_lock:
        portfolio = user["portfolio"]
        if total_cost > portfolio["cash"]:
            return jsonify({
                "error": f"Insufficient funds. Need GHS {total_cost:,.2f} but you have GHS {portfolio['cash']:,.2f}"
            }), 400

        portfolio["cash"] = round(portfolio["cash"] - total_cost, 2)

        if symbol in portfolio["holdings"]:
            h          = portfolio["holdings"][symbol]
            new_shares = h["shares"] + shares
            h["avg_cost"] = round(
                ((h["avg_cost"] * h["shares"]) + (current_price * shares)) / new_shares, 2)
            h["shares"] = new_shares
            if stop_loss    is not None: h["stop_loss"]    = stop_loss
            if price_target is not None: h["price_target"] = price_target
        else:
            portfolio["holdings"][symbol] = {
                "shares": shares, "avg_cost": current_price,
                "stop_loss": stop_loss, "price_target": price_target,
            }

        portfolio["transactions"].append({
            "type":      "buy" if order_type == "market" else "buy_limit",
            "symbol":    symbol,
            "shares":    shares,
            "price":     current_price,
            "total":     round(total_cost, 2),
            "timestamp": datetime.now().isoformat(),
            "username":  user["username"],
            "stop_loss": stop_loss,
            "price_target": price_target,
        })
        portfolio["total_value"] = calculate_portfolio_value(portfolio)
        save_users()

    return jsonify({"success": True, "portfolio": portfolio, "order_value": round(total_cost, 2)})


@app.route("/api/sell", methods=["POST"])
def sell_stock():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    if not sync_market_open():
        return jsonify({"error": "Market is currently closed. Trading is not allowed."}), 400

    data   = request.json or {}
    symbol = data.get("symbol", "").strip().upper()

    try:
        shares = int(data.get("shares", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Shares must be a whole number"}), 400

    if not symbol or shares <= 0:
        return jsonify({"error": "Invalid symbol or number of shares"}), 400

    with stock_lock:
        stock = next((s for s in stocks if s["symbol"] == symbol), None)
    if not stock:
        return jsonify({"error": f"Stock '{symbol}' not found"}), 404

    with user_lock:
        portfolio = user["portfolio"]
        if symbol not in portfolio["holdings"]:
            return jsonify({"error": f"You don't own any shares of {symbol}"}), 400

        holding = portfolio["holdings"][symbol]
        if holding["shares"] < shares:
            return jsonify({
                "error": f"You only own {holding['shares']} shares of {symbol}, cannot sell {shares}"
            }), 400

        current_price = stock["price"]
        total_value   = round(shares * current_price, 2)

        portfolio["cash"] = round(portfolio["cash"] + total_value, 2)
        holding["shares"] -= shares
        if holding["shares"] == 0:
            portfolio["holdings"].pop(symbol, None)

        portfolio["transactions"].append({
            "type":      "sell",
            "symbol":    symbol,
            "shares":    shares,
            "price":     current_price,
            "total":     total_value,
            "timestamp": datetime.now().isoformat(),
            "username":  user["username"],
        })
        portfolio["total_value"] = calculate_portfolio_value(portfolio)
        save_users()

    return jsonify({"success": True, "portfolio": portfolio, "order_value": total_value})


@app.route("/api/update_order_settings", methods=["POST"])
def update_order_settings():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    data   = request.json or {}
    symbol = data.get("symbol", "").strip().upper()
    if not symbol:
        return jsonify({"error": "Symbol is required"}), 400

    with user_lock:
        portfolio = user["portfolio"]
        if symbol not in portfolio["holdings"]:
            return jsonify({"error": "Stock not in portfolio"}), 400

        holding = portfolio["holdings"][symbol]
        sl = data.get("stop_loss")
        pt = data.get("price_target")

        if sl is not None:
            try:    holding["stop_loss"]    = float(sl)
            except: return jsonify({"error": "Invalid stop-loss"}), 400
        if pt is not None:
            try:    holding["price_target"] = float(pt)
            except: return jsonify({"error": "Invalid price target"}), 400

        save_users()

    return jsonify({"success": True, "holding": holding})


@app.route("/api/calculate_order_value", methods=["POST"])
def calculate_order_value():
    data   = request.json or {}
    symbol = data.get("symbol", "").strip().upper()
    action = data.get("action", "buy")
    try:
        shares = int(data.get("shares", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Shares must be a whole number"}), 400

    if not symbol or shares <= 0:
        return jsonify({"error": "Invalid symbol or shares"}), 400

    with stock_lock:
        stock = next((s for s in stocks if s["symbol"] == symbol), None)
    if not stock:
        return jsonify({"error": "Stock not found"}), 404

    return jsonify({
        "symbol":      symbol,
        "shares":      shares,
        "price":       stock["price"],
        "total_value": round(shares * stock["price"], 2),
        "action":      action,
    })

# ─────────────────────────────────────────────
# API — public leaderboard
# ─────────────────────────────────────────────
@app.route("/api/leaderboard")
def get_public_leaderboard():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    board = []
    with user_lock:
        for uname, u in users.items():
            pf     = u["portfolio"]
            val    = calculate_portfolio_value(pf)
            growth = round(((val - 1000000) / 1000000) * 100, 2)
            board.append({
                "username":       uname,
                "portfolio_value":round(val, 2),
                "growth_percent": growth,
                "holdings_count": len(pf["holdings"]),
                "total_trades":   len(pf["transactions"]),
                "rank": 0,
            })

    board.sort(key=lambda x: x["portfolio_value"], reverse=True)
    for i, e in enumerate(board):
        e["rank"] = i + 1
    return jsonify(board)

# ─────────────────────────────────────────────
# API — admin
# ─────────────────────────────────────────────
@app.route("/api/admin/leaderboard")
def get_admin_leaderboard():
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403

    board = []
    with user_lock:
        for uname, u in users.items():
            pf     = u["portfolio"]
            val    = pf["total_value"]
            growth = round(((val - 1000000) / 1000000) * 100, 2)
            hv = {}
            for sym, h in pf["holdings"].items():
                s = next((x for x in stocks if x["symbol"] == sym), None)
                if s:
                    hv[sym] = {
                        "shares":        h["shares"],
                        "current_value": round(h["shares"] * s["price"], 2),
                        "avg_cost":      h["avg_cost"],
                    }
            board.append({
                "username":       uname,
                "portfolio_value":val,
                "growth_percent": growth,
                "cash":           pf["cash"],
                "holdings_count": len(pf["holdings"]),
                "holdings_value": hv,
                "total_trades":   len(pf["transactions"]),
                "rank": 0,
            })

    board.sort(key=lambda x: x["portfolio_value"], reverse=True)
    for i, e in enumerate(board):
        e["rank"] = i + 1
    return jsonify(board)


@app.route("/api/admin/users")
def get_admin_users():
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403

    result = []
    with user_lock:
        for uname, u in users.items():
            pf     = u["portfolio"]
            val    = pf["total_value"]
            growth = round(((val - 1000000) / 1000000) * 100, 2)
            result.append({
                "username":       uname,
                "portfolio_value":val,
                "growth_percent": growth,
                "cash":           pf["cash"],
                "holdings_count": len(pf["holdings"]),
                "total_trades":   len(pf["transactions"]),
                "registered_at":  u.get("registered_at", "—"),
            })
    return jsonify(result)


@app.route("/api/admin/stats")
def get_admin_stats():
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403

    with user_lock:
        total_users    = len(users)
        total_pv       = sum(u["portfolio"]["total_value"] for u in users.values())
        avg_pv         = total_pv / total_users if total_users else 0
        active_traders = sum(1 for u in users.values() if u["portfolio"]["holdings"])
        total_trades   = sum(len(u["portfolio"]["transactions"]) for u in users.values())

    with stock_lock:
        mcap   = sum(s["price"] * 1_000_000 for s in stocks)
        gainer = max(stocks, key=lambda x: x["price"])
        loser  = min(stocks, key=lambda x: x["price"])

    return jsonify({
        "total_users":             total_users,
        "total_portfolio_value":   round(total_pv, 2),
        "average_portfolio_value": round(avg_pv, 2),
        "active_traders":          active_traders,
        "total_trades":            total_trades,
        "market_open":             sync_market_open(),
        "market_stats": {
            "total_market_cap": round(mcap, 2),
            "biggest_gainer":   {"symbol": gainer["symbol"], "price": gainer["price"]},
            "biggest_loser":    {"symbol": loser["symbol"],  "price": loser["price"]},
        },
    })


@app.route("/api/admin/reset_competition", methods=["POST"])
def reset_competition():
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403
    with user_lock:
        users.clear()
        save_users()
    return jsonify({"success": True, "message": "Competition reset. All users cleared."})


@app.route("/api/admin/delete_user", methods=["POST"])
def delete_user():
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403
    username = (request.json or {}).get("username", "").strip()
    if not username:
        return jsonify({"error": "Username required"}), 400
    with user_lock:
        if username not in users:
            return jsonify({"error": f"User '{username}' not found"}), 404
        del users[username]
        save_users()
    return jsonify({"success": True, "message": f"User '{username}' deleted."})


@app.route("/api/admin/reset_user_portfolio", methods=["POST"])
def reset_user_portfolio():
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403
    username = (request.json or {}).get("username", "").strip()
    if not username:
        return jsonify({"error": "Username required"}), 400
    with user_lock:
        if username not in users:
            return jsonify({"error": f"User '{username}' not found"}), 404
        users[username]["portfolio"] = init_portfolio()
        save_users()
    return jsonify({"success": True, "message": f"Portfolio for '{username}' reset to GHS 1,000,000."})


@app.route("/api/admin/user_detail/<username>")
def get_user_detail(username):
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403
    with user_lock:
        if username not in users:
            return jsonify({"error": "User not found"}), 404
        u  = users[username]
        pf = u["portfolio"]
        tv = calculate_portfolio_value(pf)
        details = []
        for sym, h in pf["holdings"].items():
            s  = next((x for x in stocks if x["symbol"] == sym), None)
            cp = s["price"] if s else h["avg_cost"]
            cv = cp * h["shares"]
            pnl= (cp - h["avg_cost"]) * h["shares"]
            cost_basis = h["avg_cost"] * h["shares"]
            details.append({
                "symbol":        sym,
                "shares":        h["shares"],
                "avg_cost":      h["avg_cost"],
                "current_price": cp,
                "current_value": round(cv, 2),
                "pnl":           round(pnl, 2),
                "pnl_pct":       round((pnl / cost_basis) * 100, 2) if cost_basis > 0 else 0,
                "stop_loss":     h.get("stop_loss"),
                "price_target":  h.get("price_target"),
            })
        return jsonify({
            "username":    username,
            "cash":        pf["cash"],
            "total_value": tv,
            "holdings":    details,
            "transactions":pf["transactions"][-20:],
            "total_trades":len(pf["transactions"]),
            "growth_pct":  round(((tv - 1000000) / 1000000) * 100, 2),
        })


@app.route("/api/admin/adjust_stock_price", methods=["POST"])
def adjust_stock_price():
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403
    data   = request.json or {}
    symbol = data.get("symbol", "").strip().upper()
    try:
        new_price = float(data.get("price", 0))
        if new_price <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Price must be a positive number"}), 400

    with stock_lock:
        stock = next((s for s in stocks if s["symbol"] == symbol), None)
        if not stock:
            return jsonify({"error": "Stock not found"}), 404
        old_price      = stock["price"]
        stock["price"] = round(new_price, 2)
        stock["history"].append({"time": datetime.now().isoformat(), "price": stock["price"]})
        if len(stock["history"]) > 100:
            stock["history"].pop(0)

    return jsonify({
        "success":   True,
        "message":   f"{symbol} updated: GHS {old_price:.2f} → GHS {new_price:.2f}",
        "symbol":    symbol,
        "old_price": old_price,
        "new_price": round(new_price, 2),
    })


@app.route("/api/admin/market_control", methods=["POST"])
def market_control():
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403
    global market_open
    action = (request.json or {}).get("action", "")
    if action == "open":
        market_open = True
        set_setting('market_open', 'true')
        return jsonify({"success": True, "message": "Market opened", "market_open": True})
    elif action == "close":
        market_open = False
        set_setting('market_open', 'false')
        return jsonify({"success": True, "message": "Market closed", "market_open": False})
    return jsonify({"error": "Use 'open' or 'close'"}), 400

# ─────────────────────────────────────────────
# Start background thread + entry point
# ─────────────────────────────────────────────
price_thread = threading.Thread(target=update_prices, daemon=True)
price_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)