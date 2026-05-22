import asyncio
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

async def test_ai():
    hf_token = os.getenv("HF_TOKEN")
    model = "moonshotai/Kimi-K2.5:fireworks-ai"
    
    print(f"Testing with token: {hf_token[:5]}...{hf_token[-5:]}")
    print(f"Model: {model}")
    
    client = AsyncOpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=hf_token,
    )
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello"}
            ],
            max_tokens=10,
        )
        print("Response received:")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_ai())
