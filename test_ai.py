import os
import logging
from dotenv import load_dotenv

# Set up logging so we can see any API errors
logging.basicConfig(level=logging.INFO)

# Load the .env file explicitly
load_dotenv()

def run_ai_test():
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("❌ ERROR: HF_TOKEN not found! Please check your .env file.")
        return
        
    print("✅ HF_TOKEN found. Initializing AI Engine...")
    print("⏳ Loading local models (this may take a few seconds the first time)...")
    
    from win_engine.analysis.ai_enhancement import get_ai_engine
    engine = get_ai_engine()
    
    print("\n🧠 1. Testing Local AI Sentiment Analysis...")
    sentiment = engine.score_emotional_hook("SHOCKING: YouTube automation is destroying channels!")
    print(f"Result: {sentiment}")
    
    print("\n☁️ 2. Testing Hugging Face Cloud Title Generation...")
    test_script = "In this video, I will show you exactly how to build a YouTube automation channel from scratch using completely free AI tools and earn passive income."
    title = engine.generate_cloud_title(test_script)
    print(f"Result: {title if title else '❌ Failed to generate (Check API token or connection)'}")

if __name__ == "__main__":
    run_ai_test()
