/**
 * React Dashboard Example
 * ======================
 * 
 * This example demonstrates Understand-First with a React dashboard application.
 * It shows how the tool handles modern React patterns, hooks, state management,
 * and component architecture.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import './App.css';

// Custom hooks for data fetching and state management
const useApi = (url, options = {}) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        },
        ...options
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [url, options]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
};

const useLocalStorage = (key, initialValue) => {
  const [storedValue, setStoredValue] = useState(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.error(`Error reading localStorage key "${key}":`, error);
      return initialValue;
    }
  });

  const setValue = useCallback((value) => {
    try {
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      console.error(`Error setting localStorage key "${key}":`, error);
    }
  }, [key, storedValue]);

  return [storedValue, setValue];
};

// Context for global state management
const AppContext = React.createContext();

const AppProvider = ({ children }) => {
  const [user, setUser] = useLocalStorage('user', null);
  const [theme, setTheme] = useLocalStorage('theme', 'light');
  const [notifications, setNotifications] = useState([]);

  const addNotification = useCallback((message, type = 'info') => {
    const id = Date.now();
    setNotifications(prev => [...prev, { id, message, type, timestamp: new Date() }]);
    
    // Auto-remove notification after 5 seconds
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 5000);
  }, []);

  const removeNotification = useCallback((id) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  }, []);

  const login = useCallback((userData) => {
    setUser(userData);
    addNotification('Successfully logged in!', 'success');
  }, [addNotification]);

  const logout = useCallback(() => {
    setUser(null);
    addNotification('Logged out successfully', 'info');
  }, [addNotification]);

  const value = useMemo(() => ({
    user,
    theme,
    notifications,
    login,
    logout,
    toggleTheme,
    addNotification,
    removeNotification
  }), [user, theme, notifications, login, logout, toggleTheme, addNotification, removeNotification]);

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
};

const useApp = () => {
  const context = React.useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};

// Utility functions for data processing
const calculateMetrics = (data) => {
  if (!data || !Array.isArray(data)) return { total: 0, average: 0, trend: 0 };
  
  const total = data.reduce((sum, item) => sum + (item.value || 0), 0);
  const average = data.length > 0 ? total / data.length : 0;
  const trend = data.length > 1 ? 
    ((data[data.length - 1].value || 0) - (data[0].value || 0)) / data.length : 0;
  
  return { total, average, trend };
};

const formatCurrency = (amount) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(amount);
};

const formatDate = (date) => {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(date));
};

// Reusable components
const LoadingSpinner = ({ size = 'medium' }) => (
  <div className={`loading-spinner ${size}`}>
    <div className="spinner"></div>
  </div>
);

const ErrorMessage = ({ error, onRetry }) => (
  <div className="error-message">
    <h3>Something went wrong</h3>
    <p>{error}</p>
    {onRetry && (
      <button onClick={onRetry} className="retry-button">
        Try Again
      </button>
    )}
  </div>
);

const Notification = ({ notification, onRemove }) => (
  <div className={`notification ${notification.type}`}>
    <span className="message">{notification.message}</span>
    <button 
      className="close-button" 
      onClick={() => onRemove(notification.id)}
      aria-label="Close notification"
    >
      ×
    </button>
  </div>
);

const NotificationContainer = () => {
  const { notifications, removeNotification } = useApp();
  
  return (
    <div className="notification-container">
      {notifications.map(notification => (
        <Notification
          key={notification.id}
          notification={notification}
          onRemove={removeNotification}
        />
      ))}
    </div>
  );
};

// Dashboard components
const MetricCard = ({ title, value, trend, icon, color = 'blue' }) => {
  const trendClass = trend > 0 ? 'positive' : trend < 0 ? 'negative' : 'neutral';
  const trendIcon = trend > 0 ? '↗' : trend < 0 ? '↘' : '→';
  
  return (
    <div className={`metric-card ${color}`}>
      <div className="metric-header">
        <div className="metric-icon">{icon}</div>
        <div className="metric-title">{title}</div>
      </div>
      <div className="metric-value">{value}</div>
      <div className={`metric-trend ${trendClass}`}>
        <span className="trend-icon">{trendIcon}</span>
        <span className="trend-value">{Math.abs(trend).toFixed(1)}%</span>
      </div>
    </div>
  );
};

const Chart = ({ data, type = 'line', title, height = 300 }) => {
  const [chartData, setChartData] = useState(null);
  
  useEffect(() => {
    // Simulate chart data processing
    if (data && Array.isArray(data)) {
      const processedData = data.map((item, index) => ({
        x: index,
        y: item.value || 0,
        label: item.label || `Point ${index + 1}`
      }));
      setChartData(processedData);
    }
  }, [data]);
  
  if (!chartData) {
    return <LoadingSpinner size="small" />;
  }
  
  return (
    <div className="chart-container">
      <h3 className="chart-title">{title}</h3>
      <div className={`chart ${type}`} style={{ height: `${height}px` }}>
        <svg viewBox="0 0 400 300" className="chart-svg">
          {type === 'line' && (
            <polyline
              fill="none"
              stroke="#667eea"
              strokeWidth="2"
              points={chartData.map(d => `${d.x * 50},${300 - d.y * 2}`).join(' ')}
            />
          )}
          {type === 'bar' && chartData.map((d, i) => (
            <rect
              key={i}
              x={i * 50}
              y={300 - d.y * 2}
              width="40"
              height={d.y * 2}
              fill="#667eea"
            />
          ))}
          {chartData.map((d, i) => (
            <circle
              key={i}
              cx={d.x * 50}
              cy={300 - d.y * 2}
              r="4"
              fill="#667eea"
            />
          ))}
        </svg>
      </div>
    </div>
  );
};

const DataTable = ({ data, columns, onRowClick, sortable = true }) => {
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  
  const handleSort = useCallback((key) => {
    if (!sortable) return;
    
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  }, [sortable]);
  
  const sortedData = useMemo(() => {
    if (!sortConfig.key) return data;
    
    return [...data].sort((a, b) => {
      const aVal = a[sortConfig.key];
      const bVal = b[sortConfig.key];
      
      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortConfig]);
  
  if (!data || data.length === 0) {
    return <div className="no-data">No data available</div>;
  }
  
  return (
    <div className="data-table">
      <table>
        <thead>
          <tr>
            {columns.map(column => (
              <th 
                key={column.key}
                className={sortable ? 'sortable' : ''}
                onClick={() => handleSort(column.key)}
              >
                {column.title}
                {sortConfig.key === column.key && (
                  <span className="sort-indicator">
                    {sortConfig.direction === 'asc' ? '↑' : '↓'}
                  </span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedData.map((row, index) => (
            <tr 
              key={index} 
              className={onRowClick ? 'clickable' : ''}
              onClick={() => onRowClick && onRowClick(row)}
            >
              {columns.map(column => (
                <td key={column.key}>
                  {column.render ? column.render(row[column.key], row) : row[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// Main dashboard components
const Dashboard = () => {
  const { user, theme, addNotification } = useApp();
  const [selectedTimeRange, setSelectedTimeRange] = useState('7d');
  
  // Mock API calls
  const { data: salesData, loading: salesLoading, error: salesError, refetch: refetchSales } = useApi('/api/sales');
  const { data: userData, loading: userLoading, error: userError } = useApi('/api/users');
  const { data: orderData, loading: orderLoading, error: orderError } = useApi('/api/orders');
  
  const salesMetrics = useMemo(() => calculateMetrics(salesData), [salesData]);
  const userMetrics = useMemo(() => calculateMetrics(userData), [userData]);
  const orderMetrics = useMemo(() => calculateMetrics(orderData), [orderData]);
  
  const handleTimeRangeChange = useCallback((range) => {
    setSelectedTimeRange(range);
    addNotification(`Time range changed to ${range}`, 'info');
  }, [addNotification]);
  
  const handleRefresh = useCallback(() => {
    refetchSales();
    addNotification('Data refreshed', 'success');
  }, [refetchSales, addNotification]);
  
  if (salesLoading || userLoading || orderLoading) {
    return <LoadingSpinner size="large" />;
  }
  
  if (salesError || userError || orderError) {
    return (
      <ErrorMessage 
        error={salesError || userError || orderError} 
        onRetry={handleRefresh}
      />
    );
  }
  
  return (
    <div className={`dashboard ${theme}`}>
      <header className="dashboard-header">
        <h1>Dashboard</h1>
        <div className="header-controls">
          <select 
            value={selectedTimeRange} 
            onChange={(e) => handleTimeRangeChange(e.target.value)}
            className="time-range-selector"
          >
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
            <option value="90d">Last 90 Days</option>
          </select>
          <button onClick={handleRefresh} className="refresh-button">
            Refresh
          </button>
        </div>
      </header>
      
      <div className="metrics-grid">
        <MetricCard
          title="Total Sales"
          value={formatCurrency(salesMetrics.total)}
          trend={salesMetrics.trend}
          icon="💰"
          color="green"
        />
        <MetricCard
          title="Active Users"
          value={userMetrics.total}
          trend={userMetrics.trend}
          icon="👥"
          color="blue"
        />
        <MetricCard
          title="Orders"
          value={orderMetrics.total}
          trend={orderMetrics.trend}
          icon="📦"
          color="purple"
        />
        <MetricCard
          title="Average Order"
          value={formatCurrency(orderMetrics.average)}
          trend={0}
          icon="📊"
          color="orange"
        />
      </div>
      
      <div className="charts-section">
        <Chart
          data={salesData}
          type="line"
          title="Sales Over Time"
          height={300}
        />
        <Chart
          data={userData}
          type="bar"
          title="User Activity"
          height={300}
        />
      </div>
      
      <div className="tables-section">
        <div className="table-container">
          <h3>Recent Orders</h3>
          <DataTable
            data={orderData || []}
            columns={[
              { key: 'id', title: 'Order ID' },
              { key: 'customer', title: 'Customer' },
              { key: 'amount', title: 'Amount', render: (value) => formatCurrency(value) },
              { key: 'status', title: 'Status' },
              { key: 'date', title: 'Date', render: (value) => formatDate(value) }
            ]}
            onRowClick={(row) => addNotification(`Selected order ${row.id}`, 'info')}
          />
        </div>
      </div>
    </div>
  );
};

const LoginForm = () => {
  const { login } = useApp();
  const [formData, setFormData] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Mock successful login
      login({
        id: '1',
        email: formData.email,
        name: 'John Doe',
        role: 'admin'
      });
    } catch (error) {
      console.error('Login failed:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleChange = (e) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };
  
  return (
    <div className="login-container">
      <form onSubmit={handleSubmit} className="login-form">
        <h2>Welcome Back</h2>
        <div className="form-group">
          <label htmlFor="email">Email</label>
          <input
            type="email"
            id="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            type="password"
            id="password"
            name="password"
            value={formData.password}
            onChange={handleChange}
            required
          />
        </div>
        <button type="submit" disabled={loading} className="login-button">
          {loading ? <LoadingSpinner size="small" /> : 'Sign In'}
        </button>
      </form>
    </div>
  );
};

const Header = () => {
  const { user, theme, toggleTheme, logout } = useApp();
  
  return (
    <header className="app-header">
      <div className="header-left">
        <h1>React Dashboard</h1>
      </div>
      <div className="header-right">
        <button onClick={toggleTheme} className="theme-toggle">
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
        {user && (
          <div className="user-menu">
            <span>Welcome, {user.name}</span>
            <button onClick={logout} className="logout-button">
              Logout
            </button>
          </div>
        )}
      </div>
    </header>
  );
};

// Main App component
const App = () => {
  const { user } = useApp();
  
  return (
    <div className="app">
      <Header />
      <main className="main-content">
        {user ? <Dashboard /> : <LoginForm />}
      </main>
      <NotificationContainer />
    </div>
  );
};

// App with provider wrapper
const AppWithProvider = () => (
  <AppProvider>
    <App />
  </AppProvider>
);

export default AppWithProvider;
