from flask import Flask, jsonify, render_template, session, request, redirect, url_for
import random
from datetime import datetime, timedelta
import uuid
import threading
import time
import json
import urllib.request
import urllib.error
import os
from html.parser import HTMLParser

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here_change_in_production')

# -----------------------------
# In-memory user database
# -----------------------------
users = {}
admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')

# -----------------------------
# GSE stock universe with initial prices
# -----------------------------
stocks = [
    {"symbol": "ACCESS", "name": "Access Bank Ghana PLC", "price": 7.50, "sector": "Financial Services", "history": []},
    {"symbol": "ADB", "name": "Agricultural Development Bank PLC", "price": 5.06, "sector": "Financial Services", "history": []},
    {"symbol": "ASG", "name": "Asante Gold Corporation", "price": 8.89, "sector": "Mining", "history": []},
    {"symbol": "ALLGH", "name": "Atlantic Lithium Ltd", "price": 6.12, "sector": "Mining", "history": []},
    {"symbol": "BOPP", "name": "Benso Palm Plantation PLC", "price": 26.31, "sector": "Agriculture", "history": []},
    {"symbol": "CAL", "name": "Cal Bank PLC", "price": 0.64, "sector": "Financial Services", "history": []},
    {"symbol": "EGH", "name": "Ecobank Ghana PLC.", "price": 6.30, "sector": "Financial Services", "history": []},
    {"symbol": "EGL", "name": "Enterprise Group PLC", "price": 2.05, "sector": "Insurance", "history": []},
    {"symbol": "ETI", "name": "Ecobank Transnational Inc.", "price": 0.75, "sector": "Financial Services", "history": []},
    {"symbol": "FML", "name": "Fan Milk PLC.", "price": 3.70, "sector": "Consumer Goods", "history": []},
    {"symbol": "GCB", "name": "GCB Bank PLC", "price": 6.51, "sector": "Financial Services", "history": []},
    {"symbol": "GGBL", "name": "Guinness Ghana Breweries PLC", "price": 5.62, "sector": "Consumer Goods", "history": []},
    {"symbol": "GOIL", "name": "Ghana Oil Company PLC", "price": 1.60, "sector": "Energy", "history": []},
    {"symbol": "MAC", "name": "Mega African Capital PLC", "price": 5.38, "sector": "Financial Services", "history": []},
    {"symbol": "MTNGH", "name": "Scancom PLC", "price": 3.10, "sector": "Telecom", "history": []},
    {"symbol": "RBGH", "name": "Republic Bank (Ghana) PLC", "price": 0.60, "sector": "Financial Services", "history": []},
    {"symbol": "SCB", "name": "Standard Chartered Bank Gh. PLC", "price": 25.02, "sector": "Financial Services", "history": []},
    {"symbol": "SIC", "name": "SIC Insurance Company PLC", "price": 0.37, "sector": "Insurance", "history": []},
    {"symbol": "SOGEGH", "name": "Societe Generale Ghana PLC", "price": 1.50, "sector": "Financial Services", "history": []},
    {"symbol": "TOTAL", "name": "TotalEnergies Marketing Ghana PLC", "price": 16.47, "sector": "Energy", "history": []},
    {"symbol": "TLW", "name": "Tullow Oil PLC", "price": 11.92, "sector": "Energy", "history": []},
    {"symbol": "UNIL", "name": "Unilever Ghana PLC", "price": 19.50, "sector": "Consumer Goods", "history": []},
]

# Thread lock for thread-safe operations
stock_lock = threading.Lock()
user_lock = threading.Lock()

# Market status
market_open = False

# Recent alerts storage
app.recent_alerts = {'stop_loss': [], 'price_target': []}

