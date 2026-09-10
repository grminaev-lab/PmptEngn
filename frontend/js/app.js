import { RequestsPage } from './requests.js';
import { ResultsPage } from './results.js';

document.addEventListener('DOMContentLoaded', () => {
    // Инициализация страниц
    const requestsPage = new RequestsPage();
    const resultsPage = new ResultsPage();

    // Переключение вкладок
    const navBtns = document.querySelectorAll('.nav-btn');
    const tabs = {
        requests: document.getElementById('tab-requests'),
        results: document.getElementById('tab-results')
    };

    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Обновляем активную кнопку
            navBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Показываем соответствующую вкладку
            const tabName = btn.dataset.tab;
            Object.keys(tabs).forEach(key => {
                tabs[key].classList.toggle('active', key === tabName);
            });

            // При переключении на результаты обновляем список сессий
            if (tabName === 'results') {
                resultsPage.loadSessions();
            }
        });
    });
});