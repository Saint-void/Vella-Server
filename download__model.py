import os
from huggingface_hub import hf_hub_download, snapshot_download

# 1. The GGUF Repo (already has the weights)
gguf_path = r"V:/Document/Vella-Modes/models/gemma-3-1b-it-gguf"
# 2. The Base Repo (for tokenizer)
base_repo = "google/gemma-3-1b-it"

print(f"🚀 Fetching missing tokenizer files from {base_repo}...")

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
            local_dir=gguf_path,
            local_dir_use_symlinks=False
        )
    
    print("\n✅ Tokenizer files downloaded successfully!")

except Exception as e:
    print(f"\n❌ Error: {e}")
