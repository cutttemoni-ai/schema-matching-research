from dataclasses import dataclass
from pathlib import Path
import os
import math

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    provider: str = "vertex"
    project: str = ""
    location: str = "global"
    model: str = "gemini-3.8-flash"
    timeout_ms: int = 60000
    input_price: float | None = None
    output_price: float | None = None
    currency: str = "USD"
    azure_endpoint: str = ""
    azure_tenant: str = ""
    azure_subscription: str = ""
    azure_location: str = ""
    ollama_endpoint: str = "http://127.0.0.1:11434"
    local_timeout_seconds: int = 180
    azure_vm_name: str = "schema-match-llm-vm"
    azure_vm_resource_group: str = "schema-match-demo-rg"
    azure_vm_location: str = "eastasia"
    azure_vm_timeout_seconds: int = 600
    matching_preset: str = "compact_v1"
    azure_vm_transport: str = "rest"

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env")
        provider = os.getenv("LLM_PROVIDER", "vertex").strip()
        if provider not in {"azure", "vertex", "ollama", "azure_vm"}:
            raise ValueError("모델 제공자 설정이 올바르지 않습니다.")
        preset=os.getenv('MATCHING_PRESET','compact_v1')
        transport=os.getenv('AZURE_VM_TRANSPORT','rest')
        if preset not in {'compact_v1','baseline_v2'} or transport not in {'rest','cli'}:
            raise ValueError('매칭 프리셋 또는 VM 전송 설정이 올바르지 않습니다.')
        def price(key):
            value = os.getenv(key, "").strip()
            if not value:
                return None
            parsed = float(value)
            if not math.isfinite(parsed) or parsed < 0:
                raise ValueError(f"{key}: 단가는 0 이상이어야 합니다.")
            return parsed
        return cls(
            provider=provider,
            project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
            model=(os.getenv("OLLAMA_MODEL","qwen3:4b") if provider in {"ollama","azure_vm"} else
                os.getenv("AZURE_OPENAI_DEPLOYMENT", "") if provider == "azure" else os.getenv("GEMINI_MODEL", "gemini-3.8-flash")),
            input_price=price("INPUT_PRICE_PER_MILLION"),
            output_price=price("OUTPUT_PRICE_PER_MILLION"),
            currency=os.getenv("PRICE_CURRENCY", "USD"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_tenant=os.getenv("AZURE_TENANT_ID", ""),
            azure_subscription=os.getenv("AZURE_SUBSCRIPTION_ID", ""),
            azure_location=os.getenv("AZURE_LOCATION", ""),
            ollama_endpoint=os.getenv("OLLAMA_ENDPOINT","http://127.0.0.1:11434"),
            local_timeout_seconds=int(os.getenv("LOCAL_TIMEOUT_SECONDS","180")),
            azure_vm_name=os.getenv("AZURE_VM_NAME","schema-match-llm-vm"),
            azure_vm_resource_group=os.getenv("AZURE_VM_RESOURCE_GROUP","schema-match-demo-rg"),
            azure_vm_location=os.getenv("AZURE_VM_LOCATION","eastasia"),
            azure_vm_timeout_seconds=int(os.getenv("AZURE_VM_TIMEOUT_SECONDS","600")),
            matching_preset=preset,
            azure_vm_transport=transport,
        )
