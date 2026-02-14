import logging
from typing import Optional, Dict, Any
from .speech_pipeline import SpeechPipeline
from .nlu_engine import NLUEngine
from .vision_pipeline import VisionPipeline
from .calendar_manager import CalendarManager
from .task_manager import TaskManager
from .privacy import PrivacyFilter
from .cloud_proxy import CloudProxy
from .config import Config
import traceback

logger = logging.getLogger(__name__)

class HybridOrchestrator:
    def __init__(self):
        self.privacy_filter = PrivacyFilter(Config.DB_ENCRYPTION_PASSWORD)
        self.speech = SpeechPipeline()
        self.nlu = NLUEngine(privacy_filter=self.privacy_filter)
        self.vision = VisionPipeline()
        self.calendar = CalendarManager()
        self.tasks = TaskManager()
        self.cloud = CloudProxy(self.privacy_filter, enabled=Config.ENABLE_CLOUD)
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
    async def process_text(self, text: str, session_id: Optional[str] = None,
                           use_cloud: bool = False) -> Dict[str, Any]:
        """Main entry for text input (SMS, chat, etc.)."""
        try:
            # 1. Retrieve context if session exists
            context = self.active_sessions.get(session_id, {}) if session_id else {}
            
            # 2. Intent parsing (try local first)
            intent_result = await self.nlu.parse_intent(text, context)
            
            # 3. If cloud is requested and local confidence low, try cloud
            if use_cloud and intent_result.get("confidence", 1.0) < 0.7:
                cloud_result = await self.cloud.call_llm(text)
                if cloud_result:
                    intent_result = await self.nlu.parse_intent(cloud_result, context)
                    intent_result["source"] = "cloud"
            
            # 4. Execute action based on intent
            response = await self._execute_intent(intent_result, session_id)
            
            # 5. Update session
            if session_id:
                self.active_sessions[session_id] = {
                    **context,
                    "last_intent": intent_result,
                    "last_response": response
                }
            
            return {"success": True, "response": response, "intent": intent_result}
        
        except Exception as e:
            logger.exception("Error in process_text")
            return {"success": False, "error": str(e), "trace": traceback.format_exc()}
    
    async def process_voice(self, audio_bytes: bytes, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Process incoming voice (from call)."""
        try:
            # Transcribe with error handling
            transcript = await self.speech.transcribe(audio_bytes)
            if not transcript:
                return {"success": False, "error": "Transcription failed"}
            
            # Then process as text
            return await self.process_text(transcript, session_id)
        
        except Exception as e:
            logger.exception("Voice processing error")
            return {"success": False, "error": str(e)}
    
    async def process_image(self, image_path: str, task_id: Optional[int] = None) -> Dict[str, Any]:
        """Analyze image and optionally update task."""
        try:
            analysis = self.vision.analyze_image(image_path)
            if not analysis:
                return {"success": False, "error": "Image analysis failed"}
            
            if task_id:
                # Update task progress based on analysis
                self.tasks.update_progress_from_image(task_id, analysis)
            
            return {"success": True, "analysis": analysis}
        
        except Exception as e:
            logger.exception("Image processing error")
            return {"success": False, "error": str(e)}
    
    async def _execute_intent(self, intent: Dict[str, Any], session_id: Optional[str]) -> str:
        """Map intent to actions (calendar, tasks, etc.)."""
        intent_type = intent.get("intent", "unknown")
        try:
            if intent_type == "check_availability":
                dt = intent.get("datetime")
                if not dt:
                    return "I need a date and time to check availability."
                available = self.calendar.check_availability(dt, intent.get("duration", 60))
                if available["available"]:
                    return f"Yes, {dt} is available. Would you like to book it?"
                else:
                    suggestions = available.get("suggested_times", [])
                    if suggestions:
                        return f"That time is not available. How about {suggestions[0]}?"
                    else:
                        return "Sorry, no availability around that time."
            
            elif intent_type == "book_appointment":
                result = self.calendar.book_appointment(
                    title=intent.get("title", "Appointment"),
                    start_datetime=intent["datetime"],
                    duration=intent.get("duration", 60),
                    attendees=intent.get("attendees", [])
                )
                return result["message"]
            
            elif intent_type == "create_task":
                task_id = self.tasks.create_task(
                    title=intent["title"],
                    description=intent.get("description"),
                    due_date=intent.get("due_date")
                )
                return f"Task created with ID {task_id}."
            
            else:
                return "I'm not sure how to help with that. Can you rephrase?"
        
        except KeyError as e:
            logger.error(f"Missing key in intent: {e}")
            return "I didn't get all the details. Please provide more information."
        except Exception as e:
            logger.exception(f"Intent execution failed: {intent_type}")
            return "Sorry, I encountered an error processing your request."
