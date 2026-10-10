import os
from dataclasses import dataclass, field

def load_env(env_path=None):
    """Locate and load .env file into os.environ if present."""
    paths = [
        env_path,
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    ]
    for p in paths:
        if p and os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip()
            break

load_env()

BLOOM_LEVELS = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]

@dataclass
class Config:
    llm_provider: str = field(default_factory=lambda: os.getenv("CALQG_LLM", "auto"))   # auto | groq | gemini | openai | mock
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    # A *different* model/provider for validation avoids self-evaluation bias
    validator_provider: str = field(default_factory=lambda: os.getenv("CALQG_VALIDATOR_LLM", "auto"))
    chunk_size: int = 700
    chunk_overlap: int = 100
    top_k: int = 4
    quality_threshold: float = 0.70
    max_attempts: int = 4
    redundancy_threshold: float = 0.85
    weights: dict = field(default_factory=lambda: {
        "relevance": 0.15, "answerability": 0.20, "grounding": 0.25,
        "bloom": 0.15, "difficulty": 0.10, "grammar": 0.05, "redundancy": 0.10,
    })
    # Hard gates: a question can never pass if these fail, whatever its total score
    hard_gates: tuple = ("answerability", "grounding", "bloom", "redundancy")
    # Ablation switches
    use_failure_memory: bool = True
    use_irt_calibration: bool = True
    use_coverage_planner: bool = True
