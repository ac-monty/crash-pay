import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Link,
  useNavigate,
  useLocation,
} from 'react-router-dom';
import LoginPage from './components/LoginPage';
import UserDashboard from './components/UserDashboard';
import UserManagement from './components/UserManagement';
import AdminDashboard from './components/AdminDashboard';
import ChatDashboard from './components/ChatDashboard';
import AdminLogin from './components/AdminLogin';
import BankingLayout from './components/finance/BankingLayout';
import DashboardOverview from './components/finance/DashboardOverview';
import AccountsPanel from './components/finance/AccountsPanel';
import SavingsPanel from './components/finance/SavingsPanel';
import LoansPanel from './components/finance/LoansPanel';
import TradingPanel from './components/finance/TradingPanel';
import SharedLogo from './components/SharedLogo';
import Icon from './components/Icon';
import PageWrapper from './components/PageWrapper';
import PrivateRoute from './components/PrivateRoute';

/**
 * Comprehensive Banking Application with AI Chat Assistant
 *
 * Purpose: Security Research & AI Safety Learning Platform
 * Contains intentional vulnerabilities for educational purposes
 *
 * Features:
 * 1. React 18 with Hooks (useState, useEffect, useCallback)
 * 2. Real-time AI chat with function calling
 * 3. Account management & transaction history
 * 4. Admin dashboard with user management
 * 5. Intentional security issues for learning:
 *    - XSS through innerHTML usage
 *    - Missing CSRF protection
 *    - Weak session management
 *    - Insufficient input validation
 *
 *  Crash Pay • Banking Simulation with Admin Dashboard
 *  WARNING: For educational use only - contains intentional vulnerabilities
 */

const API_BASE = '/api';

/* ------------------------------------------------------------------ */
/* 🎨 Theme Context                                                   */
/* ------------------------------------------------------------------ */
const ThemeContext = React.createContext();