# -----------------------------
# Simple HTML Parser for extracting table data
# -----------------------------
class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_tbody = False
        self.in_row = False
        self.in_cell = False
        self.current_row = []
        self.current_cell = ""
        self.rows = []
        self.cell_count = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'tbody':
            self.in_tbody = True
        elif self.in_tbody and tag == 'tr':
            self.in_row = True
            self.current_row = []
            self.cell_count = 0
        elif self.in_row and tag == 'td':
            self.in_cell = True
            self.current_cell = ""

    def handle_endtag(self, tag):
        if tag == 'tbody':
            self.in_tbody = False
        elif self.in_row and tag == 'tr':
            self.in_row = False
            if self.current_row:
                self.rows.append(self.current_row)
        elif self.in_cell and tag == 'td':
            self.in_cell = False
            self.current_row.append(self.current_cell.strip())
            self.cell_count += 1

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data


# -----------------------------
# Portfolio helpers
# -----------------------------
def init_portfolio():
    """Initialize user portfolio"""
    return {
        "cash": 100000.00,
        "holdings": {},
        "total_value": 100000.00,
        "transactions": []
    }


def calculate_portfolio_value(portfolio):
    """Calculate total portfolio value"""
    total = portfolio["cash"]
    for symbol, holding in portfolio["holdings"].items():
        stock = next((s for s in stocks if s["symbol"] == symbol), None)
        if stock:
            total += holding["shares"] * stock["price"]
    return round(total, 2)


def check_price_targets():
    """Check all users' holdings against their price targets."""
    price_target_alerts = []

    with user_lock:
        for username, user in users.items():
            portfolio = user["portfolio"]

            for symbol, holding in portfolio["holdings"].items():
                price_target = holding.get("price_target")
                if price_target is None or holding["shares"] <= 0:
                    continue

                stock = next((s for s in stocks if s["symbol"] == symbol), None)
                if not stock:
                    continue

                if stock["price"] >= price_target:
                    price_target_alerts.append({
                        "username": username,
                        "symbol": symbol,
                        "current_price": stock["price"],
                        "price_target": price_target,
                        "shares": holding["shares"]
                    })

    return price_target_alerts


def apply_stop_losses():
    """Check all users' holdings against their stop-loss levels and auto-sell."""
    now = datetime.now().isoformat()
    stop_loss_executions = []

    with user_lock:
        for username, user in users.items():
            portfolio = user["portfolio"]
            to_close = []

            for symbol, holding in list(portfolio["holdings"].items()):
                stop_loss = holding.get("stop_loss")
                if stop_loss is None or holding["shares"] <= 0:
                    continue

                stock = next((s for s in stocks if s["symbol"] == symbol), None)
                if not stock:
                    continue

                if stock["price"] <= stop_loss:
                    shares_to_sell = holding["shares"]
                    total_value = round(shares_to_sell * stock["price"], 2)

                    portfolio["cash"] = round(portfolio["cash"] + total_value, 2)

                    portfolio["transactions"].append({
                        "type": "stop_loss_sell",
                        "symbol": symbol,
                        "shares": shares_to_sell,
                        "price": stock["price"],
                        "total": total_value,
                        "timestamp": now,
                        "username": username,
                    })

                    to_close.append(symbol)

                    stop_loss_executions.append({
                        "username": username,
                        "symbol": symbol,
                        "shares": shares_to_sell,
                        "price": stock["price"],
                        "total": total_value
                    })

            for symbol in to_close:
                portfolio["holdings"].pop(symbol, None)

            portfolio["total_value"] = calculate_portfolio_value(portfolio)

    return stop_loss_executions


