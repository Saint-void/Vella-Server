import os
import time
import uuid

import weaviate

# ============================
# LAZY WEAVIATE CLIENT / EMBEDDER
# ============================
CLASS_NAME = "VellaMemory"
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_RETRY_SECONDS = int(os.getenv("WEAVIATE_RETRY_SECONDS", "30"))

_client = None
_embedder = None
_next_client_retry_at = 0.0


def _get_client():
    global _client, _next_client_retry_at

    if _client is not None:
        return _client

    now = time.time()
    if now < _next_client_retry_at:
        return None

    try:
        _client = weaviate.Client(url=WEAVIATE_URL, startup_period=2)
        print(f"✅ Weaviate connected at {WEAVIATE_URL}")
        return _client
    except Exception as e:
        _next_client_retry_at = now + WEAVIATE_RETRY_SECONDS
        print(f"⚠️ Weaviate unavailable at {WEAVIATE_URL}; memory disabled for now: {e}")
        return None


def _get_embedder():
    global _embedder

    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder

# ============================
# SCHEMA SETUP
# ============================
def setup_schema():
    client = _get_client()
    if client is None:
        return

    if client.schema.exists(CLASS_NAME):
        return

    client.schema.create_class({
        "class": CLASS_NAME,
        "vectorizer": "none",
        "properties": [
            {"name": "text", "dataType": ["text"]},
            {"name": "user_id", "dataType": ["text"]},
            {"name": "timestamp", "dataType": ["date"]},
        ],
    })

# ============================
# ADD MEMORY
# ============================
def add_memory(text: str, user_id: str):
    client = _get_client()
    if client is None:
        return

    embedder = _get_embedder()
    vector = embedder.encode(text).tolist()

    client.data_object.create(
        data_object={
            "text": text,
            "user_id": user_id,
        },
        class_name=CLASS_NAME,
        uuid=str(uuid.uuid4()),
        vector=vector,
    )

# ============================
# SEARCH MEMORY
# ============================
def search_memory(prompt: str, user_id: str, fallback_count: int = 5) -> list[str]:
    """
    Return a list of previous conversation texts for this user.
    Falls back to last N memories if semantic search returns nothing.
    """
    client = _get_client()
    if client is None:
        return []

    try:
        # Try semantic search
        results = client.query.get(CLASS_NAME, ["text", "user_id"]) \
            .with_near_text({"concepts": [prompt]}) \
            .with_limit(fallback_count) \
            .do()

        memories = []
        if results and "data" in results:
            get_block = results["data"].get("Get", {})
            if CLASS_NAME in get_block:
                memories = [
                    m["text"] for m in get_block[CLASS_NAME]
                    if m.get("user_id") == user_id
                ]

        # If semantic search failed or empty, fallback to last N memories
        if not memories:
            raw_objects_resp = client.data_object.get(CLASS_NAME, ["text", "user_id", "timestamp"])
            raw_objects = raw_objects_resp.get("objects", []) if raw_objects_resp else []

            memories = [
                obj["properties"]["text"]
                for obj in sorted(raw_objects, key=lambda x: x["properties"].get("timestamp", ""), reverse=True)
                if obj["properties"].get("user_id") == user_id
            ][:fallback_count]

        return memories

    except Exception as e:
        print("Weaviate query failed:", e)
        return []
