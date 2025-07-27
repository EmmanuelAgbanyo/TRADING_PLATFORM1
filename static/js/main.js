// DOM Elements
const themeToggle = document.getElementById('theme-toggle');
const searchInput = document.getElementById('search-input');
const sectorFilter = document.getElementById('sector-filter');
const stockSort = document.getElementById('stock-sort');
const stocksTableBody = document.getElementById('stocks-table-body');
const holdingsTableBody = document.getElementById('holdings-table-body');
const cashElement = document.getElementById('cash');
const totalValueElement = document.getElementById('total-value');
const dailyChangeElement = document.getElementById('daily-change');
const topPerformerElement = document.getElementById('top-performer');
const stockChart = document.getElementById('stock-chart');
const stockSelector = document.getElementById('stock-selector');
const tradeModal = document.getElementById('trade-modal');
const closeModal = document.querySelector('.close');
const tradeTitle = document.getElementById('trade-title');
const tradeSymbol = document.getElementById('trade-symbol');
const tradeName = document.getElementById('trade-name');
const tradePrice = document.getElementById('trade-price');
const tradeChange = document.getElementById('trade-change');
const tradeType = document.getElementById('trade-type');
const tradeShares = document.getElementById('trade-shares');
const tradeEstimate = document.getElementById('trade-estimate');
const confirmTradeBtn = document.getElementById('confirm-trade');
const tradeMessage = document.getElementById('trade-message');
const resetBtn = document.querySelector('.btn-reset');
const timeframeBtns = document.querySelectorAll('.timeframe-btn');
const currentTimeElement = document.getElementById('current-time');

// Global variables
let chart = null;
let currentStock = null;
let portfolio = null;
let allStocks = [];

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    // Set up event listeners
    themeToggle.addEventListener('click', toggleTheme);
    searchInput.addEventListener('input', filterStocks);
    sectorFilter.addEventListener('change', filterStocks);
    stockSort.addEventListener('change', sortStocks);
    closeModal.addEventListener('click', () => tradeModal.style.display = 'none');
    tradeShares.addEventListener('input', updateTradeEstimate);
    tradeType.addEventListener('change', updateTradeEstimate);
    confirmTradeBtn.addEventListener('click', executeTrade);
    resetBtn.addEventListener('click', resetPortfolio);
    timeframeBtns.forEach(btn => btn.addEventListener('click', () => selectTimeframe(btn)));
    
    // Set current time
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);
    
    // Load initial data
    loadStocks();
    loadPortfolio();
    
    // Set up chart
    setupChart();
    
    // Close modal when clicking outside
    window.addEventListener('click', (e) => {
        if (e.target === tradeModal) {
            tradeModal.style.display = 'none';
        }
    });
});

// Theme toggle function
function toggleTheme() {
    document.body.classList.toggle('dark-theme');
    const icon = themeToggle.querySelector('i');
    if (document.body.classList.contains('dark-theme')) {
        icon.classList.remove('fa-moon');
        icon.classList.add('fa-sun');
    } else {
        icon.classList.remove('fa-sun');
        icon.classList.add('fa-moon');
    }
}

// Update current time
function updateCurrentTime() {
    const now = new Date();
    currentTimeElement.textContent = now.toLocaleTimeString();
}

// Load stock data
function loadStocks() {
    fetch('/api/stocks')
        .then(response => response.json())
        .then(stocks => {
            allStocks = stocks;
            renderStocks(stocks);
            populateStockSelector(stocks);
        })
        .catch(error => console.error('Error loading stocks:', error));
}

