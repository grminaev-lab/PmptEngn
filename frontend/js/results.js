import { api } from './api.js';

export class ResultsPage {
    constructor() {
        this.sessionsSelect = document.getElementById('sessions-list');
        this.resultsDisplay = document.getElementById('results-display');
        this.btnSaveJson = document.getElementById('btn-save-json');
        this.currentSessionId = null;
        this.isInitializing = false;  // Флаг для подавления ложных событий
        this.isInitialized = false;

        this.init();
    }

    async init() {
        console.log('[ResultsPage] init() started');
        this.isInitializing = true;
        
        await this.loadSessions();
        this.bindEvents();
        
        // Загружаем последнюю сессию по умолчанию
        if (this.sessionsSelect.options.length > 0) {
            this.sessionsSelect.selectedIndex = 0;
            const id = this.sessionsSelect.value;
            console.log('[ResultsPage] init() loading session:', id);
            await this.loadSession(id);
        }
        
        this.isInitializing = false;
        this.isInitialized = true;
        console.log('[ResultsPage] init() completed');
    }

    async loadSessions() {
        console.log('[ResultsPage] loadSessions() started');
        try {
            const sessions = await api.getSessions();
            console.log('[ResultsPage] loadSessions() got', sessions.length, 'sessions');
            this.sessionsSelect.innerHTML = '';
            sessions.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = `${s.id}: ${s.date}/${s.time}`;
                this.sessionsSelect.appendChild(opt);
            });
            return sessions;
        } catch (err) {
            console.error('[ResultsPage] loadSessions() error:', err);
            this.sessionsSelect.innerHTML = '<option value="">Ошибка загрузки сессий</option>';
            return [];
        }
    }

    bindEvents() {
        console.log('[ResultsPage] bindEvents() called');
        this.sessionsSelect.addEventListener('change', () => {
            // Игнорируем событие change во время инициализации
            if (this.isInitializing) {
                console.log('[ResultsPage] change ignored (initializing)');
                return;
            }
            const id = this.sessionsSelect.value;
            console.log('[ResultsPage] select changed to:', id);
            if (id) this.loadSession(id);
        });

        this.btnSaveJson.addEventListener('click', () => {
            if (this.currentSessionId) this.exportSession();
        });
    }

    async loadSession(sessionId) {
        console.log('[ResultsPage] loadSession() called with id:', sessionId);
        this.currentSessionId = sessionId;
        try {
            const data = await api.getSessionDetails(sessionId);
            console.log('[ResultsPage] loadSession() got data for id:', data.id);
            this.renderResults(data);
        } catch (err) {
            console.error('[ResultsPage] loadSession() error:', err);
            this.resultsDisplay.innerHTML = `<p style="color:#e53e3e;">Ошибка загрузки данных: ${err.message}</p>`;
        }
    }

    async refresh() {
        console.log('[ResultsPage] ========== refresh() START ==========');
        console.log('[ResultsPage] Current select value BEFORE:', this.sessionsSelect.value);
        
        // Сохраняем текущий выбор ДО обновления списка
        const previousSelection = this.sessionsSelect.value;
        
        // Обновляем список сессий (временно отключаем обработчик)
        this.isInitializing = true;
        const sessions = await this.loadSessions();
        this.isInitializing = false;
        
        console.log('[ResultsPage] After loadSessions, select value:', this.sessionsSelect.value);
        console.log('[ResultsPage] Sessions count:', sessions.length);
        
        if (sessions.length === 0) {
            this.currentSessionId = null;
            this.resultsDisplay.innerHTML = '<p>Нет сохранённых опросов</p>';
            console.log('[ResultsPage] refresh() - no sessions');
            return;
        }
        
        // Восстанавливаем выбор пользователя если он существует
        let finalId;
        if (previousSelection && sessions.find(s => s.id == previousSelection)) {
            this.sessionsSelect.value = previousSelection;
            finalId = previousSelection;
            console.log('[ResultsPage] Restored selection:', previousSelection);
        } else {
            this.sessionsSelect.selectedIndex = 0;
            finalId = this.sessionsSelect.value;
            console.log('[ResultsPage] Selected first option:', finalId);
        }
        
        // Загружаем данные для выбранной сессии
        console.log('[ResultsPage] Calling loadSession with:', finalId);
        await this.loadSession(finalId);
        console.log('[ResultsPage] ========== refresh() END ==========');
    }

    renderResults(data) {
        console.log('[ResultsPage] renderResults() called for session:', data.id);
        
        const paramsHtml = `
            <h4>Параметры опроса</h4>
            <div class="param-grid">
                <span class="label">Температура:</span><span>${data.temperature}</span>
                <span class="label">Макс. токенов:</span><span>${data.maxTokens}</span>
                <span class="label">Системный промпт:</span><span>${data.systemPrompt || '(пусто)'}</span>
                <span class="label">Текст запроса:</span><span>${data.userQuery || '(пусто)'}</span>
            </div>
        `;

        let responsesHtml = '';
        if (data.responses && data.responses.length > 0) {
            data.responses.forEach(r => {
                const isError = r.status === 'error';
                responsesHtml += `
                    <div>
                        <span class="agent-name">Agent: ${r.agentName}</span>
                        <span class="response-text ${isError ? 'error-text' : ''}">
                            Response: ${r.text || '(пустой ответ)'}
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
        console.log('[ResultsPage] renderResults() completed');
    }

    async exportSession() {
        try {
            const data = await api.exportSession(this.currentSessionId);
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