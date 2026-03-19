from llama_cpp import Llama
from typing import Any, Iterator

# Load model once
llm = Llama(
    model_path= r"V:\Document\Vella-Modes\models\volco_llm\TinyLlama_1_1B_Chat_v1_0_Q4_K_M.gguf",
    n_ctx=2048,
    n_threads=4,
    verbose=False
)

def stream_generate(prompt: str) -> Iterator[str]:
    """Yields tokens with explicit typing to fix Pylance errors."""
    
    stream: Any = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": "You are Volco, a voice assistant. Be brief and friendly."},
            {"role": "user", "content": prompt}
        ],
        stream=True,
        max_tokens=80
    )

    for chunk in stream:
        # Use .get() safely and ignore type-checking for this line
        delta = chunk['choices'][0].get('delta', {}) # type: ignore
        if 'content' in delta:
            content = delta['content']
            if content:
                yield str(content)