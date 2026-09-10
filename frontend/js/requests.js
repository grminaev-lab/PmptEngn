import { api } from './api.js';

export class RequestsPage {
    constructor() {
        this.sourceSelect = document.getElementById('source-agents');
        this.destSelect = document.getElementById('dest-agents');
        this.tempSlider = document.getElementById('temperature');
        this.tempInput = document.getElementById('temperature-input');
        this.tempDisplay = document.getElementById('temp-value');
        this.maxTokens = document.getElementById('max-tokens');
        this.systemPrompt = document.getElementById('system-prompt');
        this.userQuery = document.getElementById('user-query');
        this.btnStart = document.getElementById('btn-start-requests');
        this.btnSave = document.getElementById('btn-save-settings');

        this.init();
    }

    async init() {
        await this.loadConfig();
        this.bindEvents();
    }

    async loadConfig() {
        try {
            const config = await api.getConfig();
            
            // Заполняем список доступных агентов
            this.sourceSelect.innerHTML = '';
            config.agents.forEach(agent => {
                const opt = document.createElement('option');
                opt.value = agent.name;
                opt.textContent = agent.name;
                this.sourceSelect.appendChild(opt);
            });

            // Устанавливаем значения по умолчанию
            this.tempSlider.value = config.defaults.temperature;
            this.tempInput.value = config.defaults.temperature;
            this.tempDisplay.textContent = config.defaults.temperature;
            this.maxTokens.value = config.defaults.maxTokens;
            this.systemPrompt.value = config.defaults.systemPrompt || '';
            this.userQuery.value = config.defaults.userQuery || '';
        } catch (err) {
            console.error('Ошибка загрузки конфигурации:', err);
            alert('Ошибка загрузки конфигурации. Проверьте подключение к серверу.');
        }
    }

    bindEvents() {
        // Синхронизация слайдера и поля ввода температуры
        this.tempSlider.addEventListener('input', () => {
            const val = this.tempSlider.value;
            this.tempInput.value = val;
            this.tempDisplay.textContent = val;
        });
        
        this.tempInput.addEventListener('input', () => {
            let val = parseFloat(this.tempInput.value);
            if (isNaN(val)) return;
            val = Math.min(1, Math.max(0, val));
            this.tempSlider.value = val;
            this.tempDisplay.textContent = val;
        });

        // Кнопки перемещения агентов
        document.getElementById('btn-move-right').addEventListener('click', () => this.moveSelected('right'));
        document.getElementById('btn-move-all-right').addEventListener('click', () => this.moveAll('right'));
        document.getElementById('btn-move-left').addEventListener('click', () => this.moveSelected('left'));
        document.getElementById('btn-move-all-left').addEventListener('click', () => this.moveAll('left'));

        // Сохранение настроек
        this.btnSave.addEventListener('click', () => this.saveSettings());

        // Запуск опроса
        this.btnStart.addEventListener('click', () => this.startPolling());
    }

    moveSelected(direction) {
        const from = direction === 'right' ? this.sourceSelect : this.destSelect;
        const to = direction === 'right' ? this.destSelect : this.sourceSelect;
        const selected = Array.from(from.selectedOptions);
        selected.forEach(opt => {
            from.removeChild(opt);
            to.appendChild(opt);
        });
        // Сортируем оба списка
        this.sortSelect(this.sourceSelect);
        this.sortSelect(this.destSelect);
    }

    moveAll(direction) {
        const from = direction === 'right' ? this.sourceSelect : this.destSelect;
        const to = direction === 'right' ? this.destSelect : this.sourceSelect;
        const options = Array.from(from.options);
        options.forEach(opt => {
            from.removeChild(opt);
            to.appendChild(opt);
        });
    }

    sortSelect(select) {
        const opts = Array.from(select.options);
        opts.sort((a, b) => a.value.localeCompare(b.value));
        opts.forEach(opt => select.appendChild(opt));
    }

    getSelectedAgents() {
        return Array.from(this.destSelect.options).map(opt => opt.value);
    }

    getParams() {
        return {
            temperature: parseFloat(this.tempSlider.value),
            maxTokens: parseInt(this.maxTokens.value),
            systemPrompt: this.systemPrompt.value,
            userQuery: this.userQuery.value,
            agents: this.getSelectedAgents()
        };
    }

    async saveSettings() {
        try {
            const data = this.getParams();
            await api.saveSettings(data);
            alert('Настройки сохранены!');
        } catch (err) {
            alert('Ошибка сохранения: ' + err.message);
        }
    }

    async startPolling() {
        const data = this.getParams();
        if (data.agents.length === 0) {
            alert('Выберите хотя бы одного агента для опроса!');
            return;
        }

        this.btnStart.disabled = true;
        this.btnStart.textContent = '⏳ Запрос выполняется...';

        try {
            const result = await api.startPolling(data);
            alert(result.message || 'Session completed. Please check results.');
        } catch (err) {
            alert('Ошибка: ' + err.message);
        } finally {
            this.btnStart.disabled = false;
            this.btnStart.textContent = 'Start requests';
        }
    }
}