function ThemeProvider({ children }) {
  const [isDark, setIsDark] = useState(() => {
    // Load preference from localStorage or fallback to system preference
    const stored = localStorage.getItem('crashpay_theme');
    if (stored !== null) return stored === 'dark';
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  const toggleTheme = () => setIsDark(prev => {
    const next = !prev;
    localStorage.setItem('crashpay_theme', next ? 'dark' : 'light');
    return next;
  });

  // Apply theme class to <body> for full-page background
  React.useEffect(() => {
    document.body.classList.toggle('dark', isDark);
    document.body.classList.toggle('light', !isDark);
  }, [isDark]);

  return (
    <ThemeContext.Provider value={{ isDark, toggleTheme }}>
      <div className={`app ${isDark ? 'dark' : 'light'}`}>
        {children}
      </div>
    </ThemeContext.Provider>
  );
}

/* ------------------------------------------------------------------ */
/* 🏦 Banking Dashboard Component                                     */
/* ------------------------------------------------------------------ */
function BankingDashboard() {
  const [user, setUser] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem('bankingToken');
    const userData = localStorage.getItem('currentUser');

    if (!token || !userData) {
      navigate('/banking/login');
      return;
    }

    const parsedUser = JSON.parse(userData);
    setUser(parsedUser);
    fetchTransactions(parsedUser.id);
  }, [navigate]);

  const fetchTransactions = async (userId) => {
    try {
      const res = await fetch(`${API_BASE}/banking/transactions/${userId}`);
      const data = await res.json();
      if (data.ok) {
        setTransactions(data.transactions);
      }
    } catch (err) {
      console.error('Failed to fetch transactions:', err);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('bankingToken');
    localStorage.removeItem('currentUser');
    // Clear persisted chat data so a new user starts fresh
    localStorage.removeItem('bankingChatMessages');
    localStorage.removeItem('bankingChatSessionId');
    navigate('/banking/login');
    // Force full reload so chat component remounts with cleared state
    window.location.reload();
  };

  if (loading) {
    return <div className="banking-loading">Loading your account...</div>;
  }

  return (
    <div className="banking-dashboard">
      <nav className="banking-nav">
        <div className="bank-logo">
          <SharedLogo size="small" showText={false} />
          <span style={{ marginLeft: '0.5rem', fontSize: '1.2rem', fontWeight: '700', color: 'var(--accent-gold)' }}>
            CRASH PAY
          </span>
        </div>
        <div className="nav-user">
          <span>Welcome, {user?.name}</span>
          <button onClick={logout} className="logout-btn">Sign Out</button>
        </div>
      </nav>

      <div className="dashboard-content">
        <div className="account-summary">
          <div className="balance-card">
            <h2>Account Balance</h2>
            <div className="balance-amount">${user?.balance?.toLocaleString()}</div>
            <p>Available Balance</p>
          </div>

          <div className="account-info">
            <h3>Account Information</h3>
            <p><strong>Account Holder:</strong> {user?.name}</p>
            <p><strong>SSN:</strong> {user?.ssn}</p>
            <p><strong>Account ID:</strong> {user?.id?.substring(0, 8)}...</p>
          </div>
        </div>

        <div className="transactions-section">
          <h2>Recent Transactions</h2>
          <div className="transactions-table">
            {transactions.length === 0 ? (
              <div className="no-transactions">
                <p>No transactions found</p>
                <p>Contact admin to generate sample transactions</p>
              </div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Description</th>
                    <th>Amount</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((tx) => (
                    <tr key={tx.id}>
                      <td>{new Date(tx.createdAt).toLocaleDateString()}</td>
                      <td>{tx.description}</td>
                      <td className={tx.amount >= 0 ? 'amount-positive' : 'amount-negative'}>
                        {tx.amount >= 0 ? '+' : ''}${tx.amount}
                      </td>
                      <td>
                        <span className={`status ${tx.status.toLowerCase()}`}>
                          {tx.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Floating Chat Assistant */}
      <FloatingChatAssistant />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 🤖 Floating Chat Assistant Component                              */
/* ------------------------------------------------------------------ */
function FloatingChatAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: '👋 Welcome to <strong>Crash Pay</strong>!<br/>Ask me anything about your accounts or today\'s markets.',
    },
  ]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [sessionId, setSessionId] = useState(
    localStorage.getItem('bankingChatSessionId') || null
  );
  const [showSessionEndButton, setShowSessionEndButton] = useState(false);
  const bottomRef = useRef(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load messages from localStorage on mount
  useEffect(() => {
    const savedMessages = localStorage.getItem('bankingChatMessages');
    if (savedMessages) {
      try {
        setMessages(JSON.parse(savedMessages));
      } catch (err) {
        console.error('Failed to load saved messages:', err);
      }
    }
  }, []);

  // Save messages to localStorage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem('bankingChatMessages', JSON.stringify(messages));
    }
  }, [messages]);

  // Save session ID to localStorage whenever it changes
  useEffect(() => {
    if (sessionId) {
      localStorage.setItem('bankingChatSessionId', sessionId);
    }
  }, [sessionId]);

  // Handle function calls triggered by the LLM (intelligent intent detection)
  const handleFunctionCall = (functionName, parameters) => {
    console.log('🔧 Function called:', functionName, parameters);

    switch (functionName) {
      case 'trigger_end_session':
        setShowSessionEndButton(true);
        break;
      case 'check_account_balance':
        // Future: Show balance widget or redirect to balance view
        console.log('Balance check requested');
        break;
      case 'transfer_money':
        // Future: Show transfer form or redirect to transfer page
        console.log('Money transfer requested:', parameters);
        break;
      default:
        console.log('Unknown function:', functionName);
    }
  };

  const clearSession = async () => {
    try {
      if (sessionId) {
        await fetch(`${API_BASE}/chat/close`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sessionId }),
        });
      }
    } catch (err) {
      console.error('Failed to close session:', err);
    } finally {
      // Clear frontend state
      setMessages([]);
      setSessionId(null);
      setShowSessionEndButton(false);
      localStorage.removeItem('bankingChatSessionId');
      localStorage.removeItem('bankingChatMessages');
    }
  };

  // Just close the chat window without clearing session
  const closeChat = () => {
    setIsOpen(false);
  };

  // Handle ending session when user confirms
  const handleEndSession = () => {
    clearSession();
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: 'Thank you for using our banking assistant. Your session has been ended. Have a great day! 👋'
    }]);
    setShowSessionEndButton(false);
  };

  const sendMessage = useCallback(
    async (e) => {
      e?.preventDefault();
      const trimmed = input.trim();
      if (!trimmed || isSending) return;

      console.log('🚀 Sending message:', trimmed);
      console.log('📝 Current sessionId:', sessionId);
      console.log('💬 Current messages count:', messages.length);

      setMessages((m) => [...m, { role: 'user', content: trimmed }]);
      setInput('');
      setIsSending(true);

      try {
        const requestBody = { message: trimmed };
        if (sessionId) {
          requestBody.sessionId = sessionId;
          console.log('✅ Including sessionId in request:', sessionId);
        } else {
          console.log('⚠️ No sessionId - will create new session');
        }

        const res = await fetch(`${API_BASE}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: localStorage.getItem('bankingToken')
              ? `Bearer ${localStorage.getItem('bankingToken')}`
              : undefined,
          },
          body: JSON.stringify(requestBody),
        });

        console.log('📡 Request sent. Status:', res.status);

        if (!res.ok) {
          throw new Error(`Server responded ${res.status}`);
        }

        // Get the plain text response
        const assistantMessage = await res.text();

        // Extract session info from headers
        const newSessionId = res.headers.get('X-Session-Id');
        const messageCount = res.headers.get('X-Message-Count');
        const userId = res.headers.get('X-User-Id');

        console.log('📩 Response received:');
        console.log('  - New sessionId:', newSessionId);
        console.log('  - Message count:', messageCount);
        console.log('  - User ID:', userId);
        console.log('  - Response:', assistantMessage.substring(0, 100) + '...');

        // Check if the response contains function calls (JSON format)
        try {
          const parsed = JSON.parse(assistantMessage);

          // Check for function calls in the LLM response
          if (parsed.function_call) {
            console.log('🔧 LLM Function call detected:', parsed.function_call);
            handleFunctionCall(parsed.function_call.name, parsed.function_call.arguments);

            // Use the content from the response as the display message
            const displayMessage = parsed.token || parsed.content || `I'll help you with that.`;
            setMessages((m) => [
              ...m,
              { role: 'assistant', content: displayMessage },
            ]);
          } else {
            // Regular text response - check for token or content field
            const displayMessage = parsed.token || parsed.content || assistantMessage;
            setMessages((m) => [
              ...m,
              { role: 'assistant', content: displayMessage },
            ]);
          }
        } catch (parseError) {
          // Not JSON, treat as plain text response
          setMessages((m) => [
            ...m,
            { role: 'assistant', content: assistantMessage },
          ]);
        }

        // Store session ID for future requests
        if (newSessionId) {
          setSessionId(newSessionId);
          console.log('💾 Updated sessionId state to:', newSessionId);
        }
      } catch (err) {
        console.error('❌ Error in sendMessage:', err);
        setMessages((m) => [
          ...m,
          {
            role: 'assistant',
            content: '⚠️ Sorry, something went wrong while contacting the server.',
          },
        ]);
      } finally {
        setIsSending(false);
      }
    },
    [input, isSending, sessionId]
  );

  // Render action buttons based on context
  const renderActionButtons = () => {
    const buttons = [];

    if (showSessionEndButton) {
      buttons.push(
        <button
          key="end-session"
          onClick={handleEndSession}
          className="chat-action-button end-session"
          title="End this conversation"
        >
          End Session 🚪
        </button>
      );
    }

    // Future expandable buttons can be added here
    // Examples:
    // - Transfer money button
    // - Check balance button
    // - Contact support button
    // - etc.

    return buttons.length > 0 ? (
      <div className="chat-action-buttons">
        {buttons}
      </div>
    ) : null;
  };

  return (
    <>
      {/* Chat Button */}
      <button
        className="chat-float-button"
        onClick={() => setIsOpen(!isOpen)}
        title="Banking Assistant"
      >
        🤖
      </button>

      {/* Chat Window */}
      {isOpen && (
        <div className="chat-float-window">
          <div className="chat-float-header">
            <h4>🤖 Banking Assistant</h4>
            <div className="chat-float-controls">
              <button onClick={closeChat} className="chat-close">×</button>
            </div>
          </div>

          <div className="chat-float-messages">
            {messages.map((msg, idx) => (
              <div key={idx} className={`chat-float-message ${msg.role}`}>
                <span dangerouslySetInnerHTML={{ __html: msg.content }} />
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Action buttons (expandable for future features) */}
          {renderActionButtons()}

          <form onSubmit={sendMessage} className="chat-float-input">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about your account..."
              autoComplete="off"
            />
            <button type="submit" disabled={isSending}>
              {isSending ? '⏳' : '📤'}
            </button>
          </form>
        </div>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* 🏠 Navigation Component                                            */
/* ------------------------------------------------------------------ */
function Navigation() {
  const { isDark, toggleTheme } = React.useContext(ThemeContext);
  const location = useLocation();

  // Don't show navigation on banking pages (they have their own nav)
  if (location.pathname.includes('/banking/')) {
    return null;
  }

  return (
    <nav className="crash-pay-navbar">
      <div className="crash-pay-nav-brand">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <SharedLogo size="small" showText={false} />
          <h1>CRASH PAY Admin</h1>
        </div>
      </div>
      <div className="crash-pay-nav-links">
        <Link
          to="/banking/login"
          className={`crash-pay-nav-link ${location.pathname.includes('/banking') ? 'active' : ''}`}
        >
          <Icon name="bank" size="default" />
          Banking
        </Link>
        <Link
          to="/admin/dashboard"
          className={`crash-pay-nav-link ${location.pathname.includes('/admin/dashboard') ? 'active' : ''}`}
        >
          <Icon name="dashboard" size="default" />
          Dashboard
        </Link>
        <Link
          to="/admin/users"
          className={`crash-pay-nav-link ${location.pathname === '/admin/users' ? 'active' : ''}`}
        >
          <Icon name="users" size="default" />
          Users
        </Link>
        <Link
          to="/chat"
          className={`crash-pay-nav-link ${location.pathname === '/chat' ? 'active' : ''}`}
        >
          <Icon name="chat" size="default" />
          Chat
        </Link>
        <button onClick={toggleTheme} className="crash-pay-theme-toggle">
          <Icon name={isDark ? 'lightTheme' : 'darkTheme'} size="default" />
        </button>
      </div>
    </nav>
  );
}

/* ------------------------------------------------------------------ */
/* 🏠 Home Component                                                  */
/* ------------------------------------------------------------------ */
function Home() {
  const navigate = useNavigate();

  useEffect(() => {
    // Redirect to banking login by default (main user interface)
    const timeout = setTimeout(() => navigate('/banking/login'), 1000);
    return () => clearTimeout(timeout);
  }, [navigate]);

  return (
    <div className="home">
      <h1>🏦 Crash Pay</h1>
      <p>
        Banking simulation with AI assistant
      </p>
      <p>Redirecting to banking portal...</p>
      <div className="home-links">
        <Link to="/banking/login" className="home-link">🏦 Banking Portal</Link>
        <Link to="/admin/login" className="home-link">📊 Admin Center</Link>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 🌐 App Router                                                      */
/* ------------------------------------------------------------------ */
export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <div className="app-layout">
          <Navigation />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/admin/dashboard" element={<AdminDashboard />} />
              <Route path="/admin/users" element={<UserManagement />} />
              <Route path="/admin/login" element={<AdminLogin />} />
              <Route path="/chat" element={<ChatDashboard />} />
              <Route path="/banking/login" element={<LoginPage />} />
              <Route element={<PrivateRoute />}>
                <Route path="/banking/*" element={<BankingLayout />}>
                  <Route path="dashboard" element={<DashboardOverview />} />
                  <Route path="accounts" element={<AccountsPanel />} />
                  <Route path="investing" element={<SavingsPanel />} />
                  <Route path="loans" element={<LoansPanel />} />
                  <Route path="trading" element={<TradingPanel />} />
                </Route>
              </Route>
              <Route
                path="*"
                element={
                  <div className="not-found">
                    <h2>404 – Not Found</h2>
                    <Link to="/admin/dashboard">Return to Dashboard</Link>
                  </div>
                }
              />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </ThemeProvider>
  );
}