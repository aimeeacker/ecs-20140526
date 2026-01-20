import datetime
import os
import sys
from typing import Dict, Iterable, Optional, Tuple

from alibabacloud_bssopenapi20171214 import models as bss_models
from alibabacloud_bssopenapi20171214.client import Client as BssClient
from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_credentials.models import Config as CredentialConfig
from alibabacloud_tea_openapi import models as open_api_models


def build_bss_client() -> BssClient:
    region_id = os.getenv("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou")
    endpoint = os.getenv("ALIBABA_CLOUD_BSS_ENDPOINT", "business.aliyuncs.com")
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
        endpoint=endpoint,
    )
    return BssClient(config)


def hour_window(hours: int = 24) -> Tuple[str, str]:
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    end = now.replace(minute=0, second=0, microsecond=0)
    start = end - datetime.timedelta(hours=hours)
    return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")


def fetch_savings_plan_usage(
    client: BssClient, start_period: str, end_period: str
) -> Iterable[bss_models.DescribeSavingsPlansUsageDetailResponseBodyDataItems]:
    token = None
    while True:
        request = bss_models.DescribeSavingsPlansUsageDetailRequest(
            start_period=start_period,
            end_period=end_period,
            period_type="HOUR",
            max_results=300,
            token=token,
        )
        response = client.describe_savings_plans_usage_detail(request)
        body = response.body
        if not body or not body.data:
            return
        for item in body.data.items or []:
            yield item
        token = body.data.next_token
        if not token:
            return


def fetch_resource_usage(
    client: BssClient, start_period: str, end_period: str, resource_type: str
) -> Iterable[bss_models.DescribeResourceUsageDetailResponseBodyDataItems]:
    next_token = None
    while True:
        request = bss_models.DescribeResourceUsageDetailRequest(
            start_period=start_period,
            end_period=end_period,
            period_type="HOUR",
            resource_type=resource_type,
            max_results=300,
            next_token=next_token,
        )
        response = client.describe_resource_usage_detail(request)
        body = response.body
        if not body or not body.data:
            return
        for item in body.data.items or []:
            yield item
        next_token = body.data.next_token
        if not next_token:
            return


def aggregate_costs(
    items: Iterable[object], time_attr: str, cost_attr: str
) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for item in items:
        time_value = getattr(item, time_attr, None)
        cost_value = getattr(item, cost_attr, None)
        if not time_value or cost_value is None:
            continue
        try:
            cost = float(cost_value)
        except (TypeError, ValueError):
            continue
        totals[time_value] = totals.get(time_value, 0.0) + cost
    return totals


def first_currency(items: Iterable[object], attr: str) -> Optional[str]:
    for item in items:
        value = getattr(item, attr, None)
        if value:
            return value
    return None


def print_totals(title: str, totals: Dict[str, float], currency: Optional[str]) -> None:
    if not totals:
        print(f"{title}: no data")
        return
    label = f" ({currency})" if currency else ""
    print(f"{title}{label}")
    for hour in sorted(totals.keys()):
        print(f"  {hour}: {totals[hour]:.6f}")


def main() -> None:
    client = build_bss_client()
    start_period, end_period = hour_window(24)
    print(f"Period: {start_period} -> {end_period} (Asia/Shanghai)")

    savings_items = list(fetch_savings_plan_usage(client, start_period, end_period))
    savings_currency = first_currency(savings_items, "currency")
    savings_totals = aggregate_costs(savings_items, "start_period", "postpaid_cost")
    print_totals("SavingsPlans postpaid_cost", savings_totals, savings_currency)

    for resource_type in ("RI", "SCU"):
        resource_items = list(
            fetch_resource_usage(client, start_period, end_period, resource_type)
        )
        resource_currency = first_currency(resource_items, "currency")
        resource_totals = aggregate_costs(resource_items, "start_time", "postpaid_cost")
        print_totals(
            f"{resource_type} postpaid_cost",
            resource_totals,
            resource_currency,
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise
