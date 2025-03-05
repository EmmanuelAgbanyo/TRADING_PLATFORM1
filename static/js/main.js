let stocks = [];
let portfolio = JSON.parse(localStorage.getItem('portfolio')) || { cash: 100000, holdings: {} };

// Fetch stocks from the API
async function fetchStocks() {
    try {
        const response = await fetch('/api/stocks');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        stocks = await response.json();
        updateStockTable();
        updatePortfolioValue();
    } catch (error) {
        console.error('Error fetching stocks:', error);
        document.getElementById('error-message').textContent = `Failed to load stock data: ${error.message}. Please try refreshing the page.`;
    }
}

// Update the stock table with search functionality
function updateStockTable() {
    const searchInput = document.getElementById('search-input').value.toLowerCase();
    const tableBody = document.getElementById('stocks-table-body');
    tableBody.innerHTML = '';
    stocks.forEach(stock => {
        if (stock.symbol.toLowerCase().includes(searchInput) || stock.name.toLowerCase().includes(searchInput)) {
            const row = `
                <tr>
                    <td>${stock.symbol}</td>
                    <td>${stock.name}</td>
                    <td>${stock.price.toFixed(2)}</td>
                    <td>
                        <input type="number" min="1" id="shares-${stock.symbol}" placeholder="Shares">
                        <button onclick="buy('${stock.symbol}', ${stock.price})">Buy</button>
                        <button onclick="sell('${stock.symbol}', ${stock.price})">Sell</button>
                    </td>
                </tr>`;
            tableBody.innerHTML += row;
        }
    });
}

// Update portfolio value
function updatePortfolioValue() {
    let totalValue = portfolio.cash;
    const holdingsTableBody = document.getElementById('holdings-table-body');
    holdingsTableBody.innerHTML = '';
    for (const symbol in portfolio.holdings) {
        const holding = portfolio.holdings[symbol];
        const stock = stocks.find(s => s.symbol === symbol);
        if (stock && stock.price > 0) {
            const cost = holding.shares * holding.purchase_price;
            const current_value = holding.shares * stock.price;
            const gain_loss = ((current_value - cost) / cost) * 100;
            totalValue += current_value;
            const row = `
                <tr>
                    <td>${symbol}</td>
                    <td>${holding.shares}</td>
                    <td>${cost.toFixed(2)}</td>
                    <td>${current_value.toFixed(2)}</td>
                    <td>${gain_loss.toFixed(2)}%</td>
                </tr>`;
            holdingsTableBody.innerHTML += row;
        }
    }
    document.getElementById('cash').textContent = portfolio.cash.toFixed(2);
    document.getElementById('total-value').textContent = totalValue.toFixed(2);
    localStorage.setItem('portfolio', JSON.stringify(portfolio));
}

// Buy stock
function buy(symbol, purchase_price) {
    const sharesInput = document.getElementById(`shares-${symbol}`);
    const shares = parseInt(sharesInput.value);
    if (!shares || shares <= 0) {
        document.getElementById('error-message').textContent = 'Please enter a valid number of shares.';
        return;
    }
    const cost = shares * purchase_price;
    if (cost > portfolio.cash) {
        document.getElementById('error-message').textContent = 'Insufficient cash to complete this purchase.';
        return;
    }
    portfolio.cash -= cost;
    if (portfolio.holdings[symbol]) {
        const existing = portfolio.holdings[symbol];
        const totalShares = existing.shares + shares;
        existing.purchase_price = (existing.purchase_price * existing.shares + purchase_price * shares) / totalShares;
        existing.shares = totalShares;
    } else {
        portfolio.holdings[symbol] = { shares: shares, purchase_price: purchase_price };
    }
    updatePortfolioValue();
    document.getElementById('error-message').textContent = `Bought ${shares} shares of ${symbol} successfully.`;
    sharesInput.value = '';
}

// Sell stock
function sell(symbol, current_price) {
    const sharesInput = document.getElementById(`shares-${symbol}`);
    const shares = parseInt(sharesInput.value);
    if (!shares || shares <= 0) {
        document.getElementById('error-message').textContent = 'Please enter a valid number of shares.';
        return;
    }
    if (!portfolio.holdings[symbol] || portfolio.holdings[symbol].shares < shares) {
        document.getElementById('error-message').textContent = 'Not enough shares to sell.';
        return;
    }
    const revenue = shares * current_price;
    portfolio.holdings[symbol].shares -= shares;
    portfolio.cash += revenue;
    if (portfolio.holdings[symbol].shares === 0) {
        delete portfolio.holdings[symbol];
    }
    updatePortfolioValue();
    document.getElementById('error-message').textContent = `Sold ${shares} shares of ${symbol} successfully.`;
    sharesInput.value = '';
}

// Reset portfolio
function resetPortfolio() {
    localStorage.removeItem('portfolio');
    portfolio = { cash: 100000, holdings: {} };
    updatePortfolioValue();
    document.getElementById('error-message').textContent = 'Portfolio reset successfully.';
}

// Search input event listener
document.getElementById('search-input').addEventListener('input', updateStockTable);

// Initial fetch and update every 10 seconds
fetchStocks();
setInterval(fetchStocks, 10000);

// Sample chart
const ctx = document.getElementById('stock-chart').getContext('2d');
const chart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        datasets: [{
            label: 'Sample Stock Price',
            data: [12, 19, 3, 5, 2, 3],
            borderColor: '#FFA500', /* Orange from GSE */
            backgroundColor: 'rgba(255, 165, 0, 0.2)',
        }]
    },
    options: {
        scales: {
            y: {
                beginAtZero: true
            }
        }
    }
});