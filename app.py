from flask import Flask, jsonify, render_template, session, request, redirect, url_for
import random
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a real secret key

# User database (in-memory for simplicity)
users = {}

# Full stock list from GSE with sector information
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

last_update_time = datetime.now()

def init_portfolio():
    """Initialize user portfolio"""
    return {
        'cash': 100000.00,
        'holdings': {},
        'total_value': 100000.00,
        'transactions': []
    }

def update_prices():
    """Simulate price changes (±2%) for stocks every minute, ensuring prices stay non-negative."""
    global last_update_time
    now = datetime.now()
    if now - last_update_time > timedelta(minutes=1):
        print("Updating prices...")
        for stock in stocks:
            if stock["price"] > 0:
                # More volatile price changes
                change = random.uniform(-0.02, 0.02)
                stock["price"] = max(0.01, stock["price"] * (1 + change))
                stock["price"] = round(stock["price"], 2)
                # Store price history for charting
                stock["history"].append({"time": now.isoformat(), "price": stock["price"]})
                if len(stock["history"]) > 100:  # Keep last 100 minutes
                    stock["history"].pop(0)
        last_update_time = now

def calculate_portfolio_value(portfolio):
    """Calculate total portfolio value"""
    total = portfolio['cash']
    for symbol, holding in portfolio['holdings'].items():
        stock = next((s for s in stocks if s['symbol'] == symbol), None)
        if stock:
            total += holding['shares'] * stock['price']
    return round(total, 2)

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session.get('username'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            return render_template('login.html', error='Please enter both username and password')
        user = users.get(username)
        if not user or user['password'] != password:
            return render_template('login.html', error='Invalid username or password')
        session['user_id'] = user['id']
        session['username'] = username
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if not username or not password:
            return render_template('signup.html', error='Please enter both username and password')
        if password != confirm_password:
            return render_template('signup.html', error='Passwords do not match')
        if username in users:
            return render_template('signup.html', error='Username already exists')
        user_id = str(uuid.uuid4())
        users[username] = {
            'id': user_id,
            'username': username,
            'password': password,
            'portfolio': init_portfolio()
        }
        session['user_id'] = user_id
        session['username'] = username
        return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

def get_current_user():
    if 'user_id' not in session:
        return None
    username = session.get('username')
    if username and username in users:
        return users[username]
    return None

@app.route('/api/stocks')
def get_stocks():
    update_prices()
    return jsonify(stocks)

@app.route('/api/portfolio')
def get_portfolio():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    portfolio = user['portfolio']
    portfolio['total_value'] = calculate_portfolio_value(portfolio)
    return jsonify(portfolio)

@app.route('/api/buy', methods=['POST'])
def buy_stock():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    data = request.json
    symbol = data['symbol']
    shares = int(data['shares'])
    
    portfolio = user['portfolio']
    stock = next((s for s in stocks if s['symbol'] == symbol), None)
    
    if not stock:
        return jsonify({'error': 'Stock not found'}), 404
    
    total_cost = shares * stock['price']
    
    if total_cost > portfolio['cash']:
        return jsonify({'error': 'Insufficient funds'}), 400
    
    # Execute trade
    portfolio['cash'] -= total_cost
    portfolio['cash'] = round(portfolio['cash'], 2)
    
    if symbol in portfolio['holdings']:
        holding = portfolio['holdings'][symbol]
        total_shares = holding['shares'] + shares
        # Recalculate average cost
        holding['avg_cost'] = round(
            ((holding['avg_cost'] * holding['shares']) + (stock['price'] * shares)) / total_shares, 
            2
        )
        holding['shares'] = total_shares
    else:
        portfolio['holdings'][symbol] = {
            'shares': shares,
            'avg_cost': stock['price']
        }
    
    # Record transaction
    portfolio['transactions'].append({
        'type': 'buy',
        'symbol': symbol,
        'shares': shares,
        'price': stock['price'],
        'total': round(total_cost, 2),
        'timestamp': datetime.now().isoformat(),
        'username': user['username']
    })
    
    portfolio['total_value'] = calculate_portfolio_value(portfolio)
    return jsonify({'success': True, 'portfolio': portfolio})

@app.route('/api/sell', methods=['POST'])
def sell_stock():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    data = request.json
    symbol = data['symbol']
    shares = int(data['shares'])
    
    portfolio = user['portfolio']
    stock = next((s for s in stocks if s['symbol'] == symbol), None)
    
    if not stock:
        return jsonify({'error': 'Stock not found'}), 404
    
    if symbol not in portfolio['holdings']:
        return jsonify({'error': 'Stock not in portfolio'}), 400
    
    holding = portfolio['holdings'][symbol]
    
    if holding['shares'] < shares:
        return jsonify({'error': 'Insufficient shares'}), 400
    
    # Execute trade
    total_value = shares * stock['price']
    portfolio['cash'] += total_value
    portfolio['cash'] = round(portfolio['cash'], 2)
    
    holding['shares'] -= shares
    if holding['shares'] == 0:
        del portfolio['holdings'][symbol]
    
    # Record transaction
    portfolio['transactions'].append({
        'type': 'sell',
        'symbol': symbol,
        'shares': shares,
        'price': stock['price'],
        'total': round(total_value, 2),
        'timestamp': datetime.now().isoformat(),
        'username': user['username']
    })
    
    portfolio['total_value'] = calculate_portfolio_value(portfolio)
    return jsonify({'success': True, 'portfolio': portfolio})

@app.route('/api/reset', methods=['POST'])
def reset_portfolio():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    user['portfolio'] = init_portfolio()
    return jsonify({'success': True, 'portfolio': user['portfolio']})

@app.route('/api/history/<symbol>')
def get_stock_history(symbol):
    stock = next((s for s in stocks if s['symbol'] == symbol), None)
    if not stock:
        return jsonify({'error': 'Stock not found'}), 404
    return jsonify(stock['history'])

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)