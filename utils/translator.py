from typing import Optional, Dict, Any
import logging
from langdetect import detect
from googletrans import Translator


class TranslationManager:
    """Manages text translation for Arabic content."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.translator = Translator()
        self.logger = logging.getLogger(__name__)
        
        # Get translation settings
        translation_config = config.get('translation', {})
        self.enabled = translation_config.get('enabled', True)
        self.source_language = translation_config.get('source_language', 'ar')
        self.target_language = translation_config.get('target_language', 'en')
        
    def translate_if_arabic(self, text: str) -> str:
        """
        Detect if text is Arabic and translate to English if needed.
        Returns original text if translation is disabled or fails.
        """
        if not self.enabled or not text or not text.strip():
            return text
            
        try:
            # Detect language
            detected_lang = detect(text)
            
            if detected_lang == self.source_language:
                self.logger.debug(f"Translating Arabic text: {text[:50]}...")
                translated = self.translator.translate(
                    text, 
                    src=self.source_language, 
                    dest=self.target_language
                )
                return translated.text
                
        except Exception as e:
            self.logger.warning(f"Translation failed for text '{text[:50]}...': {e}")
            
        return text
        
    def translate_text(self, text: str, src_lang: Optional[str] = None, 
                      dest_lang: Optional[str] = None) -> str:
        """
        Translate text from source language to destination language.
        Uses default languages from config if not specified.
        """
        if not self.enabled or not text or not text.strip():
            return text
            
        src_lang = src_lang or self.source_language
        dest_lang = dest_lang or self.target_language
        
        try:
            translated = self.translator.translate(text, src=src_lang, dest=dest_lang)
            return translated.text
        except Exception as e:
            self.logger.warning(f"Translation failed: {e}")
            return text