import os
import openai
from dotenv import load_dotenv

load_dotenv()

# Configure for OpenRouter
openrouter.api_key = os.getenv("OPENROUTER_API_KEY")
openrouter.api_base = "https://openrouter.ai/api/v1"

# Recommended headers for OpenRouter
HTTP_REFERER = "http://localhost:3000" # Replace with your actual app URL in production
APP_NAME = "Describo"

def generate_description(product_title: str, features: list, tone: str) -> str:
    """Generates a product description using the OpenRouter API."""
    try:
        feature_string = ", ".join(features)
        
        # Using ChatCompletion for better compatibility with modern models
        response = openai.ChatCompletion.create(
            model="openai/gpt-3.5-turbo", # Or another model like "mistralai/mistral-7b-instruct"
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert copywriter specializing in compelling Etsy product descriptions."
                },
                {
                    "role": "user",
                    "content": (
                        f"Generate a compelling and {tone} product description for an Etsy listing.\n\n"
                        f"Product Title: {product_title}\n"
                        f"Key Features: {feature_string}\n\n"
                        f"The description should be engaging, easy to read, and optimized for Etsy's platform. "
                        f"Use paragraphs and bullet points for clarity. Do not include a title or any introductory sentence like 'Here is a description...'"
                    )
                }
            ],
            headers={
                "HTTP-Referer": HTTP_REFERER,
                "X-Title": APP_NAME,
            }
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"Error generating description: {e}")
        return None