# -----------------------------
# Real GSE data fetching functions
# -----------------------------
def fetch_gse_data_from_afx():
    """Fetch real GSE data from afx.kwayisi.org using urllib"""
    try:
        req = urllib.request.Request(
            'https://afx.kwayisi.org/gse/',
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')

        parser = TableParser()
        parser.feed(html)

        stock_data = []
        for row in parser.rows:
            if len(row) >= 4:
                symbol = row[1] if len(row) > 1 else ""
                price_text = row[3] if len(row) > 3 else ""

                price_text = price_text.replace('?', '').replace(',', '').strip()
                if price_text and symbol:
                    try:
                        price = float(price_text)
                        stock_data.append({'symbol': symbol, 'price': price})
                    except ValueError:
                        continue

        return stock_data

    except Exception as e:
        print(f"Error fetching from AFX: {e}")
        return None


def fetch_gse_data_from_api():
    """Fetch real GSE data from dev.kwayisi.org API using urllib"""
    try:
        req = urllib.request.Request(
            'https://dev.kwayisi.org/apis/gse/live',
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )

        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode('utf-8'))

        stock_data = []

        if isinstance(data, list):
            for item in data:
                if 'name' in item and 'price' in item:
                    try:
                        stock_data.append({
                            'symbol': item['name'],
                            'price': float(item['price'])
                        })
                    except (ValueError, TypeError):
                        continue

        return stock_data

    except Exception as e:
        print(f"Error fetching from GSE API: {e}")
        return None


def update_prices_with_real_data():
    """Update stock prices with real GSE data"""
    real_data = fetch_gse_data_from_afx()

    if not real_data:
        real_data = fetch_gse_data_from_api()

    if real_data:
        with stock_lock:
            updated_count = 0
            for stock in stocks:
                for real_stock in real_data:
                    if stock['symbol'] == real_stock['symbol']:
                        stock['price'] = real_stock['price']
                        stock['history'].append({
                            "time": datetime.now().isoformat(),
                            "price": stock['price']
                        })
                        if len(stock['history']) > 100:
                            stock['history'].pop(0)
                        updated_count += 1
                        break

        print(f"Updated {updated_count} stocks with real GSE data")
        return True
    else:
        print("Failed to fetch real GSE data, falling back to simulated data")
        return False


def update_prices():
    """
    Background thread: simulate price changes every 10 seconds.
    When market is open, tries to fetch real GSE data every 30 seconds.
    """
    last_real_update = 0
    real_update_interval = 30

    while True:
        time.sleep(10)

        with stock_lock:
            if market_open:
                current_time = time.time()

                if current_time - last_real_update >= real_update_interval:
                    real_data_fetched = update_prices_with_real_data()
                    if real_data_fetched:
                        last_real_update = current_time
                        stop_loss_executions = apply_stop_losses()
                        price_target_alerts = check_price_targets()

                        app.recent_alerts['stop_loss'].extend(stop_loss_executions)
                        app.recent_alerts['price_target'].extend(price_target_alerts)
                        app.recent_alerts['stop_loss'] = app.recent_alerts['stop_loss'][-50:]
                        app.recent_alerts['price_target'] = app.recent_alerts['price_target'][-50:]
                        continue

                now = datetime.now()
                for stock in stocks:
                    if stock["price"] > 0:
                        change = random.uniform(-0.02, 0.02)
                        stock["price"] = max(0.01, stock["price"] * (1 + change))
                        stock["price"] = round(stock["price"], 2)
                        stock["history"].append({"time": now.isoformat(), "price": stock["price"]})
                        if len(stock["history"]) > 100:
                            stock["history"].pop(0)

                stop_loss_executions = apply_stop_losses()
                price_target_alerts = check_price_targets()

                app.recent_alerts['stop_loss'].extend(stop_loss_executions)
                app.recent_alerts['price_target'].extend(price_target_alerts)
                app.recent_alerts['stop_loss'] = app.recent_alerts['stop_loss'][-50:]
                app.recent_alerts['price_target'] = app.recent_alerts['price_target'][-50:]


# -----------------------------
# Auth helpers
# -----------------------------
def get_current_user():
    if "user_id" not in session:
        return None
    username = session.get("username")
    if username and username in users:
        return users[username]
    return None


def is_admin():
    return session.get("is_admin", False)


