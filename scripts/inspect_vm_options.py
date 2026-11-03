"""Read-only VM quota/SKU/official-price inspection, without printing credentials."""
import json
from pathlib import Path
import sys

import httpx
from azure.identity import AzureCliCredential

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import Settings,ROOT

settings=Settings.from_env()
subscription=settings.azure_subscription
region="eastasia"
credential=AzureCliCredential(subscription=subscription,process_timeout=30)
token=credential.get_token("https://management.azure.com/.default").token
client=httpx.Client(timeout=45,headers={"Authorization":f"Bearer {token}"})
base=f"https://management.azure.com/subscriptions/{subscription}/providers/Microsoft.Compute"
quota=client.get(f"{base}/locations/{region}/usages",params={"api-version":"2024-03-01"})
quota.raise_for_status()
nonzero=[{"name":q["name"]["value"],"current":q["currentValue"],"limit":q["limit"]}
    for q in quota.json()["value"] if q["limit"]>0]
print(json.dumps({"region":region,"nonzero_quota":nonzero}),flush=True)
target_names={"Standard_D2as_v4","Standard_D2s_v3","Standard_B2as_v2"}
url=f"{base}/skus"
params={"api-version":"2021-07-01","$filter":f"location eq '{region}'"}
found=[]
for _ in range(15):
    response=client.get(url,params=params)
    response.raise_for_status()
    page=response.json()
    for item in page["value"]:
        if item["name"] in target_names and item["resourceType"]=="virtualMachines":
            found.append({"name":item["name"],"family":item.get("family"),"restrictions":item.get("restrictions",[])})
    url=page.get("nextLink")
    params=None
    if not url or len({i['name'] for i in found})==len(target_names):
        break
print(json.dumps({"skus":found}),flush=True)
prices=[]
# Public price calls deliberately use a separate client with NO Authorization header.
for sku in ["Standard_D2as_v4"]:
    query=f"serviceName eq 'Virtual Machines' and armRegionName eq '{region}' and armSkuName eq '{sku}' and priceType eq 'Consumption'"
    price=httpx.get("https://prices.azure.com/api/retail/prices",params={"$filter":query},timeout=45)
    price.raise_for_status()
    for item in price.json()["Items"]:
        if "Windows" not in item["productName"] and "Spot" not in item["skuName"] and "Low Priority" not in item["skuName"]:
            prices.append({k:item.get(k) for k in ["armSkuName","productName","skuName","retailPrice","currencyCode","unitOfMeasure"]})
result={"region":region,"quota":nonzero,"skus":found,"public_linux_compute_prices":prices}
(ROOT / "infra" / "vm-options.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps({"public_linux_compute_prices":prices}),flush=True)
client.close()
credential.close()
