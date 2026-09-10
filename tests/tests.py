import pytest
import json
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_get_config(client):
    """Тест получения конфигурации"""
    response = client.get('/api/config')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'agents' in data
    assert 'defaults' in data

def test_save_settings(client):
    """Тест сохранения настроек"""
    test_data = {
        'temperature': 0.5,
        'maxTokens': 1500,
        'systemPrompt': 'Test prompt',
        'userQuery': 'Test query'
    }
    response = client.post('/api/settings', json=test_data)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'

def test_get_sessions(client):
    """Тест получения списка сессий"""
    response = client.get('/api/sessions')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)