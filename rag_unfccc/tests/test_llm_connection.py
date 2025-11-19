#!/usr/bin/env python3
"""
Simple LLM Connection Test
Tests if the LLM API is properly configured and accessible.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path (go up one level from tests/ directory)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
load_dotenv(project_root / ".env")

def test_llm_connection():
    """Test LLM connection and configuration."""
    print("=" * 70)
    print("LLM CONNECTION TEST")
    print("=" * 70)
    
    # Check if .env file exists
    env_file = project_root / ".env"
    if not env_file.exists():
        print("\n⚠️  WARNING: .env file not found!")
        print(f"   Expected location: {env_file}")
        print("\n   To create a .env file:")
        print("   1. Copy env_format.txt to .env:")
        print(f"      copy env_format.txt .env")
        print("   2. Edit .env and add your API keys:")
        print("      AI_API_KEY=your_key_here")
        print("      AI_BASE_URL=your_url_here")
        print()
    else:
        print(f"\n✅ Found .env file: {env_file}")
    
    # Check environment variables
    print("\n1. Checking Environment Variables:")
    print("-" * 70)
    
    api_key = os.getenv('AI_API_KEY')
    base_url = os.getenv('AI_BASE_URL')
    model = os.getenv('LLM_MODEL', 'meta-llama/Meta-Llama-3.1-70B-Instruct')
    temperature = os.getenv('LLM_TEMPERATURE', '0.1')
    max_tokens = os.getenv('LLM_MAX_TOKENS', '4000')
    
    print(f"  AI_API_KEY: {'✅ Set' if api_key else '❌ Missing'}")
    if api_key:
        print(f"    Value: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")
    
    print(f"  AI_BASE_URL: {'✅ Set' if base_url else '❌ Missing'}")
    if base_url:
        print(f"    Value: {base_url}")
    
    print(f"  LLM_MODEL: {model}")
    print(f"  LLM_TEMPERATURE: {temperature}")
    print(f"  LLM_MAX_TOKENS: {max_tokens}")
    
    if not api_key or not base_url:
        print("\n❌ ERROR: Missing required environment variables!")
        print("\nPlease set the following in your .env file:")
        print("  AI_API_KEY=your_api_key_here")
        print("  AI_BASE_URL=your_base_url_here")
        print("\nExample:")
        print("  AI_BASE_URL=https://api.openai.com/v1")
        print("  AI_API_KEY=sk-...")
        print("\n💡 See SETUP_ENV.md for detailed instructions")
        return False
    
    # Try to initialize LLM client
    print("\n2. Initializing LLM Client:")
    print("-" * 70)
    
    try:
        from group4py.src.query import LLMClient
        
        llm_client = LLMClient(supports_guided_json=True)
        
        if not llm_client.client:
            print("  ❌ Failed to initialize LLM client")
            print("  Check your API credentials and base URL")
            return False
        
        print("  ✅ LLM client initialized successfully")
        print(f"  Model: {llm_client.model}")
        print(f"  Base URL: {base_url}")
        
    except Exception as e:
        print(f"  ❌ Error initializing client: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Try a simple API call
    print("\n3. Testing API Connection:")
    print("-" * 70)
    
    try:
        test_prompt = "Say 'Hello, world!' in JSON format: {\"message\": \"your response here\"}"
        
        print(f"  Sending test request...")
        print(f"  Prompt: {test_prompt[:50]}...")
        
        response = llm_client.call_llm(test_prompt)
        
        if response:
            print("  ✅ API call successful!")
            # Handle LLMResponseModel structure
            if hasattr(response, 'answer'):
                # response.answer is an LLMAnswerModel object
                if hasattr(response.answer, 'summary'):
                    print(f"  Summary: {response.answer.summary[:100]}...")
                elif hasattr(response.answer, 'detailed_response'):
                    print(f"  Response: {response.answer.detailed_response[:100]}...")
                else:
                    print(f"  Answer object: {type(response.answer).__name__}")
            if hasattr(response, 'question'):
                print(f"  Question: {response.question[:50]}...")
            if hasattr(response, 'citations'):
                print(f"  Citations: {len(response.citations)}")
            return True
        else:
            print("  ❌ API call returned no response")
            return False
            
    except Exception as e:
        print(f"  ❌ API call failed: {e}")
        print(f"  Error type: {type(e).__name__}")
        
        # Provide helpful error messages
        error_str = str(e).lower()
        if "connection" in error_str or "timeout" in error_str:
            print("\n  💡 Connection Error - Check:")
            print("     - Is the base URL correct?")
            print("     - Is your internet connection working?")
            print("     - Is the API service accessible?")
        elif "authentication" in error_str or "unauthorized" in error_str or "401" in error_str:
            print("\n  💡 Authentication Error - Check:")
            print("     - Is your API key correct?")
            print("     - Has your API key expired?")
        elif "rate limit" in error_str or "429" in error_str:
            print("\n  💡 Rate Limit Error - Wait a moment and try again")
        elif "model" in error_str or "404" in error_str:
            print("\n  💡 Model Error - Check:")
            print("     - Is the model name correct?")
            print("     - Is the model available at this endpoint?")
        
        import traceback
        print("\n  Full error details:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_llm_connection()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ LLM CONNECTION TEST PASSED")
    else:
        print("❌ LLM CONNECTION TEST FAILED")
        print("\nNext steps:")
        print("1. Check your .env file has AI_API_KEY and AI_BASE_URL set")
        print("2. Verify your API credentials are correct")
        print("3. Test your internet connection")
        print("4. Check if the API service is accessible")
    print("=" * 70)

