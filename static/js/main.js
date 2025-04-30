// Portfolio state
let portfolio = {
    cash: 100000,
    holdings: JSON.parse(localStorage.getItem('portfolio-holdings')) || {}
};

// Chart instance
let stockChart;

// Helper function to format numbers with commas and two decimal places
function formatNumber(num) {
    return num.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Fetch and update stocks
async function fetchStocks() {
    try {
        const response = await fetch('/api/stocks');
        const stocks = await response.json();
        updateStockTable(stocks);
        updatePortfolioTable(stocks);
        updateDashboard(stocks);
    } catch (error) {
        showError('Failed to fetch stock data. Please try again.');
    }
}

// Update stock table
function updateStockTable(stocks) {
    const tbody = document.getElementById('stocks-table-body');
    const searchQuery = document.getElementById('search-input').value.toLowerCase();
    
    tbody.innerHTML = '';
    stocks.forEach(stock => {
        if (stock.name.toLowerCase().includes(searchQuery) || stock.symbol.toLowerCase().includes(searchQuery)) {
            const row = document.createElement('tr');
            const change = stock.history.length > 1 ? 
                ((stock.price - stock.history[stock.history.length - 2].price) / stock.history[stock.history.length - 2].price * 100).toFixed(2) : 0;
            row.innerHTML = `
                <td>${stock.symbol}</td>
                <td>${stock.name}</td>
                <td>${formatNumber(stock.price)}</td>
                <td class="${change >= 0 ? 'positive' : 'negative'}">${formatNumber(parseFloat(change))}%</td>
                <td>
                    <input type="number" min="1" placeholder="Shares" id="shares-${stock.symbol}">
                    <button onclick="buyStock('${stock.symbol}', ${stock.price})" class="btn">Buy</button>
                    <button onclick="sellStock('${stock.symbol}', ${stock.price})" class="btn">Sell</button>
                </td>
            `;
            tbody.appendChild(row);
        }
    });
}

// Update portfolio table
function updatePortfolioTable(stocks) {
    const tbody = document.getElementById('holdings-table-body');
    tbody.innerHTML = '';
    let totalValue = portfolio.cash;

    Object.keys(portfolio.holdings).forEach(symbol => {
        const stock = stocks.find(s => s.symbol === symbol);
        if (stock) {
            const holding = portfolio.holdings[symbol];
            const currentValue = holding.shares * stock.price;
            const gainLoss = ((currentValue - holding.cost) / holding.cost * 100).toFixed(2);
            totalValue += currentValue;

            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${symbol}</td>
                <td>${formatNumber(holding.shares)}</td>
                <td>${formatNumber(holding.cost / holding.shares)}</td>
                <td>${formatNumber(currentValue)}</td>
                <td class="${gainLoss >= 0 ? 'positive' : 'negative'}">${formatNumber(parseFloat(gainLoss))}%</td>
                <td>
                    <button onclick="viewChart('${symbol}')" class="btn">View Chart</button>
                </td>
            `;
            tbody.appendChild(row);
        }
    });

    document.getElementById('total-value').textContent = formatNumber(totalValue) + ' GHS';
}

// Update dashboard
function updateDashboard(stocks) {
    document.getElementById('cash').textContent = formatNumber(portfolio.cash) + ' GHS';
    const marketStatus = new Date().getHours() >= 9 && new Date().getHours() < 15 ? 'Open' : 'Open';
    document.getElementById('market-status').textContent = marketStatus;
}

// Buy stock
function buyStock(symbol, price) {
    const sharesInput = document.getElementById(`shares-${symbol}`);
    const shares = parseInt(sharesInput.value);
    if (!shares || shares <= 0) {
        showError('Please enter a valid number of shares.');
        return;
    }

    const cost = shares * price;
    if (cost > portfolio.cash) {
        showError('Insufficient cash balance.');
        return;
    }

    portfolio.cash -= cost;
    if (portfolio.holdings[symbol]) {
        const holding = portfolio.holdings[symbol];
        const totalShares = holding.shares + shares;
        holding.cost = ((holding.cost * holding.shares) + cost) / totalShares;
        holding.shares = totalShares;
    } else {
        portfolio.holdings[symbol] = { shares, cost };
    }

    savePortfolio();
    fetchStocks();
    sharesInput.value = '';
    showError('');
}

// Sell stock
function sellStock(symbol, price) {
    const sharesInput = document.getElementById(`shares-${symbol}`);
    const shares = parseInt(sharesInput.value);
    if (!shares || shares <= 0) {
        showError('Please enter a valid number of shares.');
        return;
    }

    if (!portfolio.holdings[symbol] || portfolio.holdings[symbol].shares < shares) {
        showError('You do not own enough shares.');
        return;
    }

    portfolio.cash += shares * price;
    portfolio.holdings[symbol].shares -= shares;
    if (portfolio.holdings[symbol].shares === 0) {
        delete portfolio.holdings[symbol];
    }

    savePortfolio();
    fetchStocks();
    sharesInput.value = '';
    showError('');
}

// Reset portfolio
function resetPortfolio() {
    portfolio = { cash: 100000, holdings: {} };
    savePortfolio();
    fetchStocks();
    showError('Portfolio reset successfully.');
}

// Save portfolio to localStorage
function savePortfolio() {
    localStorage.setItem('portfolio-holdings', JSON.stringify(portfolio.holdings));
}

// Show error message
function showError(message) {
    const errorDiv = document.getElementById('error-message');
    errorDiv.textContent = message;
    if (message) {
        errorDiv.style.display = 'block';
        setTimeout(() => errorDiv.style.display = 'none', 3000);
    }
}

// View stock chart
async function viewChart(symbol) {
    const response = await fetch('/api/stocks');
    const stocks = await response.json();
    const stock = stocks.find(s => s.symbol === symbol);
    if (!stock) return;

    const ctx = document.getElementById('stock-chart').getContext('2d');
    if (stockChart) stockChart.destroy();

    stockChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: stock.history.map(h => new Date(h.time).toLocaleTimeString()),
            datasets: [{
                label: `${symbol} Price (GHS)`,
                data: stock.history.map(h => h.price),
                borderColor: '#006633',
                backgroundColor: 'rgba(0, 102, 51, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            scales: {
                x: { title: { display: true, text: 'Time' } },
                y: { title: { display: true, text: 'Price (GHS)' } }
            }
        }
    });
}

// Theme toggle
document.getElementById('theme-toggle').addEventListener('click', () => {
    document.body.classList.toggle('dark-theme');
    const icon = document.getElementById('theme-toggle').querySelector('i');
    icon.classList.toggle('fa-moon');
    icon.classList.toggle('fa-sun');
    localStorage.setItem('theme', document.body.classList.contains('dark-theme') ? 'dark' : 'light');
});

// Search input
document.getElementById('search-input').addEventListener('input', fetchStocks);

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    if (localStorage.getItem('theme') === 'dark') {
        document.body.classList.add('dark-theme');
        document.getElementById('theme-toggle').querySelector('i').classList.replace('fa-moon', 'fa-sun');
    }
    fetchStocks();
    setInterval(fetchStocks, 60000); // Update every minute
});

// CSS for dynamic classes
const style = document.createElement('style');
style.innerHTML = `
    .positive { color: #22c55e; }
    .negative { color: #ef4444; }
`;
document.head.appendChild(style);