import os
from pathlib import Path
import asyncio
from logger_config import logger

from voice_input import VoiceInput

class VoiceAssistant:
    def __init__(self):
        self.voice_input = VoiceInput()
        
    async def process_text(self, text: str):
        """Process recognized text"""
        print(text)
    
    def on_text_received(self, text: str):
        """Callback for recognized text"""
        asyncio.run(self.process_text(text))
    
    def start(self):
        """Start voice assistant"""
        self.voice_input.on_text_received = self.on_text_received
        self.voice_input.start()
        logger.info("Voice assistant started. Press Ctrl+C to stop...")
    
    def stop(self):
        """Stop voice assistant"""
        self.voice_input.stop()
        logger.info("Voice assistant stopped")

async def main():
    """Main function"""
    try:
        # Initialize voice assistant
        assistant = VoiceAssistant()
        
        # Start voice assistant
        assistant.start()
        
        # Keep the program running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Stopping voice assistant...")
        assistant.stop()
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        if 'assistant' in locals():
            assistant.stop()

if __name__ == "__main__":
    # Set Windows event loop policy
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run main function
    asyncio.run(main())