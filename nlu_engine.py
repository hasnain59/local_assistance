import logging
import json
import ollama
from typing import Optional, Dict, Any
from .privacy import PrivacyFilter

logger = logging.getLogger(__name__)

class NLUEngine:
    def __init__(self, privacy_filter: PrivacyFilter):
        self.privacy_filter = privacy_filter
        self.model = Config.LLM_MODEL
        
    async def parse_intent(self, text: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Extract intent and entities using local Ollama."""
        prompt = self._build_prompt(text, context)
        try:
            # Ollama call (blocking, but we can run in thread pool)
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1}
            )
            content = response['message']['content']
            
            # Try to parse JSON from response
            try:
                # Find first { ... } in case model adds extra text
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    intent_data = json.loads(json_match.group())
                else:
                    intent_data = {"intent": "unknown", "text": content}
            except json.JSONDecodeError:
                logger.warning(f"Could not parse JSON from: {content}")
                intent_data = {"intent": "unknown", "raw": content}
            
            intent_data["confidence"] = 0.8  # placeholder; could use logprobs
            return intent_data
        
        except Exception as e:
            logger.exception("Ollama inference failed")
            # Fallback: rule-based simple intent
            return self._rule_based_fallback(text)
    
    def _build_prompt(self, text: str, context: Optional[Dict]) -> str:
        context_str = ""
        if context and context.get("last_intent"):
            context_str = f"Previous intent: {context['last_intent']}\n"
        prompt = f"""{context_str}Analyze the user request and output JSON with intent and entities.
Possible intents: check_availability, book_appointment, create_task, cancel_appointment, unknown.

Request: "{text}"

JSON output:
{{
    "intent": "check_availability",
    "datetime": "2025-03-01T15:00:00",
    "duration_minutes": 60,
    "attendees": ["john@example.com"],
    "title": "Meeting with John"
}}
"""
        return prompt
    
    def _rule_based_fallback(self, text: str) -> Dict[str, Any]:
        """Simple fallback when LLM fails."""
        text_lower = text.lower()
        if "available" in text_lower or "free" in text_lower:
            return {"intent": "check_availability", "confidence": 0.5}
        elif "book" in text_lower or "schedule" in text_lower:
            return {"intent": "book_appointment", "confidence": 0.5}
        elif "task" in text_lower or "todo" in text_lower:
            return {"intent": "create_task", "confidence": 0.5}
        else:
            return {"intent": "unknown", "confidence": 0.3}
