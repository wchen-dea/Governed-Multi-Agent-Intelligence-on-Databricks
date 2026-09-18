import json
import os

import requests
from databricks.sdk.core import Config

# Set the name of the MLflow endpoint
endpoint_name = "prov-throughput-endpoint"

# Name of the registered MLflow model
model_name = "system.ai.databricks-qwen35-122b-a10b"

# Get the latest version of the MLflow model
model_version = 1

# Resolve host + auth from the Databricks CLI profile; never hardcode tokens.
config = Config(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "DEFAULT"))
API_ROOT = config.host
headers = {"Content-Type": "application/json", **config.authenticate()}

optimize_response = requests.get(
    url=f"{API_ROOT}/api/2.0/serving-endpoints/get-model-optimization-info/{model_name}/{model_version}",
    headers=headers,
)
optimizable_info = optimize_response.json()

if "optimizable" not in optimizable_info or not optimizable_info["optimizable"]:
    reason = (
        optimizable_info.get("message") or optimizable_info.get("error_code") or optimizable_info
    )
    raise ValueError(f"Model is not eligible for provisioned throughput: {reason}")

# Newer foundation models are optimized in model units instead of throughput
# bands, which requires a different served-entity field and create endpoint.
if "model_unit_chunk_size" in optimizable_info:
    chunk_size = optimizable_info["model_unit_chunk_size"]
    desired_model_units = 2 * chunk_size
    data = {
        "name": endpoint_name,
        "config": {
            "served_entities": [
                {
                    "entity_name": model_name,
                    "entity_version": model_version,
                    "provisioned_model_units": desired_model_units,
                }
            ]
        },
    }
    create_url = f"{API_ROOT}/api/2.0/serving-endpoints/pt"
else:
    chunk_size = optimizable_info["throughput_chunk_size"]

    # Minimum desired provisioned throughput
    min_provisioned_throughput = 2 * chunk_size

    # Maximum desired provisioned throughput
    max_provisioned_throughput = 3 * chunk_size

    # Send the POST request to create the serving endpoint
    data = {
        "name": endpoint_name,
        "config": {
            "served_entities": [
                {
                    "entity_name": model_name,
                    "entity_version": model_version,
                    "min_provisioned_throughput": min_provisioned_throughput,
                    "max_provisioned_throughput": max_provisioned_throughput,
                }
            ]
        },
    }
    create_url = f"{API_ROOT}/api/2.0/serving-endpoints"

response = requests.post(url=create_url, json=data, headers=headers)

print(json.dumps(response.json(), indent=4))
