import { api } from './api.js';

export class ResultsPage {
    constructor() {
        this.sessionsSelect = document.getElementById('sessions-list');
        this.resultsDisplay = document.getElementById('results-display');
        this.btnSaveJson = document.getElementById('btn-save-json');
        this.currentSessionId = null;

        this.init();
    }

    async init() {
        await this.loadSessions();
        this.bindEvents();
        // Загружаем последнюю сессию по умолчанию
        if (this.sessionsSelect.options.length > 0) {
            this.sessionsSelect.selectedIndex = 0;
            await this.loadSession(this.sessionsSelect.value);
        }
    }

    async loadSessions() {
        try {
            const sessions = await api.getSessions();
            this.sessionsSelect.innerHTML = '';
            sessions.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = `${s.id}: ${s.date}/${s.time}`;
                this.sessionsSelect.appendChild(opt);
            });
        } catch (err) {
            console.error('Ошибка загрузки сессий:', err);
        }
    }

    bindEvents() {
        this.sessionsSelect.addEventListener('change', () => {
            const id = this.sessionsSelect.value;
            if (id) this.loadSession(id);
        });

        this.btnSaveJson.addEventListener('click', () => {
            if (this.currentSessionId) this.exportSession();
        });
    }

    async loadSession(sessionId) {
        this.currentSessionId = sessionId;
        try {
            const data = await api.getSessionDetails(sessionId);
            this.renderResults(data);
        } catch (err) {
            console.error('Ошибка загрузки сессии:', err);
            this.resultsDisplay.innerHTML = `<p style="color:#e53e3e;">Ошибка загрузки данных: ${err.message}</p>`;
        }
    }

    renderResults(data) {
        // Параметры опроса
        const paramsHtml = `
            <h4>Параметры опроса</h4>
            <div class="param-grid">
                <span class="label">Температура:</span><span>${data.temperature}</span>
                <span class="label">Макс. токенов:</span><span>${data.maxTokens}</span>
                <span class="label">Системный промпт:</span><span>${data.systemPrompt || '(пусто)'}</span>
                <span class="label">Текст запроса:</span><span>${data.userQuery || '(пусто)'}</span>
            </div>
        `;

        // Ответы агентов
        let responsesHtml = '';
        if (data.responses && data.responses.length > 0) {
            data.responses.forEach(r => {
                const isError = r.status === 'error';
                responsesHtml += `
                    <div>
                        <span class="agent-name">Agent: ${r.agentName}</span>
                        <span class="response-text ${isError ? 'error-text' : ''}">
                            Response: ${r.text || r.error || '(пустой ответ)'}
                        </span>
                    </div>
                `;
            });
        } else {
            responsesHtml = '<p>Нет ответов от агентов.</p>';
        }

        this.resultsDisplay.innerHTML = `
            <div class="result-params">${paramsHtml}</div>
            <div class="result-responses">${responsesHtml}</div>
        `;
    }

    async exportSession() {
        try {
            const data = await api.exportSession(this.currentSessionId);
            // Скачивание файла
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${this.currentSessionId}.json`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            alert('Ошибка экспорта: ' + err.message);
        }
    }
}