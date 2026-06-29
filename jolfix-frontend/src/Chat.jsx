import React, { useState, useEffect, useRef } from 'react';
import './Chat.css';

export default function Chat() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef(null);

    // Ссылка на адрес твоего бэкенда FastAPI
    const API_URL = 'http://127.0.0.1:8000';
    const SESSION_ID = 'default';

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    // Подгружаем историю переписки из PostgreSQL при загрузке страницы
    useEffect(() => {
        fetch(`${API_URL}/history/${SESSION_ID}`)
            .then((res) => res.json())
            .then((data) => {
                if (data && Array.isArray(data.messages)) {
                    // Переводим формат БД [{role, content}] под нужды React
                    setMessages(data.messages);
                }
            })
            .catch((err) => console.error("Ошибка загрузки истории:", err));
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Функция отправки обычных сообщений
    const sendMessage = async (e) => {
        e.preventDefault();
        if (!input.trim() || loading) return;

        const userText = input.trim();
        setInput('');
        
        // Временные координаты Астаны для работы эндпоинта /chat
        const payload = {
            lat: 51.16,
            lon: 71.47,
            object_type: "Жилой комплекс",
            message: userText,
            session_id: SESSION_ID
        };

        setMessages((prev) => [...prev, { role: 'user', content: userText }]);
        setLoading(true);

        try {
            const response = await fetch(`${API_URL}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            const data = await response.json();
            if (response.ok && data.response) {
                setMessages((prev) => [...prev, { role: 'assistant', content: data.response }]);
            } else {
                setMessages((prev) => [...prev, { role: 'assistant', content: '⚠️ Ошибка сервера при генерации ответа.' }]);
            }
        } catch (error) {
            console.error(error);
            setMessages((prev) => [...prev, { role: 'assistant', content: '❌ Ошибка: бэкенд недоступен.' }]);
        } finally {
            setLoading(false);
        }
    };

    // 🔥 ФУНКЦИЯ ОЧИСТКИ: Вызывает роут DELETE /api/chat/clear на бэкенде
    const handleClearChat = async () => {
        if (window.confirm("Вы уверены, что хотите полностью стереть историю в Postgres и сбросить контекст?")) {
            try {
                const response = await fetch(`${API_URL}/api/chat/clear`, {
                    method: 'DELETE',
                });

                if (response.ok) {
                    setMessages([]); // Мгновенно стираем сообщения с экрана
                    alert("История успешно очищена!");
                } else {
                    alert("Не удалось очистить базу данных на сервере.");
                }
            } catch (error) {
                console.error("Ошибка сети при очистке:", error);
                alert("Ошибка соединения с бэкендом.");
            }
        }
    };

    return (
        <div className="chat-container">
            {/* Хедер с кнопкой очистки памяти */}
            <div className="chat-header">
                <div className="header-info">
                    <span className="status-dot"></span>
                    <h2>Oylan AI Assistant</h2>
                </div>
                <button onClick={handleClearChat} className="clear-chat-btn">
                    🗑️ Очистить память
                </button>
            </div>

            {/* Окно сообщений */}
            <div className="chat-messages">
                {messages.length === 0 && (
                    <div className="empty-chat">
                        🤖 Контекст пуст. Задайте любой новый вопрос!
                    </div>
                )}
                {messages.map((msg, index) => (
                    <div key={index} className={`message-wrapper ${msg.role}`}>
                        <div className="message-sender">
                            {msg.role === 'user' ? 'Вы' : 'Oylan'}
                        </div>
                        <div className="message-content">
                            {msg.content}
                        </div>
                    </div>
                ))}
                {loading && (
                    <div className="message-wrapper assistant loading">
                        <div className="message-content">Oylan думает...</div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Форма отправки */}
            <form onSubmit={sendMessage} className="chat-input-form">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Введите ваше сообщение..."
                    disabled={loading}
                />
                <button type="submit" disabled={loading || !input.trim()}>
                    Отправить
                </button>
            </form>
        </div>
    );
}