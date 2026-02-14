import logging
import aiohttp
import asyncio
from typing import Optional
from .privacy import PrivacyFilter
from .config import Config

logger = logging.getLogger(__name__)

class CloudProxy:
    """Handle opt‑in cloud API calls with strict privacy safeguards."""
    
    def __init__(self, privacy_filter: PrivacyFilter, enabled: bool = False):
        self.privacy_filter = privacy_filter
        self.enabled = enabled
        self.session: Optional[aiohttp.ClientSession] = None
        self.user_consent = False   # must be set per request/session
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def call_llm(self, prompt: str, max_retries: int = 2) -> Optional[str]:
        """Call cloud LLM (e.g., GPT-4) with anonymized prompt."""
        if not self.enabled or not self.user_consent:
            logger.warning("Cloud offloading disabled or consent not given")
            return None
        
        # Anonymize
        anonymized, mapping = self.privacy_filter.anonymize_text(prompt)
        logger.debug(f"Anonymized prompt: {anonymized}")
        
        # Choose provider based on available keys
        if Config.OPENAI_API_KEY:
            return await self._call_openai(anonymized, max_retries)
        elif Config.ANTHROPIC_API_KEY:
            return await self._call_anthropic(anonymized, max_retries)
        else:
            logger.error("No cloud API keys configured")
            return None
    
    async def _call_openai(self, prompt: str, max_retries: int) -> Optional[str]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        
        for attempt in range(max_retries + 1):
            try:
                async with self.session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data['choices'][0]['message']['content']
                        logger.info("Cloud LLM call succeeded")
                        return content
                    else:
                        error_text = await resp.text()
                        logger.error(f"OpenAI error {resp.status}: {error_text}")
            except asyncio.TimeoutError:
                logger.warning(f"OpenAI timeout (attempt {attempt+1})")
            except Exception as e:
                logger.exception(f"OpenAI call failed: {e}")
            
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)  # exponential backoff
        return None
    
    async def _call_anthropic(self, prompt: str, max_retries: int) -> Optional[str]:
        # Similar implementation for Claude
        pass
