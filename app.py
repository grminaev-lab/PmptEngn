import os
import sys
import json
import asyncio
import logging
import traceback
from datetime import datetime
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from models import db, Request, Response
from config import Config
from yandex_cloud_llm import YandexCloudLLM

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='frontend')
app.config.from_object(Config)

db_path = os.path.abspath('database/polling.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
logger.info(f"Database path: {db_path}")

CORS(app)
db.init_app(app)

# ============================================
# СОЗДАНИЕ НЕОБХОДИМЫХ ПАПОК
# ============================================

def create_required_directories():
    directories = ['database', 'results']
    for directory in directories:
        try:
            abs_path = os.path.abspath(directory)
            if not os.path.exists(abs_path):
                os.makedirs(abs_path, exist_ok=True)
                logger.info(f"Created directory: {abs_path}")
            else:
                logger.info(f"Directory already exists: {abs_path}")
            
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

if not create_required_directories():
    logger.error("Failed to create required directories. Exiting...")
    sys.exit(1)

# ============================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# ============================================

def init_database():
    try:
        db_file = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        logger.info(f"Checking database file: {db_file}")
        
        if os.path.exists(db_file):
            logger.info(f"Database file exists: {db_file}")
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
        
        with app.app_context():
            db.create_all()
            logger.info("Database tables created successfully")
            
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Tables in database: {tables}")
            return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        logger.error(traceback.format_exc())
        return False

if not init_database():
    logger.error("Failed to initialize database. Exiting...")
    sys.exit(1)

# ============================================
# ИНИЦИАЛИЗАЦИЯ КЛИЕНТА YANDEX CLOUD
# ============================================

yandex_client = None

def init_yandex_client():
    global yandex_client
    if yandex_client is None:
        api_key = Config.YANDEX_API_KEY
        folder_id = Config.FOLDER_ID
        if api_key and folder_id:
            try:
                config = get_config()
                vector_store_id = config.get('vector_store_id', 'fvtnqskf195himgtfia1')
                yandex_client = YandexCloudLLM(
                    api_key=api_key, 
                    folder_id=folder_id,
                    vector_store_id=vector_store_id
                )
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
    try:
        return Config.load_config()
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {
            'agents': [],
            'defaults': {
                'temperature': 0.25,
                'maxTokens': 1259,
                'systemPrompt': 'Ты продавец косметики. Постарайся продать, что-нибудь из каталога. \nНе выдумывай ответ, проверь актуальную информацию.\nВ конце покажи цепочку рассуждений.',
                'userQuery': 'Мыло есть?'
            },
            'timeout': 30,
            'vector_store_id': 'fvtnqskf195himgtfia1'
        }

def save_config(config_data):
    try:
        Config.save_config(config_data)
        logger.info("Configuration saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False

async def poll_agent_async(agent, temperature, max_tokens, system_prompt, user_query, message_history=None):
    client = init_yandex_client()
    if not client:
        return {
            'agent_name': agent['name'],
            'status': 'error',
            'error': 'Yandex Cloud client not initialized. Check API key and folder ID.'
        }
    
    try:
        logger.info(f"Polling agent: {agent['name']}")
        
        agent_id = agent.get('agent_id')
        model_name = agent.get('model_name')
        
        if not agent_id or not model_name:
            raise Exception(f"Agent {agent['name']} missing agent_id or model_name in config")
        
        model_uri = f"gpt://{Config.FOLDER_ID}/{model_name}"
        
        logger.info(f"Model URI: {model_uri}")
        logger.info(f"Agent ID: {agent_id}")
        
        input_messages = message_history or [{"role": "user", "content": user_query}]
        
        result = await client.completion_async(
            model_uri=model_uri,
            agent_id=agent_id,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            user_query=user_query,
            message_history=input_messages,
            timeout=Config.TIMEOUT
        )
        
        if result.get('success'):
            response_text = result.get('output_text', '')
            raw_json = result.get('raw_response', '')
            
            logger.info(f"Agent {agent['name']} responded with {len(response_text)} chars")
            
            return {
                'agent_name': agent['name'],
                'status': 'success',
                'response': response_text,
                'raw_response': raw_json,
                'response_id': result.get('response_id'),
                'usage': result.get('usage', {})
            }
        else:
            logger.error(f"Agent {agent['name']} error: {result.get('error')}")
            return {
                'agent_name': agent['name'],
                'status': 'error',
                'error': result.get('error', 'Unknown error')
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
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

# ============================================
# API ЭНДПОИНТЫ
# ============================================

@app.route('/api/config', methods=['GET'])
def get_config_api():
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
    try:
        data = request.json
        config = get_config()
        config['defaults']['temperature'] = data.get('temperature', 0.25)
        config['defaults']['maxTokens'] = data.get('maxTokens', 1259)
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
    try:
        logger.info("=" * 60)
        logger.info("STARTING POLLING REQUEST")
        
        data = request.json
        logger.debug(f"Request data: {data}")
        
        agent_names = data.get('agents', [])
        logger.info(f"Selected agents: {agent_names}")
        
        if not agent_names:
            logger.warning("No agents selected")
            return jsonify({'status': 'error', 'message': 'No agents selected'}), 400
        
        config = get_config()
        all_agents = config.get('agents', [])
        selected_agents = [a for a in all_agents if a['name'] in agent_names]
        logger.info(f"Selected agents found: {[a['name'] for a in selected_agents]}")
        
        if not selected_agents:
            logger.error("Selected agents not found in configuration")
            return jsonify({'status': 'error', 'message': 'Selected agents not found in configuration'}), 400
        
        client = init_yandex_client()
        if not client:
            logger.error("Yandex Cloud client not initialized")
            return jsonify({
                'status': 'error', 
                'message': 'Yandex Cloud client not initialized. Please check API key and folder ID in .env file.'
            }), 500
        
        logger.info("Creating database record...")
        try:
            new_request = Request(
                temperature=data.get('temperature', 0.25),
                max_tokens=data.get('maxTokens', 1259),
                system_prompt=data.get('systemPrompt', ''),
                user_query=data.get('userQuery', ''),
                message_history=[]
            )
            db.session.add(new_request)
            db.session.commit()
            logger.info(f"Created new request with ID: {new_request.request_id}")
        except Exception as db_error:
            logger.error(f"Database error: {db_error}")
            logger.error(traceback.format_exc())
            with app.app_context():
                db.drop_all()
                db.create_all()
                logger.info("Recreated database tables")
            new_request = Request(
                temperature=data.get('temperature', 0.25),
                max_tokens=data.get('maxTokens', 1259),
                system_prompt=data.get('systemPrompt', ''),
                user_query=data.get('userQuery', ''),
                message_history=[]
            )
            db.session.add(new_request)
            db.session.commit()
            logger.info(f"Created new request with ID: {new_request.request_id}")
        
        params = {
            'temperature': data.get('temperature', 0.25),
            'maxTokens': data.get('maxTokens', 1259),
            'systemPrompt': data.get('systemPrompt', ''),
            'userQuery': data.get('userQuery', '')
        }
        logger.info(f"Polling parameters: temperature={params['temperature']}, maxTokens={params['maxTokens']}")
        
        logger.info("Starting async polling...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(poll_agents_async(selected_agents, params))
        loop.close()
        logger.info(f"Polling completed. Results: {len(results)}")
        
        response_count = 0
        error_count = 0
        
        for idx, result in enumerate(results):
            logger.debug(f"Result {idx}: {result}")
            if isinstance(result, Exception):
                logger.error(f"Exception in result {idx}: {result}")
                response = Response(
                    req_id=new_request.request_id,
                    agent_name='Unknown',
                    status='error',
                    error_message=str(result)
                )
                error_count += 1
            elif result.get('status') == 'error':
                logger.error(f"Error in agent {result.get('agent_name')}: {result.get('error')}")
                response = Response(
                    req_id=new_request.request_id,
                    agent_name=result.get('agent_name', 'Unknown'),
                    status='error',
                    error_message=result.get('error', 'Unknown error')
                )
                error_count += 1
            else:
                logger.info(f"Success from agent {result.get('agent_name')}")
                response = Response(
                    req_id=new_request.request_id,
                    agent_name=result.get('agent_name', 'Unknown'),
                    resp_text=result.get('response', ''),
                    raw_response=result.get('raw_response', ''),
                    status='success'
                )
                response_count += 1
            db.session.add(response)
        
        db.session.commit()
        logger.info(f"Saved {response_count} responses and {error_count} errors for request {new_request.request_id}")
        logger.info("=" * 60)
        
        return jsonify({
            'status': 'success',
            'message': 'Session completed. Please check results.',
            'request_id': new_request.request_id,
            'responses_count': response_count,
            'errors_count': error_count
        })
    except Exception as e:
        db.session.rollback()
        logger.error("=" * 60)
        logger.error("ERROR IN START_POLLING:")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error("Traceback:")
        logger.error(traceback.format_exc())
        logger.error("=" * 60)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
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
    try:
        request_obj = Request.query.get(session_id)
        if not request_obj:
            return jsonify({'status': 'error', 'message': 'Session not found'}), 404
        
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
    return send_from_directory('frontend', 'index.html')

@app.route('/css/<path:path>')
def serve_css(path):
    return send_from_directory('frontend/css', path)

@app.route('/js/<path:path>')
def serve_js(path):
    return send_from_directory('frontend/js', path)

@app.route('/assets/<path:path>')
def serve_assets(path):
    return send_from_directory('frontend/assets', path)

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('frontend', path)

# ============================================
# ОБРАБОТКА ОШИБОК
# ============================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'status': 'error', 'message': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
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
            logger.info("Attempting to recreate database...")
            try:
                db_path = 'database/polling.db'
                if os.path.exists(db_path):
                    os.remove(db_path)
                    logger.info(f"Removed old database file: {db_path}")
                db.create_all()
                logger.info("Database recreated successfully")
            except Exception as e2:
                logger.error(f"Failed to recreate database: {e2}")
    
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
    logger.info(f"Database path: {os.path.abspath('database/polling.db')}")
    logger.info("Open http://localhost:5000 in your browser")
    logger.info("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)