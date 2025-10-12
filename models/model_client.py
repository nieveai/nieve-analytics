from abc import ABC, abstractmethod
import google.generativeai as genai
import logging
import openai

class BaseModelClient(ABC):
    @abstractmethod
    def generate_content(self, prompt):
        pass

class GeminiClient(BaseModelClient):
    def __init__(self, model_name, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        logging.info(f"Gemini client initialized with model: {model_name}")

    def generate_content(self, prompt):
        response = self.model.generate_content(prompt)
        return response.text.strip()

class OpenAIClient(BaseModelClient):
    def __init__(self, model_name, api_key, base_url=None):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url
        logging.info(f"OpenAI client initialized with model: {model_name} and base_url: {base_url}")

    def generate_content(self, prompt):
        # Check if the new OpenAI API (>= 1.0) is available
        if hasattr(openai, "OpenAI"):
            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip()
        else:
            # Legacy API for openai < 1.0
            openai.api_key = self.api_key
            if self.base_url:
                openai.api_base = self.base_url
            response = openai.Completion.create(
                engine=self.model_name,
                prompt=prompt,
                max_tokens=2048,
                n=1,
                stop=None,
                temperature=0.5,
            )
            return response.choices[0].text.strip()

class ModelClient:
    _client = None

    @classmethod
    def initialize(cls, model_provider, model_name, api_key, base_url=None):
        logging.info(f"Initializing model client for provider: {model_provider}")
        if model_provider == 'gemini':
            cls._client = GeminiClient(model_name, api_key)
        elif model_provider == 'openai':
            cls._client = OpenAIClient(model_name, api_key, base_url)
        else:
            raise ValueError(f"Unsupported model provider: {model_provider}")
        logging.info("Model client initialized successfully.")


    @classmethod
    def get_client(cls):
        if cls._client is None:
            raise RuntimeError("ModelClient has not been initialized. Please call initialize() first.")
        return cls._client