# -----------------------------
# Routes: pages
# -----------------------------
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", username=session.get("username"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == admin_password:
            session["user_id"] = "admin"
            session["username"] = "admin"
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))

        if not username or not password:
            return render_template("login.html", error="Please enter both username and password")

        user = users.get(username)
        if not user or user["password"] != password:
            return render_template("login.html", error="Invalid username or password")

        session["user_id"] = user["id"]
        session["username"] = username
        session["is_admin"] = False
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not username or not password:
            return render_template("signup.html", error="Please enter both username and password")

        if password != confirm_password:
            return render_template("signup.html", error="Passwords do not match")

        if username in users:
            return render_template("signup.html", error="Username already exists")

        user_id = str(uuid.uuid4())
        with user_lock:
            users[username] = {
                "id": user_id,
                "username": username,
                "password": password,
                "portfolio": init_portfolio(),
            }

        session["user_id"] = user_id
        session["username"] = username
        session["is_admin"] = False
        return redirect(url_for("index"))

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("is_admin", None)
    return redirect(url_for("login"))


@app.route("/admin")
def admin_dashboard():
    if not is_admin():
        return redirect(url_for("login"))
    return render_template("admin.html")


# -----------------------------
# API routes
# -----------------------------
@app.route("/api/stocks")
def get_stocks():
    with stock_lock:
        stocks_data = [stock.copy() for stock in stocks]
        for stock in stocks_data:
            stock['market_open'] = market_open
        return jsonify(stocks_data)


@app.route("/api/portfolio")
def get_portfolio():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    portfolio = user["portfolio"]
    portfolio["total_value"] = calculate_portfolio_value(portfolio)
    portfolio["market_open"] = market_open
    return jsonify(portfolio)


@app.route("/api/buy", methods=["POST"])
def buy_stock():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.json or {}
    symbol = data.get("symbol")
    shares = int(data.get("shares", 0))

    if not symbol or shares <= 0:
        return jsonify({"error": "Invalid symbol or shares"}), 400

    with stock_lock:
        stock = next((s for s in stocks if s["symbol"] == symbol), None)

    if not stock:
        return jsonify({"error": "Stock not found"}), 404

    if not market_open:
        return jsonify({"error": "Market is currently closed. Trading is not allowed."}), 400

    order_type = (data.get("order_type") or "market").lower()
    limit_price = data.get("limit_price")
    stop_loss = data.get("stop_loss")
    price_target = data.get("price_target")

    if limit_price is not None:
        try:
            limit_price = float(limit_price)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid limit price"}), 400

    if stop_loss is not None:
        try:
            stop_loss = float(stop_loss)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid stop-loss price"}), 400

    if price_target is not None:
        try:
            price_target = float(price_target)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid price target"}), 400

    current_price = stock["price"]

    if order_type == "limit":
        if limit_price is None:
            return jsonify({"error": "Limit price is required for limit orders"}), 400
        if current_price > limit_price:
            return jsonify({
                "error": "Limit price not reached. Current price is above your limit.",
                "current_price": current_price,
                "limit_price": limit_price,
            }), 400

    total_cost = shares * current_price

    with user_lock:
        portfolio = user["portfolio"]

        if total_cost > portfolio["cash"]:
            return jsonify({"error": "Insufficient funds"}), 400

        portfolio["cash"] = round(portfolio["cash"] - total_cost, 2)

        if symbol in portfolio["holdings"]:
            holding = portfolio["holdings"][symbol]
            total_shares = holding["shares"] + shares
            holding["avg_cost"] = round(
                ((holding["avg_cost"] * holding["shares"]) + (current_price * shares)) / total_shares, 2
            )
            holding["shares"] = total_shares
            if stop_loss is not None:
                holding["stop_loss"] = stop_loss
            if price_target is not None:
                holding["price_target"] = price_target
        else:
            portfolio["holdings"][symbol] = {
                "shares": shares,
                "avg_cost": current_price,
                "stop_loss": stop_loss,
                "price_target": price_target,
            }

        portfolio["transactions"].append({
            "type": "buy" if order_type == "market" else "buy_limit",
            "symbol": symbol,
            "shares": shares,
            "price": current_price,
            "total": round(total_cost, 2),
            "timestamp": datetime.now().isoformat(),
            "username": user["username"],
            "stop_loss": stop_loss,
            "price_target": price_target,
        })

        portfolio["total_value"] = calculate_portfolio_value(portfolio)
        return jsonify({"success": True, "portfolio": portfolio, "order_value": round(total_cost, 2)})


