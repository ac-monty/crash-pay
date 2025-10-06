import React, { useCallback, useEffect, useRef, useState } from 'react';
import Icon from './Icon';

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
        } else {
            // If no saved messages, ensure welcome message is shown
            setMessages([
                {
                    role: 'assistant',
                    content: '👋 Welcome to <strong>Crash Pay</strong>!<br/>Ask me anything about your accounts or today\'s markets.',
                },
            ]);
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

    // Check for welcome message when chat opens (with delay to avoid race conditions)
    useEffect(() => {
        if (isOpen && messages.length === 0) {
            // Add a small delay to avoid race conditions with session ending flow
            const timer = setTimeout(() => {
                // Double-check conditions after delay
                const savedMessages = localStorage.getItem('bankingChatMessages');
                if (!savedMessages && messages.length === 0) {
                    setMessages([
                        {
                            role: 'assistant',
                            content: '👋 Welcome to <strong>Crash Pay</strong>!<br/>Ask me anything about your accounts or today\'s markets.',
                        },
                    ]);
                }
            }, 100); // 100ms delay to let session ending flow complete

            return () => clearTimeout(timer);
        }
    }, [isOpen, messages.length]);

    // Handle function calls triggered by the LLM (intelligent intent detection)
    const handleFunctionCall = (functionName, parameters) => {
        console.log('🔧 Function called:', functionName, parameters);

        switch (functionName) {
            case 'trigger_end_session':
                setShowSessionEndButton(true);
                break;
            // Canonical backend function names
            case 'get_account_balance':
                console.log('Balance check requested');
                // Future UX: display a balance widget here
                break;
            case 'transfer_funds':
                console.log('Money transfer requested:', parameters);
                // Future UX: display transfer form here
                break;
            case 'list_recipients':
                console.log('Recipient lookup requested:', parameters);
                // Future UX: display recipients dropdown or auto-fill account ID
                break;
            case 'get_user_profile':
                console.log('User profile requested:', parameters);
                // Future UX: display user profile information
                break;
            default:
                console.log('Unknown function:', functionName);
                break;
        }
    };

    const clearSession = async () => {
        try {
            if (sessionId) {
                const token = localStorage.getItem('bankingToken');
                console.log('🔐 Closing session with token:', token ? 'Token present' : 'No token');

                const headers = {
                    'Content-Type': 'application/json',
                    Authorization: token ? `Bearer ${token}` : undefined,
                };

                const response = await fetch(`/api/llm/threads/${sessionId}/close`, {
                    method: 'POST',
                    headers,
                    body: JSON.stringify({ sessionId }),
                });

                if (!response.ok) {
                    console.error('❌ Close session failed:', response.status, response.statusText);
                    const errorText = await response.text();
                    console.error('Error details:', errorText);
                } else {
                    console.log('✅ Session closed successfully');
                }
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

        // Auto-close the chat window after showing goodbye message
        setTimeout(() => {
            setIsOpen(false);
        }, 300); // 1 second delay to let user read the goodbye message
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
                const requestBody = { prompt: trimmed, user_id: 'frontend-client' };
                if (sessionId) {
                    requestBody.session_id = sessionId;
                }

                const headers = {
                    'Content-Type': 'application/json',
                    Authorization: localStorage.getItem('bankingToken')
                        ? `Bearer ${localStorage.getItem('bankingToken')}`
                        : undefined,
                };

                const url = `/api/llm/auth/chat`;

                console.log('--- Human Sending Request ---');
                console.log('URL:', url);
                // console.log('Headers:', JSON.stringify(headers, null, 2));
                console.log('Body:', JSON.stringify(requestBody, null, 2));
                console.log('--- Human Sending Request End ---');

                const res = await fetch(url, {
                    method: 'POST',
                    headers,
                    body: JSON.stringify(requestBody),
                });

                console.log('📡 Request sent. Status:', res.status);

                if (!res.ok) {
                    const errorText = await res.text();
                    console.error('❌ Received error response text:', errorText);
                    throw new Error(`Server responded ${res.status}`);
                }

                const data = await res.json();

                // New response shape
                const newSessionId = data.request_id || sessionId;

                if (data.function_calls && data.function_calls.length > 0) {
                    handleFunctionCall(data.function_calls[0].function, data.function_calls[0].arguments);
                }

                if (data.response) {
                    console.log('🤖 Agent response received:', data.response);
                    console.log('🤖 Full response data:', data);
                    setMessages((m) => [
                        ...m,
                        { role: 'assistant', content: data.response },
                    ]);
                }

                if (newSessionId && !sessionId) {
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
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                >
                    <Icon name="close" size="small" /> End Session
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
                style={{
                    background: 'rgba(30, 41, 59, 0.3)',
                    backdropFilter: 'blur(20px)',
                    border: '1px solid var(--glass-border)',
                    borderRadius: '50%',
                    boxShadow: 'var(--shadow-intense)',
                    color: 'var(--accent-gold)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'all 0.3s ease',
                    fontSize: '1.3rem'
                }}
                onMouseOver={(e) => {
                    e.target.style.transform = 'translateY(-3px)';
                    e.target.style.boxShadow = 'var(--shadow-intense), 0 0 30px rgba(245, 158, 11, 0.3)';
                }}
                onMouseOut={(e) => {
                    e.target.style.transform = 'translateY(0)';
                    e.target.style.boxShadow = 'var(--shadow-intense)';
                }}
            >
                <Icon name="chat" size="large" />
            </button>

            {/* Chat Window */}
            {isOpen && (
                <div className="chat-float-window">
                    <div className="chat-float-header">
                        <h4 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Icon name="chat" size="small" /> Banking Assistant
                        </h4>
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
                            {isSending ? <Icon name="wait" size="small" /> : <Icon name="enter" size="small" />}
                        </button>
                    </form>
                </div>
            )}
        </>
    );
}

export default FloatingChatAssistant; 