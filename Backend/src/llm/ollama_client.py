"""Client Ollama — OrchestratorAgent (Mistral 8B quantifié)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from loguru import logger


class OllamaClient:
    """Inférence locale via Ollama (mistral:v0.3, Q4_K_M ~4-bit)."""

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
        keep_alive: str = "5m",
    ) -> None:
        self.model = model or os.getenv("ORCHESTRATOR_LLM_MODEL", "mistral:v0.3")
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.keep_alive = keep_alive

    def _post(self, path: str, payload: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
        url = f"{self.host}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            data = self._post(
                "/api/chat",
                {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "keep_alive": self.keep_alive,
                    "options": {
                        "temperature": float(os.getenv("ORCHESTRATOR_TEMPERATURE", "0.1")),
                        "num_ctx": int(os.getenv("ORCHESTRATOR_NUM_CTX", "4096")),
                    },
                },
            )
            return data.get("message", {}).get("content", "")
        except URLError as e:
            logger.warning(f"Ollama chat failed: {e}")
            return ""

    def plan_pipeline(self, patient_id: str, has_fastq: bool, has_vcf: bool) -> Dict[str, Any]:
        system = (
            "Tu es l'orchestrateur clinique du pipeline Zaynb (cancer du sein). "
            "Réponds en JSON compact uniquement."
        )
        prompt = (
            f"Patient={patient_id} fastq={has_fastq} vcf={has_vcf}. "
            "Étapes: data_manager, parabricks, vcf_analysis, llm_training(optional), "
            "prediction(BioGPT), report. Confirme l'ordre séquentiel."
        )
        raw = self.generate(prompt, system=system)
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
        steps = ["data_manager", "parabricks", "vcf_analysis", "prediction", "report"]
        if has_vcf:
            steps = ["data_manager", "vcf_analysis", "prediction", "report"]
        return {"patient_id": patient_id, "steps": steps, "source": "fallback"}

    def validate_step(self, step: str, context_summary: str) -> bool:
        prompt = (
            f"Étape courante: {step}. Contexte: {context_summary}. "
            "Réponds GO si les prérequis sont satisfaits, sinon NO."
        )
        reply = self.generate(prompt).strip().upper()
        return "GO" in reply or reply == ""
