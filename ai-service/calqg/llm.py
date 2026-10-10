"""LLM clients: Gemini, OpenAI, or an offline Mock that lets the whole pipeline run without keys.

The Mock is NOT a question generator for real use. It deterministically injects the
error types real LLMs make (wrong Bloom verb, paraphrased/unfaithful evidence) so the
validation -> failure-memory -> regeneration loop can be exercised and unit-tested offline.
"""
import json, os, re, hashlib
from .ingest import split_sentences

GEN_PROMPT = """You are an expert {subject} examiner. Write ONE exam question.

Target concept: {concept}
Target Bloom level: {bloom}  (begin the question with a verb typical of this level)
Target difficulty: {difficulty}
Question type: {qtype}

Use ONLY the source material below. Copy the evidence sentence(s) VERBATIM from it.

SOURCE MATERIAL:
{context}

{constraints}

Return ONLY JSON, no markdown:
{{"question": "...", "answer": "...", "evidence": "<verbatim sentence(s) from source>",
  "bloom": "{bloom}", "concept": "{concept}", "question_type": "{qtype}"}}"""

BLOOM_TEMPLATES = {
    "Remember":   "Define {c} in Java.",
    "Understand": "Explain the purpose of {c} in object-oriented programming.",
    "Apply":      "Write a short Java program that demonstrates {c}.",
    "Analyze":    "Differentiate between {c} and {o} with suitable examples.",
    "Evaluate":   "Justify when {c} should be preferred over {o} in a Java design.",
    "Create":     "Design a Java class structure that uses {c} for a library management system.",
}


def _parse_json(text):
    text = re.sub(r"```(json)?", "", text).strip()
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


class BaseLLM:
    name = "base"
    def generate_question(self, slot, context_chunks, constraints, attempt):
        ctx = "\n---\n".join(c["text"] for c in context_chunks)
        cons = ("CONSTRAINTS LEARNED FROM PREVIOUS FAILURES (must follow):\n- " +
                "\n- ".join(constraints)) if constraints else ""
        prompt = GEN_PROMPT.format(subject=slot.get("subject", "Java"), concept=slot["concept"],
                                   bloom=slot["bloom"], difficulty=slot["difficulty_label"],
                                   qtype=slot["qtype"], context=ctx, constraints=cons)
        return _parse_json(self.complete(prompt))
    def complete(self, prompt):
        raise NotImplementedError


class GroqLLM(BaseLLM):
    name = "groq"
    def __init__(self, model):
        from groq import Groq
        self.c, self.model = Groq(api_key=os.environ["GROQ_API_KEY"]), model
    def complete(self, prompt):
        r = self.c.chat.completions.create(model=self.model, temperature=0.4,
                                           messages=[{"role": "user", "content": prompt}])
        return r.choices[0].message.content


class GeminiLLM(BaseLLM):
    name = "gemini"
    def __init__(self, model):
        self.model = model
        self.use_openai_compat = False
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.environ["GEMINI_API_KEY"])
            self.m = genai.GenerativeModel(model)
        except Exception:
            from openai import OpenAI
            self.c = OpenAI(
                api_key=os.environ["GEMINI_API_KEY"],
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            self.use_openai_compat = True

    def complete(self, prompt):
        if self.use_openai_compat:
            r = self.c.chat.completions.create(model=self.model, temperature=0.4,
                                               messages=[{"role": "user", "content": prompt}])
            return r.choices[0].message.content
        return self.m.generate_content(prompt).text


class OpenAILLM(BaseLLM):
    name = "openai"
    def __init__(self, model):
        from openai import OpenAI
        self.c, self.model = OpenAI(), model
    def complete(self, prompt):
        r = self.c.chat.completions.create(model=self.model, temperature=0.4,
                                           messages=[{"role": "user", "content": prompt}])
        return r.choices[0].message.content


class MockLLM(BaseLLM):
    name = "mock"

    @staticmethod
    def _h(*parts):
        return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest(), 16)

    def generate_question(self, slot, context_chunks, constraints, attempt):
        c, bloom = slot["concept"], slot["bloom"]
        cons = " ".join(constraints).lower()
        sents = [s for ch in context_chunks for s in split_sentences(ch["text"])]
        # prefer definitional sentences (concept appears early)
        rel = sorted([s for s in sents if c.lower() in s.lower()],
                     key=lambda s: s.lower().find(c.lower())) or sents
        avoid = set(slot.get("avoid_evidence", []))
        rel = [s for s in rel if s not in avoid] or rel
        ev = rel[(self._h(c, bloom) + attempt) % len(rel)]
        other = next((x for x in slot.get("related", []) if x != c), "a related concept")
        o_sent = next((s for s in sents if other.lower() in s.lower() and s != ev), None)

        # Realistic, seeded LLM failure modes (suppressed once a learned constraint forbids them)
        r = self._h(c, bloom, attempt, slot.get("seed", 0)) % 100
        used_bloom = bloom
        if r < 35 and "bloom" not in cons:
            used_bloom = "Remember" if bloom != "Remember" else "Understand"
        evidence = ev
        if 35 <= r < 60 and "verbatim" not in cons:
            evidence = "In general, " + ev.lower().replace(" is ", " can be seen as ", 1)

        q = BLOOM_TEMPLATES[used_bloom].format(c=c, o=other)
        ans = ev if bloom not in ("Analyze", "Evaluate") or not o_sent else ev + " " + o_sent
        if bloom in ("Analyze", "Evaluate") and o_sent and evidence == ev:
            evidence = ev + " " + o_sent
        return {"question": q, "answer": ans, "evidence": evidence, "bloom": bloom,
                "concept": c, "question_type": slot["qtype"]}


class FallbackLLM(BaseLLM):
    """Wrapper that tries primary LLM, and on failure (e.g. Rate Limit 429), falls back to secondary LLMs or MockLLM."""
    def __init__(self, llms):
        self.llms = llms
        self.name = f"fallback({','.join(l.name for l in llms)})"

    def complete(self, prompt):
        last_err = None
        for llm in self.llms:
            try:
                return llm.complete(prompt)
            except Exception as e:
                last_err = e
                print(f"[LLM Fallback Warning] {llm.name} failed: {e}. Trying next provider...")
        if last_err:
            raise last_err

    def generate_question(self, slot, context_chunks, constraints, attempt):
        last_err = None
        for llm in self.llms:
            try:
                return llm.generate_question(slot, context_chunks, constraints, attempt)
            except Exception as e:
                last_err = e
                print(f"[LLM Fallback Warning] {llm.name} failed: {e}. Trying next provider...")
        if last_err:
            raise last_err


def make_llm(provider="auto", cfg=None):
    from .config import Config
    if cfg is None:
        cfg = Config()
    
    candidates = []
    if provider in ("auto", "groq") and os.getenv("GROQ_API_KEY"):
        try:
            candidates.append(GroqLLM(cfg.groq_model))
        except Exception as e:
            print(f"[LLM Init Warning] Failed to init GroqLLM: {e}")
    if provider in ("auto", "gemini") and os.getenv("GEMINI_API_KEY"):
        try:
            candidates.append(GeminiLLM(cfg.gemini_model))
        except Exception as e:
            print(f"[LLM Init Warning] Failed to init GeminiLLM: {e}")
    if provider in ("auto", "openai") and os.getenv("OPENAI_API_KEY"):
        try:
            candidates.append(OpenAILLM(cfg.openai_model))
        except Exception as e:
            print(f"[LLM Init Warning] Failed to init OpenAILLM: {e}")

    candidates.append(MockLLM())

    if len(candidates) == 1:
        return candidates[0]
    return FallbackLLM(candidates)

