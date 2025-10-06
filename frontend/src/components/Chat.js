import React, { useState, useEffect, useRef } from 'react';

/**
 * Chat component – deliberately renders assistant messages with
 * `dangerouslySetInnerHTML` to expose OWASP-LLM-02 (insecure output handling).
 *
 * DO NOT copy this pattern into production code.  It exists ONLY so that
 * security researchers can probe XSS‐style issues triggered by LLM output.
 */
const Chat = () => {
  const [messages, setMessages] = useState([
    {
      id: 'sys-0',
      role: 'system',
      content:
        'Welcome to Crash Pay.\nType a prompt and the model will respond.',
    },
  ]);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const bottomRef = useRef(null);

  /* Auto-scroll to bottom whenever messages change */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  /* Fetch helper */
  const sendPrompt = async (prompt) => {
    try {
      setPending(true);

      const res = await fetch(
        `/api/llm/chat`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            // Intentionally missing CSRF or auth headers – authentication
            // happens elsewhere; this surface is left weak on purpose.
          },
          body: JSON.stringify({ prompt }),
        }
      );

      if (!res.ok) {
        throw new Error(`Server responded ${res.status}`);
      }

      const data = await res.json();
      // New response shape: { response: 'text', function_calls: [...] }
      if (data && data.response) {
        setMessages((prev) => [
          ...prev,
          { id: `assistant-${Date.now()}`, role: 'assistant', content: data.response },
        ]);
      }
    } catch (err) {
      console.error('Chat error:', err);
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'error',
          content:
            '⚠️ Something went wrong contacting the LLM service. Please try again.',
        },
      ]);
    } finally {
      setPending(false);
    }
  };

  /* Form submit */
  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;

    const userMsg = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    sendPrompt(trimmed);
  };

  /* Render helpers */
  const renderMessage = (msg) => {
    const baseClasses =
      'px-4 py-2 my-1 rounded-md max-w-xl text-sm whitespace-pre-wrap';

    switch (msg.role) {
      case 'assistant':
        return (
          <div
            key={msg.id}
            className={`${baseClasses} bg-gray-100 text-gray-900 self-start`}
            /* -----------------------------------------------------------
             *  XSS WARNING:
             *  ----------------------------------------------------------
             *  We are deliberately using `dangerouslySetInnerHTML` to
             *  reflect LLM output straight into the DOM.  This is the
             *  textbook insecure pattern that OWASP-LLM-02 focuses on.
             *  ---------------------------------------------------------- */
            dangerouslySetInnerHTML={{ __html: msg.content }}
          />
        );

      case 'user':
        return (
          <div
            key={msg.id}
            className={`${baseClasses} bg-blue-600 text-white self-end`}
          >
            {msg.content}
          </div>
        );

      case 'error':
        return (
          <div
            key={msg.id}
            className={`${baseClasses} bg-red-100 text-red-700 self-center`}
          >
            {msg.content}
          </div>
        );

      default:
        // system / other roles
        return (
          <div
            key={msg.id}
            className={`${baseClasses} bg-yellow-50 text-gray-700 self-center`}
          >
            {msg.content}
          </div>
        );
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col">
        {messages.map(renderMessage)}
        <div ref={bottomRef} />
      </div>

      {/* Input form */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-gray-200 p-4 flex gap-2"
      >
        <input
          type="text"
          className="flex-1 border rounded-md p-2 text-sm"
          placeholder={
            pending ? 'Awaiting response…' : 'Ask the Crash Pay assistant…'
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={pending}
          autoFocus
        />
        <button
          type="submit"
          className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm disabled:opacity-60"
          disabled={pending || !input.trim()}
        >
          Send
        </button>
      </form>
    </div>
  );
};

export default Chat;