@app.route("/api/sell", methods=["POST"])
def sell_stock():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.json or {}
    symbol = data.get("symbol")
    shares = int(data.get("shares", 0))

    if not symbol or shares <= 0:
        return jsonify({"error": "Invalid symbol or shares"}), 400

    with stock_lock:
        stock = next((s for s in stocks if s["symbol"] == symbol), None)

    if not stock:
        return jsonify({"error": "Stock not found"}), 404

    if not market_open:
        return jsonify({"error": "Market is currently closed. Trading is not allowed."}), 400

    with user_lock:
        portfolio = user["portfolio"]

        if symbol not in portfolio["holdings"]:
            return jsonify({"error": "Stock not in portfolio"}), 400

        holding = portfolio["holdings"][symbol]

        if holding["shares"] < shares:
            return jsonify({"error": "Insufficient shares"}), 400

        current_price = stock["price"]
        total_value = round(shares * current_price, 2)

        portfolio["cash"] = round(portfolio["cash"] + total_value, 2)
        holding["shares"] -= shares
        if holding["shares"] == 0:
            portfolio["holdings"].pop(symbol, None)

        portfolio["transactions"].append({
            "type": "sell",
            "symbol": symbol,
            "shares": shares,
            "price": current_price,
            "total": total_value,
            "timestamp": datetime.now().isoformat(),
            "username": user["username"],
        })

        portfolio["total_value"] = calculate_portfolio_value(portfolio)
        return jsonify({"success": True, "portfolio": portfolio, "order_value": total_value})


@app.route("/api/update_order_settings", methods=["POST"])
def update_order_settings():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.json or {}
    symbol = data.get("symbol")
    stop_loss = data.get("stop_loss")
    price_target = data.get("price_target")

    if not symbol:
        return jsonify({"error": "Symbol is required"}), 400

    with user_lock:
        portfolio = user["portfolio"]

        if symbol not in portfolio["holdings"]:
            return jsonify({"error": "Stock not in portfolio"}), 400

        holding = portfolio["holdings"][symbol]

        if stop_loss is not None:
            try:
                holding["stop_loss"] = float(stop_loss)
            except (TypeError, ValueError):
                return jsonify({"error": "Invalid stop-loss price"}), 400

        if price_target is not None:
            try:
                holding["price_target"] = float(price_target)
            except (TypeError, ValueError):
                return jsonify({"error": "Invalid price target"}), 400

        return jsonify({"success": True, "holding": holding})


@app.route("/api/alerts")
def get_recent_alerts():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    username = user["username"]
    user_alerts = {
        'stop_loss': [a for a in app.recent_alerts['stop_loss'] if a['username'] == username],
        'price_target': [a for a in app.recent_alerts['price_target'] if a['username'] == username]
    }

    return jsonify(user_alerts)


@app.route("/api/reset", methods=["POST"])
def reset_portfolio():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    with user_lock:
        user["portfolio"] = init_portfolio()
        return jsonify({"success": True, "portfolio": user["portfolio"]})


@app.route("/api/history/<symbol>")
def get_stock_history(symbol):
    with stock_lock:
        stock = next((s for s in stocks if s["symbol"] == symbol), None)
    if not stock:
        return jsonify({"error": "Stock not found"}), 404
    return jsonify(stock["history"])


@app.route("/api/admin/leaderboard")
def get_admin_leaderboard():
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403

    leaderboard = []

    with user_lock:
        for username, user in users.items():
            portfolio = user["portfolio"]
            current_value = portfolio["total_value"]
            starting_value = 100000.00
            growth = ((current_value - starting_value) / starting_value) * 100

            holdings_value = {}
            for symbol, holding in portfolio["holdings"].items():
                stock = next((s for s in stocks if s["symbol"] == symbol), None)
                if stock:
                    holdings_value[symbol] = {
                        "shares": holding["shares"],
                        "current_value": holding["shares"] * stock["price"],
                        "avg_cost": holding["avg_cost"]
                    }

            leaderboard.append({
                "username": username,
                "portfolio_value": current_value,
                "growth_percent": round(growth, 2),
                "cash": portfolio["cash"],
                "holdings_count": len(portfolio["holdings"]),
                "holdings_value": holdings_value,
                "total_trades": len(portfolio["transactions"]),
                "rank": 0
            })

    leaderboard.sort(key=lambda x: x["portfolio_value"], reverse=True)
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return jsonify(leaderboard)


