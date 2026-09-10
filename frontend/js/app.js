import { RequestsPage } from './requests.js';
import { ResultsPage } from './results.js';

document.addEventListener('DOMContentLoaded', () => {
    console.log('[App] DOMContentLoaded');
    
    const requestsPage = new RequestsPage();
    const resultsPage = new ResultsPage();

    const navBtns = document.querySelectorAll('.nav-btn');
    const tabs = {
        requests: document.getElementById('tab-requests'),
        results: document.getElementById('tab-results')
    };

    navBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            const tabName = btn.dataset.tab;
            console.log('[App] ===== Tab clicked:', tabName, '=====');

            // Обновляем активную кнопку
            navBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Показываем соответствующую вкладку
            Object.keys(tabs).forEach(key => {
                tabs[key].classList.toggle('active', key === tabName);
            });

            // При переключении на результаты синхронизируем данные
            if (tabName === 'results') {
                console.log('[App] Calling resultsPage.refresh()...');
                await resultsPage.refresh();
                console.log('[App] refresh() completed');
            }
        });
    });
});