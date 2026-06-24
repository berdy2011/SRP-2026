import { useState, useEffect } from "react"
import "./Chat.css"

const API_URL = import.meta.env.VITE_API_URL
const SESSION_ID = "alice" // Наша рабочая сессия для PostgreSQL

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)

  // Шаг 8: Загружаем историю при открытии страницы
  useEffect(() => {
    async function loadHistory() {
      try {
        const res = await fetch(`${API_URL}/history/${SESSION_ID}`)
        if (res.ok) {
          const data = await res.json()
          // Подстраиваемся под формат бэка: data.messages
          setMessages(data.messages || [])
        }
      } catch (err) {
        console.error("Ошибка загрузки истории:", err)
      }
    }
    loadHistory()
  }, [])

  // Шаг 4: Функция отправки сообщения
  async function sendMessage() {
    if (!input.trim() || loading) return
    
    const userMsg = { role: 'user', content: input }
    // Сразу отображаем сообщение пользователя на экране
    setMessages(prev => [...prev, userMsg])
    setInput("")
    setLoading(true)
    
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMsg.content,
          session_id: SESSION_ID,
          lat: 51.16,       // Тестовые параметры для твоего бэкенда
          lon: 71.47,
          object_type: "Жилой комплекс"
        })
      })
      
      const data = await res.json()
      
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: data.reply }
      ])
    } catch (err) {
      console.error("Ошибка отправки:", err)
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: "⚠️ Ошибка сервера. Проверь, запущен ли бэкенд." }
      ])
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <span className="label">
              {msg.role === 'user' ? 'Вы' : 'Oylan'}
            </span>
            <p>{msg.content}</p>
          </div>
        ))}
        {loading && (
          <div className="message assistant loading">
            <p>Думает...</p>
          </div>
        )}
      </div>
      <div className="chat-input">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Напишите сообщение..."
          rows={3}
        />
        <button onClick={sendMessage} disabled={loading}>
          Отправить
        </button>
      </div>
    </div>
  )
}