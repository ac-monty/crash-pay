import React, { useState, useEffect, useRef, useCallback } from 'react';
import './SharedStyles.css';
import PageWrapper from './PageWrapper';
import Icon from './Icon';
import { getAdminToken } from '../utils/auth.js';

const ChatDashboard = () => {
    const [messages, setMessages] = useState([
        {
            role: 'assistant',
            content: '👋 Welcome to <strong>Crash Pay</strong>!<br/>Ask me anything about your accounts or today\'s markets.',
        },
    ]);
    const [input, setInput] = useState('');
    const [isSending, setIsSending] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const bottomRef = useRef(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleFunctionCall = (functionName, parameters) => {
        console.log('🔧 Function call received:', functionName, parameters);
        // Handle specific function calls here if needed
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
                const requestBody = { prompt: trimmed, stream: false };
                if (sessionId) {
                    requestBody.session_id = sessionId;
                    console.log('✅ Including session_id in request:', sessionId);
                } else {
                    console.log('⚠️ No session_id - starting new session');
                }

                const adminToken = getAdminToken();
                const bankingToken = localStorage.getItem('bankingToken');
                const bearer = adminToken || bankingToken;

                const res = await fetch(`/api/llm/chat`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        Authorization: bearer ? `Bearer ${bearer}` : undefined,
                    },
                    body: JSON.stringify(requestBody),
                });

                console.log('📡 Request sent. Status:', res.status);

                if (!res.ok) {
                    throw new Error(`Server responded ${res.status}`);
                }

                // Expect JSON response when stream=false
                let assistantMessage = '';
                let jsonData = null;
                try {
                    jsonData = await res.json();
                    assistantMessage = jsonData.response || '';
                } catch (_e) {
                    // Fallback: try plain text
                    assistantMessage = await res.text();
                }

                // Extract session info from headers
                const newSessionId = res.headers.get('X-Session-Id');
                const messageCount = res.headers.get('X-Message-Count');
                const userId = res.headers.get('X-User-Id');

                console.log('📩 Response received:');
                console.log('  - New sessionId:', newSessionId);
                console.log('  - Message count:', messageCount);
                console.log('  - User ID:', userId);
                console.log('  - Response:', assistantMessage.substring(0, 100) + '...');

                // Prefer structured JSON when available
                if (jsonData) {
                    // Handle possible function call envelope (future-proof)
                    if (jsonData.function_call) {
                        console.log('🔧 LLM Function call detected:', jsonData.function_call);
                        handleFunctionCall(jsonData.function_call.name, jsonData.function_call.arguments);
                        const displayMessage = jsonData.token || jsonData.content || jsonData.response || `I'll help you with that.`;
                        setMessages((m) => [...m, { role: 'assistant', content: displayMessage }]);
                    } else {
                        const displayMessage = jsonData.response || jsonData.token || jsonData.content || assistantMessage;
                        setMessages((m) => [...m, { role: 'assistant', content: displayMessage }]);
                    }
                } else {
                    // Fallback to plain text
                    setMessages((m) => [...m, { role: 'assistant', content: assistantMessage }]);
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

    return (
        <PageWrapper showBackground={true}>
            <div className="crash-pay-main-content">
                <div className="crash-pay-chat-dashboard">
                    {/* Chat Header */}
                    <div className="crash-pay-dashboard-header crash-pay-rotating-border">
                        <h1 className="crash-pay-dashboard-title">
                            <Icon name="chat" size="large" />
                            AI Chat Testing Dashboard
                        </h1>
                        <div className="crash-pay-dashboard-stats">
                            <div className="crash-pay-quick-stat">
                                <div className="crash-pay-quick-stat-value">{messages.length}</div>
                                <div className="crash-pay-quick-stat-label">Messages</div>
                            </div>
                            {sessionId && (
                                <div className="crash-pay-quick-stat">
                                    <div className="crash-pay-quick-stat-value">{sessionId.substring(0, 8)}...</div>
                                    <div className="crash-pay-quick-stat-label">Session ID</div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Chat Container */}
                    <div className="crash-pay-chat-container">
                        {/* Messages Area */}
                        <div className="crash-pay-chat-messages">
                            {messages.map((msg, idx) => (
                                <div
                                    key={idx}
                                    className={`crash-pay-chat-message ${msg.role}`}
                                >
                                    <div className="crash-pay-message-content">
                                        <span
                                            dangerouslySetInnerHTML={{ __html: msg.content }}
                                            data-role={msg.role}
                                        />
                                    </div>
                                </div>
                            ))}
                            <div ref={bottomRef} />
                        </div>

                        {/* Input Form */}
                        <form onSubmit={sendMessage} className="crash-pay-chat-input">
                            <div className="crash-pay-input-group">
                                <input
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    placeholder="Type a message to test the AI assistant..."
                                    className="crash-pay-input-field"
                                    autoComplete="off"
                                />
                                <button
                                    type="submit"
                                    disabled={isSending}
                                    className="crash-pay-chat-send-btn"
                                >
                                    {isSending ? (
                                        <>
                                            <div className="crash-pay-loading"></div>
                                            Sending...
                                        </>
                                    ) : (
                                        <>
                                            <Icon name="forward" size="default" />
                                            Send
                                        </>
                                    )}
                                </button>
                            </div>
                        </form>

                        {/* Session info for debugging */}
                        {sessionId && (
                            <div className="crash-pay-chat-debug">
                                <span>Session: {sessionId.substring(0, 8)}...</span>
                                <span>Messages: {messages.length}</span>
                                <span>Status: {isSending ? 'Sending' : 'Ready'}</span>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </PageWrapper>
    );
};

export default ChatDashboard; 