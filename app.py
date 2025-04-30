from flask import Flask, jsonify, render_template
import random
from datetime import datetime, timedelta

app = Flask(__name__)

# Full stock list from GSE (example data)
stocks = [
    {"symbol": "ACCESS", "name": "Access Bank Ghana PLC", "price": 7.50, "history": []},
    {"symbol": "ADB", "name": "Agricultural Development Bank PLC", "price": 5.06, "history": []},
    {"symbol": "ASG", "name": "Asante Gold Corporation", "price": 8.89, "history": []},
    {"symbol": "ALLGH", "name": "Atlantic Lithium Ltd", "price": 6.12, "history": []},
    {"symbol": "BOPP", "name": "Benso Palm Plantation PLC", "price": 26.31, "history": []},
    {"symbol": "CAL", "name": "Cal Bank PLC", "price": 0.64, "history": []},
    {"symbol": "EGH", "name": "Ecobank Ghana PLC.", "price": 6.30, "history": []},
    {"symbol": "EGL", "name": "Enterprise Group PLC", "price": 2.05, "history": []},
    {"symbol": "ETI", "name": "Ecobank Transnational Inc.", "price": 0.75, "history": []},
    {"symbol": "FML", "name": "Fan Milk PLC.", "price": 3.70, "history": []},
    {"symbol": "GCB", "name": "GCB Bank PLC", "price": 6.51, "history": []},
    {"symbol": "GGBL", "name": "Guinness Ghana Breweries PLC", "price": 5.62, "history": []},
    {"symbol": "GOIL", "name": "Ghana Oil Company PLC", "price": 1.60, "history": []},
    {"symbol": "MAC", "name": "Mega African Capital PLC", "price": 5.38, "history": []},
    {"symbol": "MTNGH", "name": "Scancom PLC", "price": 3.10, "history": []},
    {"symbol": "RBGH", "name": "Republic Bank (Ghana) PLC", "price": 0.60, "history": []},
    {"symbol": "SCB", "name": "Standard Chartered Bank Gh. PLC", "price": 25.02, "history": []},
    {"symbol": "SIC", "name": "SIC Insurance Company PLC", "price": 0.37, "history": []},
    {"symbol": "SOGEGH", "name": "Societe Generale Ghana PLC", "price": 1.50, "history": []},
    {"symbol": "TOTAL", "name": "TotalEnergies Marketing Ghana PLC", "price": 16.47, "history": []},
    {"symbol": "TLW", "name": "Tullow Oil PLC", "price": 11.92, "history": []},
    {"symbol": "UNIL", "name": "Unilever Ghana PLC", "price": 19.50, "history": []},
]

last_update_time = datetime.now()

def update_prices():
    """Simulate price changes (±1%) for stocks every minute, ensuring prices stay non-negative."""
    global last_update_time
    now = datetime.now()
    if now - last_update_time > timedelta(minutes=1):
        print("Updating prices...")
        for stock in stocks:
            if stock["price"] > 0:
                change = random.uniform(-0.01, 0.01)
                stock["price"] = max(0, stock["price"] * (1 + change))
                stock["price"] = round(stock["price"], 2)
                # Store price history for charting
                stock["history"].append({"time": now.isoformat(), "price": stock["price"]})
                if len(stock["history"]) > 60:  # Keep last 60 minutes
                    stock["history"].pop(0)
        last_update_time = now

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stocks')
def get_stocks():
    update_prices()
    return jsonify(stocks)

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5001)