// Базовый URL для запросов к бэкенду
const API_BASE = '/api';

export const api = {
    // Получение конфигурации (агенты, значения по умолчанию)
    async getConfig() {
        const res = await fetch(`${API_BASE}/config`);
        if (!res.ok) throw new Error('Failed to load config');
        return res.json();
    },

    // Сохранение настроек (температура, токены, промпты)
    async saveSettings(data) {
        const res = await fetch(`${API_BASE}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error('Failed to save settings');
        return res.json();
    },

    // Запуск опроса
    async startPolling(data) {
        const res = await fetch(`${API_BASE}/poll`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error('Failed to start polling');
        return res.json();
    },

    // Получение списка сессий для вкладки результатов
    async getSessions() {
        const res = await fetch(`${API_BASE}/sessions`);
        if (!res.ok) throw new Error('Failed to load sessions');
        return res.json();
    },

    // Получение деталей конкретной сессии
    async getSessionDetails(sessionId) {
        const res = await fetch(`${API_BASE}/session/${sessionId}`);
        if (!res.ok) throw new Error('Failed to load session details');
        return res.json();
    },

    // Экспорт сессии в JSON
    async exportSession(sessionId) {
        const res = await fetch(`${API_BASE}/export/${sessionId}`);
        if (!res.ok) throw new Error('Failed to export session');
        return res.json();
    }
};