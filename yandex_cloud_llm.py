import aiohttp
import asyncio
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class YandexCloudLLM:
    """Клиент для работы с Yandex AI Studio через Responses API"""
    
    def __init__(self, api_key: str, folder_id: str, vector_store_id: str = None):
        self.api_key = api_key
        self.folder_id = folder_id
        self.vector_store_id = vector_store_id or "fvtnqskf195himgtfia1"
        self.base_url = "https://rest-assistant.api.cloud.yandex.net/v1"
        self.timeout = 30
        logger.info(f"YandexCloudLLM initialized with folder_id: {folder_id}")
        logger.info(f"Vector Store ID: {self.vector_store_id}")
    
    def extract_response_text(self, result: Dict[str, Any]) -> str:
        """
        Извлечение финального текста ответа из структуры Yandex API
        """
        # 1. Прямой output_text
        if 'output_text' in result and result['output_text']:
            return result['output_text']
        
        # 2. Из output массива
        if 'output' in result and result['output']:
            output_items = result['output']
            
            for item in output_items:
                if item.get('type') == 'message' and item.get('role') == 'assistant':
                    if 'content' in item and item['content']:
                        for content_item in item['content']:
                            if content_item.get('type') == 'output_text':
                                text = content_item.get('text', '')
                                if text:
                                    return text
                
                if 'content' in item and item['content']:
                    for content_item in item['content']:
                        if content_item.get('type') == 'output_text':
                            text = content_item.get('text', '')
                            if text:
                                return text
            
            for item in output_items:
                if 'content' in item and item['content']:
                    for content_item in item['content']:
                        if content_item.get('type') == 'output_text':
                            text = content_item.get('text', '')
                            if text:
                                return text
        
        # 3. Из choices (старый формат)
        if 'choices' in result and result['choices']:
            for choice in result['choices']:
                message = choice.get('message', {})
                if message.get('content'):
                    return message.get('content')
                if message.get('text'):
                    return message.get('text')
        
        logger.warning("No output_text found in response structure")
        return ""
    
    async def completion_async(
        self,
        model_uri: str,
        agent_id: str,
        temperature: float = 0.25,
        max_tokens: int = 1259,
        system_prompt: str = "",
        user_query: str = "",
        message_history: list = None,
        previous_response_id: str = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Асинхронный запрос к Yandex AI Studio через Responses API
        """
        self.timeout = timeout
        
        url = f"{self.base_url}/responses"
        
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        
        if message_history:
            input_messages = message_history
        else:
            input_messages = [{"role": "user", "content": user_query}]
        
        payload = {
            "model": model_uri,
            "prompt": {
                "id": agent_id
            },
            "input": input_messages,
            "instructions": system_prompt or "Ты полезный ассистент. Отвечай кратко и информативно.",
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "tools": [
                {
                    "type": "file_search",
                    "vector_store_ids": [self.vector_store_id],
                    "max_num_results": 5
                }
            ],
            "tool_choice": "auto",
            "top_p": 1,
            "stream": False
        }
        
        if previous_response_id:
            payload["previous_response_id"] = previous_response_id
        
        logger.info(f"Calling Yandex Responses API for agent: {agent_id}")
        logger.debug(f"Model URI: {model_uri}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    response_text = await response.text()
                    
                    if response.status != 200:
                        logger.error(f"Yandex API error: {response.status} - {response_text}")
                        raise Exception(f"Yandex API error: {response.status} - {response_text}")
                    
                    result = json.loads(response_text)
                    logger.info("Yandex Responses API call successful")
                    
                    output_text = self.extract_response_text(result)
                    
                    if 'usage' in result:
                        usage = result['usage']
                        logger.info(f"Token usage - Input: {usage.get('input_tokens', 0)}, Output: {usage.get('output_tokens', 0)}, Total: {usage.get('total_tokens', 0)}")
                    
                    logger.debug(f"Extracted response text length: {len(output_text)} chars")
                    
                    return {
                        'success': True,
                        'response_id': result.get('id'),
                        'status': result.get('status'),
                        'output_text': output_text,
                        'raw_response': json.dumps(result, ensure_ascii=False),
                        'usage': result.get('usage', {})
                    }
                        
        except asyncio.TimeoutError:
            logger.error(f"Timeout after {timeout} seconds")
            return {
                'success': False,
                'error': f'Timeout after {timeout} seconds'
            }
        except Exception as e:
            logger.error(f"Yandex API error: {e}")
            return {
                'success': False,
                'error': str(e)
            }