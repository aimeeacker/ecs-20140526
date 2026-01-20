import asyncio
import os
import sys

from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_credentials.models import Config as CredentialConfig
from alibabacloud_ecs20140526 import models as ecs_models
from alibabacloud_ecs20140526.client import Client as EcsClient
from alibabacloud_tea_openapi import models as open_api_models


async def main() -> None:
    region_id = os.getenv("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou")
    endpoint = os.getenv("ALIBABA_CLOUD_ENDPOINT")
    zone_id = os.getenv("ALIBABA_CLOUD_ZONE_ID")
    image_id = os.getenv("ALIBABA_CLOUD_IMAGE_ID")

    role_name = os.getenv("ALIBABA_CLOUD_ECS_ROLE_NAME")
    disable_imds_v1 = os.getenv("ALIBABA_CLOUD_DISABLE_IMDS_V1", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    credentials_config = CredentialConfig(
        type="ecs_ram_role",
        role_name=role_name,
        disable_imds_v1=disable_imds_v1,
    )
    credentials_client = CredentialClient(credentials_config)

    config = open_api_models.Config(
        credential=credentials_client,
        region_id=region_id,
    )
    if endpoint:
        config.endpoint = endpoint

    client = EcsClient(config)

    system_disk = ecs_models.DescribePriceRequestSystemDisk(
        category="cloud_essd_entry",
        size=20,
    )

    request = ecs_models.DescribePriceRequest(
        resource_type="instance",
        instance_type="ecs.u1-c1m8.2xlarge",
        spot_strategy="SpotAsPriceGo",
        spot_duration=0,
        system_disk=system_disk,
        price_unit="Hour",
        region_id=region_id,
        zone_id=zone_id,
        image_id=image_id,
    )

    response = await client.describe_price_async(request)
    if response.body:
        print(response.body.to_map())
    else:
        print(response)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise
