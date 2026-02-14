import logging
from PIL import Image
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import traceback

logger = logging.getLogger(__name__)

class VisionPipeline:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self._load_model()
    
    def _load_model(self):
        try:
            model_id = "vikhyatk/moondream2"
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                trust_remote_code=True,
                torch_dtype=torch.float16 if Config.USE_GPU else torch.float32
            )
            if Config.USE_GPU:
                self.model = self.model.to("cuda")
            self.tokenizer = AutoTokenizer.from_pretrained(model_id)
            logger.info("Loaded Moondream2 vision model")
        except Exception as e:
            logger.error(f"Failed to load vision model: {e}")
            self.model = None
    
    def analyze_image(self, image_path: str) -> dict:
        """Return description and task‑related info."""
        if not self.model:
            logger.error("Vision model not available")
            return {"error": "model not loaded"}
        
        try:
            image = Image.open(image_path).convert("RGB")
            enc_image = self.model.encode_image(image)
            
            description = self.model.answer_question(
                enc_image,
                "Describe this image in detail. What is happening?",
                self.tokenizer
            )
            
            task_type = self.model.answer_question(
                enc_image,
                "What type of work or task is shown? (construction, meeting, document, etc.)",
                self.tokenizer
            )
            
            completion = self.model.answer_question(
                enc_image,
                "Is this work completed or in progress?",
                self.tokenizer
            )
            
            return {
                "description": description,
                "task_type": task_type,
                "completion_status": completion,
                "image_path": image_path
            }
        except Exception as e:
            logger.exception("Image analysis failed")
            return {"error": str(e), "trace": traceback.format_exc()}
