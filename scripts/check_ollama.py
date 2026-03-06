import os
import json
from ollama import Client
from dotenv import load_dotenv

load_dotenv()
hosts = [os.getenv("OLLAMA_HOST", "https://ollama.com"), "http://localhost:11434"]
for host in hosts:
    print(f"\nChecking models on host: {host}")
    try:
        client = Client(host=host)
        models_resp = client.list()
        # The response is usually a ModelResponse or list of Model objects
        models = getattr(models_resp, 'models', models_resp)
        print("Available models:")
        for m in models:
            name = getattr(m, 'model', getattr(m, 'name', str(m)))
            print(f" - {name}")
    except Exception as e:
        print(f"Error listing models on {host}: {e}")
