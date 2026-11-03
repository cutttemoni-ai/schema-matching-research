"""Create public-only SSH material; no private SSH key is retained."""
from pathlib import Path
import json
import sys
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT

runtime=ROOT / ".runtime"
runtime.mkdir(exist_ok=True)
key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
public=key.public_key().public_bytes(serialization.Encoding.OpenSSH,serialization.PublicFormat.OpenSSH).decode()
del key
params={"$schema":"https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
    "contentVersion":"1.0.0.0","parameters":{"sshPublicKey":{"value":public},
    "cloudInit":{"value":(ROOT / "infra" / "install-model.sh").read_text(encoding="utf-8")}}}
(runtime / "vm.parameters.json").write_text(json.dumps(params),encoding="utf-8")
print("VM parameters prepared. Only public SSH key retained; inbound Internet ports denied.")
