import os
import base64
import json
from dotenv import load_dotenv
from openai import OpenAI
import re

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def encode_image(image_path: str):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        print(f"Error encoding image: {e}")
        return None

def image_to_text(image_path: str):
    """
    Extracts all text and a detailed description from the image using OpenAI Vision API.
    Returns:
        str: Combined extracted text and image description.
    """
    try:
        base64_image = encode_image(image_path)
        if not base64_image:
            return ""
        file_extension = os.path.splitext(image_path)[1][1:]
        image_type = file_extension if file_extension else "png"
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "1. Extract all text from the image. 2. Describe the image contextually in detail. Respond in JSON with keys 'extracted_text' and 'image_description'."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1024,
        )
        content = response.choices[0].message.content
        # Try to extract JSON block if present
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            json_str = content  # fallback

        try:
            image_json = json.loads(json_str)
        except Exception as e:
            print(f"Could not parse JSON: {e}\nContent was:\n{content}")
            return ""

        extracted_text = image_json.get("extracted_text", "")
        image_description = image_json.get("image_description", "")
        text_response = extracted_text + "\n" + image_description
        return text_response.strip()
    except Exception as e:
        print(f"Error extracting text from image: {e}")
        return ""

def audio_to_text(audio_path: str):
    """
    Extracts text from audio using OpenAI Whisper API.
    Returns:
        str: Transcribed audio text.
    """
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        with open(audio_path, "rb") as audio_file:
            translation = client.audio.translations.create(
                model="whisper-1",
                file=audio_file,
            )
        return translation.text
    except Exception as e:
        print(f"Error extracting text from audio: {e}")
        return ""

def video_to_text(video_path: str):
    """
    Placeholder for extracting text from video.
    Returns:
        str: Extracted text from video (not implemented).
    """
    print("Video to text extraction is not implemented yet.")
    return ""

# text = image_to_text("dummy_data/image.jpg")

# print(text)