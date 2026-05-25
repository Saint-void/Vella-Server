import os
from huggingface_hub import hf_hub_download

# Dynamic path resolution: Models are in a sibling folder 'models' to 'Vella-Server'
BASE_MODELS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))
gguf_path = os.path.join(BASE_MODELS_PATH, "gemma-3-1b-it-gguf")

# 2. The Base Repo (for tokenizer)
base_repo = "google/gemma-3-1b-it"

print(f"🚀 Fetching missing tokenizer files from {base_repo}...")
print(f"📂 Target directory: {gguf_path}")

tokenizer_files = [
    "tokenizer.model",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "config.json"
]

try:
    os.makedirs(gguf_path, exist_ok=True)
    
    for file in tokenizer_files:
        print(f"📥 Downloading {file}...")
        hf_hub_download(
            repo_id=base_repo,
            filename=file,
            local_dir=gguf_path
        )
    
    print("\n✅ Tokenizer files downloaded successfully!")

except Exception as e:
    print(f"\n❌ Error: {e}")