// Render stocks to table
function renderStocks(stocks) {
    stocksTableBody.innerHTML = '';
    
    stocks.forEach(stock => {
        // Calculate random change for demo
        const change = (Math.random() * 4 - 2).toFixed(2);
        const changeClass = change >= 0 ? 'positive' : 'negative';
        const changeSign = change >= 0 ? '+' : '';
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><strong>${stock.symbol}</strong></td>
            <td>${stock.name}</td>
            <td>${stock.sector}</td>
            <td>${stock.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} GHS</td>
            <td class="${changeClass}">${changeSign}${change}%</td>
            <td>
                <button class="btn btn-outline trade-btn" data-symbol="${stock.symbol}">
                    <i class="fas fa-exchange-alt"></i> Trade
                </button>
            </td>
        `;
        stocksTableBody.appendChild(row);
    });
    
    // Add event listeners to trade buttons
    document.querySelectorAll('.trade-btn').forEach(btn => {
        btn.addEventListener('click', () => openTradeModal(btn.dataset.symbol));
    });
}

// Filter stocks based on search and sector
function filterStocks() {
    const searchTerm = searchInput.value.toLowerCase();
    const sector = sectorFilter.value;
    
    const filtered = allStocks.filter(stock => {
        const matchesSearch = stock.symbol.toLowerCase().includes(searchTerm) || 
                             stock.name.toLowerCase().includes(searchTerm);
        const matchesSector = sector === '' || stock.sector === sector;
        return matchesSearch && matchesSector;
    });
    
    renderStocks(filtered);
}

// Sort stocks
function sortStocks() {
    const sortBy = stockSort.value;
    const sorted = [...allStocks];
    
    switch(sortBy) {
        case 'name':
            sorted.sort((a, b) => a.name.localeCompare(b.name));
            break;
        case 'price':
            sorted.sort((a, b) => b.price - a.price);
            break;
        case 'change':
            // For demo, random change values
            sorted.sort(() => Math.random() - 0.5);
            break;
    }
    
    renderStocks(sorted);
}

// Load portfolio data
function loadPortfolio() {
    fetch('/api/portfolio')
        .then(response => response.json())
        .then(data => {
            portfolio = data;
            renderPortfolio();
            updateDashboard();
        })
        .catch(error => console.error('Error loading portfolio:', error));
}

// Render portfolio to table
function renderPortfolio() {
    holdingsTableBody.innerHTML = '';
    
    if (!portfolio.holdings || Object.keys(portfolio.holdings).length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td colspan="6" style="text-align: center; padding: 2rem;">
                <i class="fas fa-info-circle"></i> You don't own any stocks yet
            </td>
        `;
        holdingsTableBody.appendChild(row);
        return;
    }
    
    let totalPortfolioValue = portfolio.cash;
    
    Object.entries(portfolio.holdings).forEach(([symbol, holding]) => {
        const stock = allStocks.find(s => s.symbol === symbol);
        if (!stock) return;
        
        const currentValue = stock.price * holding.shares;
        totalPortfolioValue += currentValue;
        const gainLoss = ((stock.price - holding.avg_cost) / holding.avg_cost * 100).toFixed(2);
        const gainLossClass = gainLoss >= 0 ? 'positive' : 'negative';
        const gainLossSign = gainLoss >= 0 ? '+' : '';
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><strong>${symbol}</strong></td>
            <td>${holding.shares}</td>
            <td>${holding.avg_cost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} GHS</td>
            <td>${currentValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} GHS</td>
            <td class="${gainLossClass}">${gainLossSign}${gainLoss}%</td>
            <td>
                <button class="btn btn-outline trade-btn" data-symbol="${symbol}">
                    <i class="fas fa-exchange-alt"></i> Trade
                </button>
            </td>
        `;
        holdingsTableBody.appendChild(row);
    });
    
    // Update total portfolio value in dashboard
    totalValueElement.textContent = `${totalPortfolioValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} GHS`;
    
    // Add event listeners to trade buttons
    document.querySelectorAll('.trade-btn').forEach(btn => {
        btn.addEventListener('click', () => openTradeModal(btn.dataset.symbol));
    });
}

// Update dashboard stats
function updateDashboard() {
    cashElement.textContent = `${portfolio.cash.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} GHS`;
    
    // For demo, random daily change
    const dailyChange = (Math.random() * 3 - 1.5).toFixed(2);
    const dailyChangeSign = dailyChange >= 0 ? '+' : '';
    dailyChangeElement.textContent = `${dailyChangeSign}${dailyChange}%`;
    dailyChangeElement.className = dailyChange >= 0 ? 'positive' : 'negative';
    
    // For demo, select a random top performer
    const topStock = allStocks[Math.floor(Math.random() * allStocks.length)];
    const topChange = (Math.random() * 4).toFixed(1);
    topPerformerElement.textContent = `${topStock.symbol} (+${topChange}%)`;
}

// Open trade modal
function openTradeModal(symbol) {
    const stock = allStocks.find(s => s.symbol === symbol);
    if (!stock) return;
    
    currentStock = stock;
    
    // For demo, random change value
    const change = (Math.random() * 4 - 2).toFixed(2);
    const changeSign = change >= 0 ? '+' : '';
    
    // Update modal content
    tradeSymbol.textContent = stock.symbol;
    tradeName.textContent = stock.name;
    tradePrice.textContent = `${stock.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} GHS`;
    tradeChange.textContent = `${changeSign}${change}%`;
    tradeChange.className = change >= 0 ? 'positive' : 'negative';
    tradeShares.value = '1';
    
    // Reset trade type and message
    tradeType.value = 'buy';
    tradeMessage.textContent = '';
    tradeMessage.className = '';
    
    // Update estimate
    updateTradeEstimate();
    
    // Show modal
    tradeModal.style.display = 'flex';
}

// Update trade estimate based on shares and action
function updateTradeEstimate() {
    if (!currentStock) return;
    
    const shares = parseInt(tradeShares.value) || 0;
    const price = currentStock.price;
    const total = shares * price;
    const action = tradeType.value;
    
    tradeEstimate.textContent = `${total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} GHS`;
    tradeTitle.textContent = action === 'buy' ? 'Buy Stock' : 'Sell Stock';
}

// Execute trade
function executeTrade() {
    if (!currentStock) return;
    
    const shares = parseInt(tradeShares.value);
    if (isNaN(shares) || shares <= 0) {
        showTradeMessage('Please enter a valid number of shares', 'error');
        return;
    }
    
    const action = tradeType.value;
    const endpoint = action === 'buy' ? '/api/buy' : '/api/sell';
    
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            symbol: currentStock.symbol,
            shares: shares
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showTradeMessage(data.error, 'error');
        } else {
            portfolio = data.portfolio;
            showTradeMessage(
                `${action === 'buy' ? 'Bought' : 'Sold'} ${shares} shares of ${currentStock.symbol} successfully!`, 
                'success'
            );
            renderPortfolio();
            updateDashboard();
            
            // Close modal after successful trade
            setTimeout(() => {
                tradeModal.style.display = 'none';
            }, 2000);
        }
    })
    .catch(error => {
        showTradeMessage('Error executing trade: ' + error.message, 'error');
    });
}

// Show trade message
function showTradeMessage(message, type) {
    tradeMessage.textContent = message;
    tradeMessage.className = type;
}

// Reset portfolio
function resetPortfolio() {
    if (!confirm('Are you sure you want to reset your portfolio? All holdings and transactions will be lost.')) {
        return;
    }
    
    fetch('/api/reset', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        portfolio = data.portfolio;
        renderPortfolio();
        updateDashboard();
    })
    .catch(error => console.error('Error resetting portfolio:', error));
}

// Populate stock selector for charts
function populateStockSelector(stocks) {
    stockSelector.innerHTML = '<option value="">Select a stock...</option>';
    stocks.forEach(stock => {
        const option = document.createElement('option');
        option.value = stock.symbol;
        option.textContent = `${stock.symbol} - ${stock.name}`;
        stockSelector.appendChild(option);
    });
    
    stockSelector.addEventListener('change', () => {
        if (stockSelector.value) {
            loadStockHistory(stockSelector.value);
        } else {
            if (chart) chart.destroy();
        }
    });
}

// Load stock history for chart
function loadStockHistory(symbol) {
    fetch(`/api/history/${symbol}`)
        .then(response => response.json())
        .then(history => {
            renderStockChart(history, symbol);
        })
        .catch(error => console.error('Error loading stock history:', error));
}

// Setup chart
function setupChart() {
    const ctx = stockChart.getContext('2d');
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Stock Price',
                data: [],
                borderColor: '#006633',
                backgroundColor: 'rgba(0, 102, 51, 0.1)',
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    }
                },
                y: {
                    beginAtZero: false,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        callback: function(value) {
                            return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' GHS';
                        }
                    }
                }
            }
        }
    });
}

// Render stock chart
function renderStockChart(history, symbol) {
    const labels = history.map((point, index) => {
        const date = new Date(point.time);
        return `${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`;
    });
    
    const data = history.map(point => point.price);
    
    const stock = allStocks.find(s => s.symbol === symbol);
    const currentPrice = stock ? stock.price : 0;
    const change = data.length > 1 ? ((currentPrice - data[0]) / data[0] * 100).toFixed(2) : 0;
    
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.data.datasets[0].label = `${symbol} Price`;
    chart.data.datasets[0].borderColor = change >= 0 ? '#10b981' : '#ef4444';
    chart.data.datasets[0].backgroundColor = change >= 0 ? 
        'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)';
    chart.update();
}

// Select timeframe for chart
function selectTimeframe(btn) {
    timeframeBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    
    // For demo, reload chart with selected timeframe
    if (stockSelector.value) {
        loadStockHistory(stockSelector.value);
    }
}