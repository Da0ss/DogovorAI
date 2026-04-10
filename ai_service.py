import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.getenv("HF_TOKEN"),
)

def analyze_contract_image(base64_image):
    response = client.chat.completions.create(
        model="moonshotai/Kimi-K2.5:fireworks-ai",
        messages=[
            {
                "role": "system",
                "content": "Ты юрист-аналитик. Найди риски в договоре на фото и ответь строго в JSON."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Проанализируй этот документ на риски:"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ],
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content