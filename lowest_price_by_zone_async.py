import asyncio
import os
import sys
from typing import Dict, List, Optional

from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_credentials.models import Config as CredentialConfig
from alibabacloud_ecs20140526 import models as ecs_models
from alibabacloud_ecs20140526.client import Client as EcsClient
from alibabacloud_tea_openapi import models as open_api_models


TARGET_REGIONS = [
    "ap-northeast-1",  # Tokyo
    "cn-hongkong",     # Hong Kong
    "ap-southeast-1",  # Singapore
    "us-west-1",       # US West
    "us-east-1",       # US East
]

REGION_LABELS = {
    "ap-northeast-1": "Tokyo",
    "cn-hongkong": "Hong Kong",
    "ap-southeast-1": "Singapore",
    "us-west-1": "US West",
    "us-east-1": "US East",
}

INSTANCE_TYPE = "ecs.e-c1m1.large"
RESOURCE_TYPE = "instance"
SPOT_STRATEGY = "SpotAsPriceGo"
SPOT_DURATION = 0
SYSTEM_DISK_CATEGORY = "cloud_essd_entry"
SYSTEM_DISK_SIZE = 20
PRICE_UNIT = "Hour"


def build_credentials_client() -> CredentialClient:
    role_name = os.getenv("ALIBABA_CLOUD_ECS_ROLE_NAME")
    disable_imds_v1 = os.getenv("ALIBABA_CLOUD_DISABLE_IMDS_V1", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    credentials_config = CredentialConfig(
        type="ecs_ram_role",
        role_name=role_name,
        disable_imds_v1=disable_imds_v1,
    )
    return CredentialClient(credentials_config)


def build_client(
    region_id: str,
    access_key_id: str,
    access_key_secret: str,
    security_token: Optional[str],
    endpoint: Optional[str],
) -> EcsClient:
    config = open_api_models.Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        region_id=region_id,
    )
    if security_token:
        config.security_token = security_token
    if endpoint:
        config.endpoint = endpoint
    return EcsClient(config)


def zone_supports_instance(zone: ecs_models.DescribeZonesResponseBodyZonesZone) -> bool:
    available = zone.available_instance_types
    if not available or not available.instance_types:
        return True
    return INSTANCE_TYPE in available.instance_types


async def fetch_zones(
    client: EcsClient,
    region_id: str,
) -> List[str]:
    request = ecs_models.DescribeZonesRequest(
        region_id=region_id,
        instance_charge_type="PostPaid",
        spot_strategy=SPOT_STRATEGY,
        verbose=True,
    )
    response = await client.describe_zones_async(request)
    zones: List[str] = []
    if response.body and response.body.zones and response.body.zones.zone:
        for zone in response.body.zones.zone:
            if not zone or not zone.zone_id:
                continue
            if not zone_supports_instance(zone):
                continue
            zones.append(zone.zone_id)
    return zones


async def fetch_price(
    sem: asyncio.Semaphore,
    client: EcsClient,
    region_id: str,
    zone_id: str,
) -> Optional[Dict[str, object]]:
    async with sem:
        try:
            system_disk = ecs_models.DescribePriceRequestSystemDisk(
                category=SYSTEM_DISK_CATEGORY,
                size=SYSTEM_DISK_SIZE,
            )
            request = ecs_models.DescribePriceRequest(
                resource_type=RESOURCE_TYPE,
                instance_type=INSTANCE_TYPE,
                spot_strategy=SPOT_STRATEGY,
                spot_duration=SPOT_DURATION,
                system_disk=system_disk,
                price_unit=PRICE_UNIT,
                region_id=region_id,
                zone_id=zone_id,
            )
            response = await client.describe_price_async(request)
            if not response.body or not response.body.price_info or not response.body.price_info.price:
                return None
            price_info = response.body.price_info.price
            if price_info.trade_price is None:
                return None
            return {
                "region_id": region_id,
                "zone_id": zone_id,
                "trade_price": price_info.trade_price,
                "original_price": price_info.original_price,
                "discount_price": price_info.discount_price,
                "currency": price_info.currency,
            }
        except Exception as exc:
            msg = str(exc).splitlines()[0]
            print(f"Skip {region_id}/{zone_id}: {msg}", file=sys.stderr)
            return None


async def main() -> None:
    endpoint = os.getenv("ALIBABA_CLOUD_ENDPOINT")
    max_concurrency = int(os.getenv("MAX_CONCURRENCY", "10"))

    credentials_client = build_credentials_client()
    credential = credentials_client.get_credential()
    access_key_id = credential.get_access_key_id()
    access_key_secret = credential.get_access_key_secret()
    security_token = credential.get_security_token()
    clients = {
        region_id: build_client(
            region_id,
            access_key_id,
            access_key_secret,
            security_token,
            endpoint,
        )
        for region_id in TARGET_REGIONS
    }

    zone_tasks = [
        fetch_zones(clients[region_id], region_id)
        for region_id in TARGET_REGIONS
    ]
    zone_lists = await asyncio.gather(*zone_tasks, return_exceptions=True)

    zones_by_region: Dict[str, List[str]] = {}
    for region_id, zones in zip(TARGET_REGIONS, zone_lists):
        if isinstance(zones, Exception):
            msg = str(zones).splitlines()[0]
            print(f"Skip zones for {region_id}: {msg}", file=sys.stderr)
            continue
        zones_by_region[region_id] = zones

    sem = asyncio.Semaphore(max_concurrency)
    price_tasks = []
    for region_id, zones in zones_by_region.items():
        client = clients[region_id]
        for zone_id in zones:
            price_tasks.append(fetch_price(sem, client, region_id, zone_id))

    results = [r for r in await asyncio.gather(*price_tasks) if r]
    if not results:
        print("No price results.")
        return

    results.sort(key=lambda r: r["trade_price"])
    best = results[0]
    label = REGION_LABELS.get(best["region_id"], best["region_id"])
    print("Full price list (sorted by trade_price):")
    for item in results:
        region_label = REGION_LABELS.get(item["region_id"], item["region_id"])
        print(
            f"{item['region_id']} ({region_label}) {item['zone_id']} "
            f"trade_price={item['trade_price']} {item['currency']} "
            f"original_price={item['original_price']} "
            f"discount_price={item['discount_price']}"
        )
    print(
        f"Best: {best['region_id']} ({label}) {best['zone_id']} "
        f"trade_price={best['trade_price']} {best['currency']} "
        f"original_price={best['original_price']} "
        f"discount_price={best['discount_price']}"
    )
    print(f"Checked {len(results)} zone prices.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise
