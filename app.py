import os
import sys
import json
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from models import db, Request, Response
from config import Config
from yandex_cloud_llm import YandexCloudLLM
import logging
import traceback

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='frontend')
app.config.from_object(Config)

# Получаем абсолютный путь к БД
db_path = os.path.abspath('database/polling.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
logger.info(f"Database path: {db_path}")

CORS(app)
db.init_app(app)

# ============================================
# СОЗДАНИЕ НЕОБХОДИМЫХ ПАПОК
# ============================================

def create_required_directories():
    """Создание необходимых папок с обработкой ошибок"""
    directories = ['database', 'results']
    
    for directory in directories:
        try:
            # Получаем абсолютный путь
            abs_path = os.path.abspath(directory)
            
            # Проверяем, существует ли папка
            if not os.path.exists(abs_path):
                os.makedirs(abs_path, exist_ok=True)
                logger.info(f"Created directory: {abs_path}")
            else:
                logger.info(f"Directory already exists: {abs_path}")
            
            # Проверяем права на запись
            test_file = os.path.join(abs_path, '.write_test')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                logger.info(f"Write permissions OK for: {abs_path}")
            except Exception as e:
                logger.error(f"No write permissions for {abs_path}: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to create directory {directory}: {e}")
            return False
    
    return True

# Создаем папки при запуске
if not create_required_directories():
    logger.error("Failed to create required directories. Exiting...")
    sys.exit(1)

# ============================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# ============================================

def init_database():
    """Инициализация базы данных с обработкой ошибок"""
    try:
        # Проверяем, существует ли файл БД
        db_file = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        logger.info(f"Checking database file: {db_file}")
        
        # Если файл существует, проверяем его
        if os.path.exists(db_file):
            logger.info(f"Database file exists: {db_file}")
            # Проверяем, можно ли открыть
            try:
                with open(db_file, 'r+') as f:
                    pass
                logger.info("Database file is accessible")
            except Exception as e:
                logger.error(f"Cannot access database file: {e}")
                logger.info("Removing corrupted database file...")
                try:
                    os.remove(db_file)
                    logger.info("Removed corrupted database file")
                except Exception as e2:
                    logger.error(f"Cannot remove database file: {e2}")
                    return False
        
        # Создаем таблицы
        with app.app_context():
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Проверяем, что таблицы созданы
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Tables in database: {tables}")
            
            return True
            
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        logger.error(traceback.format_exc())
        
        # Пробуем альтернативный путь
        try:
            alt_path = os.path.join(os.path.dirname(__file__), 'database', 'polling.db')
            logger.info(f"Trying alternative path: {alt_path}")
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{alt_path}'
            with app.app_context():
                db.create_all()
                logger.info("Database created with alternative path")
                return True
        except Exception as e2:
            logger.error(f"Alternative path also failed: {e2}")
            return False

# Инициализируем БД
if not init_database():
    logger.error("Failed to initialize database. Exiting...")
    sys.exit(1)


# Инициализация клиента Yandex Cloud
yandex_client = None

def init_yandex_client():
    global yandex_client
    if yandex_client is None:
        api_key = Config.YANDEX_API_KEY
        folder_id = Config.FOLDER_ID
        if api_key and folder_id:
            try:
                yandex_client = YandexCloudLLM(api_key=api_key, folder_id=folder_id)
                logger.info("Yandex Cloud client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Yandex Cloud client: {e}")
        else:
            logger.warning("Yandex Cloud API key or folder ID not set")
    return yandex_client

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def get_config():
    """Получение конфигурации из файла"""
    try:
        return Config.load_config()
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        # Возвращаем конфигурацию по умолчанию
        return {
            'agents': [],
            'defaults': {
                'temperature': 0.7,
                'maxTokens': 2000,
                'systemPrompt': 'You are a helpful assistant.',
                'userQuery': 'Tell me about artificial intelligence.'
            },
            'timeout': 30
        }

def save_config(config_data):
    """Сохранение конфигурации"""
    try:
        Config.save_config(config_data)
        logger.info("Configuration saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False

def format_response_for_display(agent_name, response_text, status='success', error=None):
    """Форматирование ответа для отображения"""
    if status == 'error':
        return {
            'agent_name': agent_name,
            'text': f'Ошибка: {error}',
            'status': 'error'
        }
    return {
        'agent_name': agent_name,
        'text': response_text,
        'status': 'success'
    }

async def poll_agent_async(agent, temperature, max_tokens, system_prompt, user_query):
    """Асинхронный опрос одного агента"""
    client = init_yandex_client()
    if not client:
        return {
            'agent_name': agent['name'],
            'status': 'error',
            'error': 'Yandex Cloud client not initialized. Check API key and folder ID.'
        }
    
    try:
        logger.info(f"Polling agent: {agent['name']}")
        # Использование асинхронного метода Yandex AI Studio
        response = await client.completion_async(
            model_uri=agent['uri'],
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            user_query=user_query,
            timeout=Config.TIMEOUT
        )
        
        logger.info(f"Agent {agent['name']} responded successfully")
        return {
            'agent_name': agent['name'],
            'status': 'success',
            'response': response
        }
    except asyncio.TimeoutError:
        logger.warning(f"Agent {agent['name']} timed out after {Config.TIMEOUT} seconds")
        return {
            'agent_name': agent['name'],
            'status': 'error',
            'error': f'Timeout after {Config.TIMEOUT} seconds'
        }
    except Exception as e:
        logger.error(f"Error polling agent {agent['name']}: {e}")
        return {
            'agent_name': agent['name'],
            'status': 'error',
            'error': str(e)
        }

async def poll_agents_async(agents, params):
    """Асинхронный опрос всех выбранных агентов"""
    tasks = []
    for agent in agents:
        task = poll_agent_async(
            agent,
            params['temperature'],
            params['maxTokens'],
            params['systemPrompt'],
            params['userQuery']
        )
        tasks.append(task)
    
    # Запуск всех задач параллельно
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

# ============================================
# API ЭНДПОИНТЫ
# ============================================

@app.route('/api/config', methods=['GET'])
def get_config_api():
    """Получение конфигурации"""
    try:
        config = get_config()
        return jsonify({
            'agents': config.get('agents', []),
            'defaults': config.get('defaults', {}),
            'timeout': config.get('timeout', 30)
        })
    except Exception as e:
        logger.error(f"Error in get_config_api: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/settings', methods=['POST'])
def save_settings_api():
    """Сохранение настроек"""
    try:
        data = request.json
        config = get_config()
        
        # Обновляем значения по умолчанию
        config['defaults']['temperature'] = data.get('temperature', 0.7)
        config['defaults']['maxTokens'] = data.get('maxTokens', 2000)
        config['defaults']['systemPrompt'] = data.get('systemPrompt', '')
        config['defaults']['userQuery'] = data.get('userQuery', '')
        
        if save_config(config):
            return jsonify({'status': 'success', 'message': 'Settings saved successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to save settings'}), 500
    except Exception as e:
        logger.error(f"Error in save_settings_api: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/poll', methods=['POST'])
def start_polling():
    """Запуск опроса агентов"""
    try:
        logger.info("=" * 60)
        logger.info("STARTING POLLING REQUEST")
          
        data = request.json
        logger.debug(f"Request data: {data}")
        agent_names = data.get('agents', [])
        logger.info(f"Selected agents: {agent_names}")
        
        if not agent_names:
            return jsonify({'status': 'error', 'message': 'No agents selected'}), 400
        
        # Получаем полную информацию об агентах из конфига
        config = get_config()
        all_agents = config.get('agents', [])
        selected_agents = [a for a in all_agents if a['name'] in agent_names]
        
        if not selected_agents:
            return jsonify({'status': 'error', 'message': 'Selected agents not found in configuration'}), 400
        
        # Проверяем, инициализирован ли клиент Yandex Cloud
        client = init_yandex_client()
        logger.debug(f"Yandex client initialized: {client is not None}")
        if not client:
            logger.error("Yandex Cloud client not initialized")
            return jsonify({
                'status': 'error', 
                'message': 'Yandex Cloud client not initialized. Please check API key and folder ID in .env file.'
            }), 500
        
        # Создаем запись в БД
        logger.info("Creating database record...")
        new_request = Request(
            temperature=data.get('temperature', 0.7),
            max_tokens=data.get('maxTokens', 2000),
            system_prompt=data.get('systemPrompt', ''),
            user_query=data.get('userQuery', '')
        )
        db.session.add(new_request)
        db.session.commit()
        logger.info(f"Created new request with ID: {new_request.request_id}")
        
        # Асинхронный опрос агентов
        params = {
            'temperature': data.get('temperature', 0.7),
            'maxTokens': data.get('maxTokens', 2000),
            'systemPrompt': data.get('systemPrompt', ''),
            'userQuery': data.get('userQuery', '')
        }
        logger.info(f"Polling parameters: temperature={params['temperature']}, maxTokens={params['maxTokens']}")
        
        # Запускаем асинхронные запросы
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(poll_agents_async(selected_agents, params))
        loop.close()
        logger.info(f"Polling completed. Results: {len(results)}")

        # Сохраняем результаты в БД
        response_count = 0
        error_count = 0
        
        for result in results:
            if isinstance(result, Exception):
                # Ошибка выполнения
                response = Response(
                    req_id=new_request.request_id,
                    agent_name='Unknown',
                    status='error',
                    error_message=str(result)
                )
                error_count += 1
            elif result.get('status') == 'error':
                # Ошибка агента
                response = Response(
                    req_id=new_request.request_id,
                    agent_name=result.get('agent_name', 'Unknown'),
                    status='error',
                    error_message=result.get('error', 'Unknown error')
                )
                error_count += 1
            else:
                # Успешный ответ
                response = Response(
                    req_id=new_request.request_id,
                    agent_name=result.get('agent_name', 'Unknown'),
                    resp_text=result.get('response', ''),
                    status='success'
                )
                response_count += 1
            db.session.add(response)
        
        db.session.commit()
        logger.info(f"Saved {response_count} responses and {error_count} errors for request {new_request.request_id}")
        
        return jsonify({
            'status': 'success',
            'message': 'Session completed. Please check results.',
            'request_id': new_request.request_id,
            'responses_count': response_count,
            'errors_count': error_count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in start_polling: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Получение списка всех сессий"""
    try:
        requests = Request.query.order_by(Request.req_date.desc()).all()
        sessions = []
        for req in requests:
            sessions.append({
                'id': req.request_id,
                'date': req.req_date.strftime('%Y-%m-%d'),
                'time': req.req_date.strftime('%H:%M:%S')
            })
        return jsonify(sessions)
    except Exception as e:
        logger.error(f"Error in get_sessions: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/session/<int:session_id>', methods=['GET'])
def get_session_details(session_id):
    """Получение деталей конкретной сессии"""
    try:
        request_obj = Request.query.get(session_id)
        if not request_obj:
            return jsonify({'status': 'error', 'message': 'Session not found'}), 404
        
        response_data = {
            'id': request_obj.request_id,
            'temperature': request_obj.temperature,
            'maxTokens': request_obj.max_tokens,
            'systemPrompt': request_obj.system_prompt,
            'userQuery': request_obj.user_query,
            'responses': []
        }
        
        for resp in request_obj.responses:
            if resp.status == 'error':
                response_data['responses'].append({
                    'agentName': resp.agent_name,
                    'text': f'Ошибка: {resp.error_message}',
                    'status': 'error'
                })
            else:
                response_data['responses'].append({
                    'agentName': resp.agent_name,
                    'text': resp.resp_text,
                    'status': 'success'
                })
        
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_session_details: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/export/<int:session_id>', methods=['GET'])
def export_session(session_id):
    """Экспорт сессии в JSON"""
    try:
        request_obj = Request.query.get(session_id)
        if not request_obj:
            return jsonify({'status': 'error', 'message': 'Session not found'}), 404
        
        # Формируем данные для экспорта
        export_data = {
            'request_id': request_obj.request_id,
            'date': request_obj.req_date.strftime('%Y-%m-%d %H:%M:%S'),
            'parameters': {
                'temperature': request_obj.temperature,
                'max_tokens': request_obj.max_tokens,
                'system_prompt': request_obj.system_prompt,
                'user_query': request_obj.user_query
            },
            'responses': []
        }
        
        for resp in request_obj.responses:
            export_data['responses'].append({
                'agent_name': resp.agent_name,
                'response': resp.resp_text,
                'status': resp.status,
                'error': resp.error_message
            })
        
        # Сохраняем в файл
        filename = f"results/{request_obj.request_id}_{request_obj.req_date.strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Exported session {session_id} to {filename}")
        return send_file(filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Error in export_session: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# СЕРВИНГ СТАТИЧЕСКИХ ФАЙЛОВ ФРОНТЕНДА
# ============================================

@app.route('/')
def index():
    """Главная страница - отдаем фронтенд"""
    return send_from_directory('frontend', 'index.html')

@app.route('/css/<path:path>')
def serve_css(path):
    """Сервинг CSS файлов"""
    return send_from_directory('frontend/css', path)

@app.route('/js/<path:path>')
def serve_js(path):
    """Сервинг JavaScript файлов"""
    return send_from_directory('frontend/js', path)

@app.route('/assets/<path:path>')
def serve_assets(path):
    """Сервинг файлов assets (опционально)"""
    return send_from_directory('frontend/assets', path)

# Общий обработчик для любых других статических файлов
@app.route('/static/<path:path>')
def serve_static(path):
    """Сервинг статических файлов"""
    return send_from_directory('frontend', path)

# ============================================
# ОБРАБОТКА ОШИБОК
# ============================================

@app.errorhandler(404)
def not_found(error):
    """Обработка 404 ошибок"""
    return jsonify({'status': 'error', 'message': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Обработка 500 ошибок"""
    logger.error(f"Internal server error: {error}")
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

# ============================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
    
    # Проверяем наличие API ключа при запуске
    if not Config.YANDEX_API_KEY or not Config.FOLDER_ID:
        logger.warning("=" * 60)
        logger.warning("WARNING: YANDEX_API_KEY or FOLDER_ID not set in .env file")
        logger.warning("The application will not be able to poll AI agents")
        logger.warning("Please set these variables in the .env file and restart")
        logger.warning("=" * 60)
    else:
        logger.info("Yandex Cloud credentials found")
    
    logger.info("=" * 60)
    logger.info("Starting AI Polling Application")
    logger.info("Open http://localhost:5000 in your browser")
    logger.info("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)