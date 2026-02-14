from fastapi import Request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import logging
from .orchestrator import HybridOrchestrator

logger = logging.getLogger(__name__)

class CallHandler:
    def __init__(self, orchestrator: HybridOrchestrator):
        self.orchestrator = orchestrator
    
    async def handle_incoming_call(self, request: Request) -> Response:
        """Twilio webhook for incoming calls."""
        try:
            form = await request.form()
            call_sid = form.get("CallSid")
            from_number = form.get("From")
            
            # Log call start
            # (you'd insert into call_logs here)
            
            resp = VoiceResponse()
            # Greeting
            resp.say("Hello, I'm your local assistant. How can I help?",
                     voice="Polly.Joanna")
            
            gather = Gather(
                input="speech",
                action="/webhook/process-speech",
                method="POST",
                speech_timeout="auto",
                language="en-US"
            )
            resp.append(gather)
            return Response(content=str(resp), media_type="application/xml")
        
        except Exception as e:
            logger.exception("Error in incoming call webhook")
            # Fallback response
            resp = VoiceResponse()
            resp.say("Sorry, I'm having trouble. Please try again later.")
            return Response(content=str(resp), media_type="application/xml")
    
    async def process_speech(self, request: Request) -> Response:
        """Handle speech result from Twilio."""
        try:
            form = await request.form()
            call_sid = form.get("CallSid")
            speech_result = form.get("SpeechResult")
            
            if not speech_result:
                # No speech detected
                resp = VoiceResponse()
                resp.say("I didn't catch that. Could you repeat?")
                gather = Gather(input="speech", action="/webhook/process-speech")
                resp.append(gather)
                return Response(content=str(resp), media_type="application/xml")
            
            # Process with orchestrator
            result = await self.orchestrator.process_text(speech_result, session_id=call_sid)
            
            resp = VoiceResponse()
            if result["success"]:
                resp.say(result["response"], voice="Polly.Joanna")
            else:
                resp.say("Sorry, something went wrong. Please try again.")
            
            # Continue conversation
            gather = Gather(input="speech", action="/webhook/process-speech")
            resp.append(gather)
            return Response(content=str(resp), media_type="application/xml")
        
        except Exception as e:
            logger.exception("Speech processing failed")
            resp = VoiceResponse()
            resp.say("An error occurred. Goodbye.")
            return Response(content=str(resp), media_type="application/xml")
