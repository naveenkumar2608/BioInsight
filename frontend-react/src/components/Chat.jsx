import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, LogOut, User, Loader2, MessageSquare, Plus, Menu } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';

export default function Chat({ token, onLogout }) {
    const { sessionId } = useParams();
    const navigate = useNavigate();
    const [sessions, setSessions] = useState([]);
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const chatEndRef = useRef(null);

    // Initial welcome message
    const welcomeMsg = {
        text: "Hello! I'm your BioInsight Assistant. You can ask me about any drug and its target interaction in natural language.\n\nTry something like: **\"How does Imatinib interact with BCR-ABL1?\"**",
        isUser: false
    };

    useEffect(() => {
        fetchSessions();
    }, []);

    useEffect(() => {
        if (sessionId && sessionId !== currentSessionId) {
            loadSession(sessionId);
        } else if (!sessionId && currentSessionId) {
            startNewChat();
        }
    }, [sessionId]);

    const fetchSessions = async () => {
        try {
            const res = await axios.get('/api/sessions', {
                headers: { Authorization: `Bearer ${token}` }
            });
            setSessions(res.data);
        } catch (err) {
            console.error("Failed to fetch sessions", err);
        }
    };

    const loadSession = async (sid) => {
        // Prevent redundant loading if already on this session
        if (currentSessionId === sid && messages.length > 1) return;

        setLoading(true);
        try {
            const res = await axios.get(`/api/sessions/${sid}`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setMessages(res.data);
            setCurrentSessionId(sid);
        } catch (err) {
            console.error("Failed to load messages", err);
            if (err.response?.status === 404) {
                navigate('/chat');
            }
        } finally {
            setLoading(false);
        }
    };

    const startNewChat = () => {
        setCurrentSessionId(null);
        setMessages([welcomeMsg]);
        if (window.location.pathname !== '/chat') {
            navigate('/chat');
        }
    };

    const scrollToBottom = () => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async (e) => {
        e?.preventDefault();
        if (!input.trim() || loading) return;

        const userMsg = input.trim();
        const newMsg = { text: userMsg, isUser: true };
        setMessages(prev => [...prev.filter(m => m.text !== welcomeMsg.text || prev.length > 1), newMsg]);
        setInput('');
        setLoading(true);

        try {
            const response = await axios.post('/api/chat',
                { message: userMsg, session_id: currentSessionId },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            const { reply, data, session_id } = response.data;
            const assistantMsg = { text: reply, isUser: false, data };

            // If it was a new session, update UI and sync URL
            if (!currentSessionId) {
                setCurrentSessionId(session_id);
                fetchSessions();
                // Set messages BEFORE navigating to prevent race condition with loadSession
                setMessages(prev => [...prev, assistantMsg]);
                navigate(`/c/${session_id}`, { replace: true });
            } else {
                setMessages(prev => [...prev, assistantMsg]);
            }
        } catch (err) {
            setMessages(prev => [...prev, {
                text: "I encountered an error. Please make sure you're logged in.",
                isUser: false
            }]);
        } finally {
            setLoading(false);
        }
    };

    const formatText = (text) => {
        if (!text) return "";
        return text.split('\n').map((line, i) => (
            <span key={i}>
                {line.split(/\*\*(.*?)\*\*/g).map((part, j) =>
                    j % 2 === 1 ? <b key={j}>{part}</b> : part
                )}
                <br />
            </span>
        ));
    };

    return (
        <div className="app-layout" style={{ flexDirection: 'row' }}>
            {/* Sidebar */}
            <aside className={`sidebar glass ${sidebarOpen ? 'open' : 'closed'}`}>
                <div className="sidebar-header">
                    <button className="new-chat-btn" onClick={() => navigate('/chat')}>
                        <Plus size={18} />
                        <span>New Chat</span>
                    </button>
                </div>

                <div className="sessions-list">
                    {sessions.map(s => (
                        <div
                            key={s.id}
                            className={`session-item ${currentSessionId === s.id ? 'active' : ''}`}
                            onClick={() => navigate(`/c/${s.id}`)}
                        >
                            <MessageSquare size={16} />
                            <span className="session-title">{s.title}</span>
                        </div>
                    ))}
                </div>

                <div className="sidebar-footer">
                    <div className="user-profile">
                        <User size={20} />
                        <span>My Account</span>
                    </div>
                    <button className="logout-btn" onClick={onLogout}>
                        <LogOut size={16} />
                        Logout
                    </button>
                </div>
            </aside>

            {/* Main Chat Area */}
            <div className="chat-area-container">
                <nav className="navbar glass">
                    <button className="menu-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
                        <Menu size={24} />
                    </button>
                    <div className="logo">BioInsight AI</div>
                    <div className="nav-actions">
                        <span className="session-status">{currentSessionId ? 'History Mode' : 'New Session'}</span>
                    </div>
                </nav>

                <main className="chat-main">
                    <div className="messages-container">
                        {(messages.length === 0 ? [welcomeMsg] : messages).map((msg, i) => (
                            <div key={i} className={`message ${msg.is_user || msg.isUser ? 'user-message' : 'assistant-message'}`}>
                                <div className="msg-content">{formatText(msg.text)}</div>

                                {msg.data && (
                                    <div className="analysis-card">
                                        <div className="card-header">
                                            <h4 style={{ margin: 0 }}>Analysis: {msg.data.drug} → {msg.data.target}</h4>
                                            <span className={`confidence-badge ${msg.data.confidence_score === 0 ? 'error' : ''}`}>
                                                {(msg.data.confidence_score * 100).toFixed(0)}% Confidence
                                            </span>
                                        </div>
                                        <div className="card-body">
                                            <div className="explanation-text">
                                                {formatText(msg.data.explanation)}
                                            </div>
                                            <div className="source-tags">
                                                {msg.data.evidence_sources?.map((s, si) => (
                                                    <span key={si} className="tag">{s}</span>
                                                ))}
                                                {msg.data.raw_evidence_count > 0 && (
                                                    <span className="tag">+ {msg.data.raw_evidence_count} evidence items</span>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}
                        <div ref={chatEndRef} />
                    </div>

                    <div className="input-area">
                        <form className="chat-input-wrapper glass" onSubmit={handleSend}>
                            <input
                                type="text"
                                placeholder="Describe the interaction you're curious about..."
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                disabled={loading}
                            />
                            <button type="submit" className="send-btn" disabled={loading}>
                                {loading ? <Loader2 className="animate-spin" /> : <Send size={20} />}
                            </button>
                        </form>
                        <p className="input-disclaimer">BioInsight AI can make mistakes. Check important info.</p>
                    </div>
                </main>
            </div>
        </div>
    );
}
