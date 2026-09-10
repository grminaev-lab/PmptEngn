import aiohttp
import asyncio
import json
from typing import Optional, Dict, Any

class YandexCloudLLM:
    """Клиент для работы с Yandex AI Studio"""
    
    def __init__(self, api_key: str, folder_id: str):
        self.api_key = api_key
        self.folder_id = folder_id
        self.base_url = "https://llm.api.cloud.yandex.net"
        self.timeout = 30
        
    async def completion_async(
        self,
        model_uri: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        system_prompt: str = "",
        user_query: str = "",
        timeout: int = 30
    ) -> str:
        """
        Асинхронный запрос к Yandex AI Studio
        
        Документация: https://cloud.yandex.ru/docs/yandexgpt/api-ref/v1/TextGeneration/completionAsync
        """
        self.timeout = timeout
        
        # Формируем запрос согласно документации Yandex AI Studio
        url = f"{self.base_url}/api/v1/completionAsync"
        
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Формируем сообщения
        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "text": system_prompt
            })
        messages.append({
            "role": "user",
            "text": user_query
        })
        
        payload = {
            "modelUri": model_uri,
            "completionOptions": {
                "temperature": temperature,
                "maxTokens": max_tokens
            },
            "messages": messages
        }
        
        # Отправка запроса
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Yandex API error: {response.status} - {error_text}")
                
                result = await response.json()
                
                # Асинхронный запрос возвращает operation_id
                if 'operation_id' in result:
                    operation_id = result['operation_id']
                    return await self._wait_for_operation(session, operation_id)
                else:
                    # Синхронный ответ (возможно, если используется синхронный метод)
                    return self._extract_response(result)
    
    async def _wait_for_operation(self, session: aiohttp.ClientSession, operation_id: str) -> str:
        """Ожидание завершения асинхронной операции"""
        url = f"{self.base_url}/api/v1/operations/{operation_id}"
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        start_time = asyncio.get_event_loop().time()
        while True:
            # Проверка таймаута
            if asyncio.get_event_loop().time() - start_time > self.timeout:
                raise asyncio.TimeoutError(f"Operation {operation_id} timed out")
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to get operation status: {response.status} - {error_text}")
                
                result = await response.json()
                
                # Проверяем статус операции
                if result.get('done', False):
                    if result.get('response'):
                        return self._extract_response(result['response'])
                    else:
                        error = result.get('error', {}).get('message', 'Unknown error')
                        raise Exception(f"Operation failed: {error}")
                
                # Ожидаем перед следующим запросом
                await asyncio.sleep(0.5)
    
    def _extract_response(self, response_data: Dict[str, Any]) -> str:
        """Извлечение текста ответа из структуры Yandex AI Studio"""
        try:
            # Структура ответа Yandex AI Studio
            if 'result' in response_data:
                alternatives = response_data['result'].get('alternatives', [])
                if alternatives:
                    return alternatives[0].get('message', {}).get('text', '')
            elif 'alternatives' in response_data:
                if response_data['alternatives']:
                    return response_data['alternatives'][0].get('message', {}).get('text', '')
            return str(response_data)
        except Exception as e:
            raise Exception(f"Failed to extract response: {e}")