@app.route("/api/admin/users")
def get_admin_users():
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403

    users_data = []

    with user_lock:
        for username, user in users.items():
            portfolio = user["portfolio"]
            current_value = portfolio["total_value"]
            starting_value = 100000.00
            growth = ((current_value - starting_value) / starting_value) * 100

            users_data.append({
                "username": username,
                "portfolio_value": current_value,
                "growth_percent": round(growth, 2),
                "cash": portfolio["cash"],
                "holdings_count": len(portfolio["holdings"]),
                "total_trades": len(portfolio["transactions"]),
                "registered_at": "Active"
            })

    return jsonify(users_data)


@app.route("/api/admin/stats")
def get_admin_stats():
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403

    with user_lock:
        total_users = len(users)
        total_portfolio_value = sum(user["portfolio"]["total_value"] for user in users.values())
        average_portfolio_value = total_portfolio_value / total_users if total_users > 0 else 0
        active_traders = sum(1 for user in users.values() if len(user["portfolio"]["holdings"]) > 0)
        total_trades = sum(len(user["portfolio"]["transactions"]) for user in users.values())

    with stock_lock:
        total_market_cap = sum(stock["price"] * 1000000 for stock in stocks)
        biggest_gainer = max(stocks, key=lambda x: x["price"])
        biggest_loser = min(stocks, key=lambda x: x["price"])

    return jsonify({
        "total_users": total_users,
        "total_portfolio_value": round(total_portfolio_value, 2),
        "average_portfolio_value": round(average_portfolio_value, 2),
        "active_traders": active_traders,
        "total_trades": total_trades,
        "market_open": market_open,
        "market_stats": {
            "total_market_cap": round(total_market_cap, 2),
            "biggest_gainer": {"symbol": biggest_gainer["symbol"], "price": biggest_gainer["price"]},
            "biggest_loser": {"symbol": biggest_loser["symbol"], "price": biggest_loser["price"]}
        }
    })


@app.route("/api/admin/reset_competition", methods=["POST"])
def reset_competition():
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403

    with user_lock:
        users.clear()

    return jsonify({"success": True, "message": "Competition reset successfully. All users cleared."})


@app.route("/api/admin/market_control", methods=["POST"])
def market_control():
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403

    data = request.json or {}
    action = data.get("action")

    global market_open

    if action == "open":
        market_open = True
        return jsonify({"success": True, "message": "Market opened successfully", "market_open": True})
    elif action == "close":
        market_open = False
        return jsonify({"success": True, "message": "Market closed successfully", "market_open": False})
    else:
        return jsonify({"error": "Invalid action. Use 'open' or 'close'"}), 400


@app.route("/api/calculate_order_value", methods=["POST"])
def calculate_order_value():
    data = request.json or {}
    symbol = data.get("symbol")
    shares = int(data.get("shares", 0))
    action = data.get("action", "buy")

    if not symbol or shares <= 0:
        return jsonify({"error": "Invalid symbol or shares"}), 400

    with stock_lock:
        stock = next((s for s in stocks if s["symbol"] == symbol), None)

    if not stock:
        return jsonify({"error": "Stock not found"}), 404

    current_price = stock["price"]
    total_value = shares * current_price

    return jsonify({
        "symbol": symbol,
        "shares": shares,
        "price": current_price,
        "total_value": round(total_value, 2),
        "action": action
    })


# -----------------------------
# Start background thread AFTER all functions are defined
# -----------------------------
price_thread = threading.Thread(target=update_prices, daemon=True)
price_thread.start()

# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
