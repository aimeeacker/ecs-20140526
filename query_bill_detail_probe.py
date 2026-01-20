import datetime
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

from alibabacloud_bssopenapi20171214.client import Client as BssClient
from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_credentials.models import Config as CredentialConfig
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_openapi_util.client import Client as OpenApiUtilClient


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


def time_window(hours: int = 24) -> Tuple[str, str]:
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    end = now.replace(minute=0, second=0, microsecond=0)
    start = end - datetime.timedelta(hours=hours)
    return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")


def billing_cycle_and_date() -> Tuple[str, str]:
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    return now.strftime("%Y-%m"), now.strftime("%Y-%m-%d")


def summarize_response(label: str, payload: Dict[str, Any]) -> None:
    top_keys = sorted(payload.keys())
    print(f"{label} top-level keys: {', '.join(top_keys)}")

    body = payload.get("body")
    if isinstance(body, dict):
        payload = body
        print(f"{label} body keys: {', '.join(sorted(payload.keys()))}")

    summary_keys = ["Code", "Message", "RequestId", "Success", "TotalCount", "NextToken"]
    summary = {k: payload.get(k) for k in summary_keys if k in payload}
    if summary:
        print(f"{label} summary: {json.dumps(summary, ensure_ascii=True)}")
    data = payload.get("Data")
    if isinstance(data, dict):
        list_candidates: List[Iterable[Any]] = []
        for key in ("Items", "List", "DetailList", "Records", "Data"):
            value = data.get(key)
            if isinstance(value, list):
                list_candidates.append(value)
            elif isinstance(value, dict):
                for nested_key in ("Item", "Items", "List", "Records", "DetailList"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, list):
                        list_candidates.append(nested_value)
        if list_candidates:
            items = list_candidates[0]
            print(f"{label} items: {len(items)}")
            if items:
                print(
                    f"{label} first item keys: {', '.join(sorted(items[0].keys()))}"
                )
            return
        print(f"{label} data keys: {', '.join(sorted(data.keys()))}")
        return
    if isinstance(data, list):
        print(f"{label} items: {len(data)}")
        if data:
            print(f"{label} first item keys: {', '.join(sorted(data[0].keys()))}")
        return


def extract_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(payload.get("body"), dict):
        payload = payload["body"]
    data = payload.get("Data")
    if isinstance(data, dict):
        items = data.get("Items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        if isinstance(items, dict):
            for key in ("Item", "Items", "List", "Records", "DetailList"):
                value = items.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def call_query_bill_detail(
    client: BssClient,
    start_time: str,
    end_time: str,
    granularity: str,
    product_code: Optional[str],
    subscription_type: Optional[str],
    api_version: str,
) -> Dict[str, Any]:
    query: Dict[str, Any] = {
        "StartTime": start_time,
        "EndTime": end_time,
        "Granularity": granularity,
    }
    if product_code:
        query["ProductCode"] = product_code
    if subscription_type:
        query["SubscriptionType"] = subscription_type

    req = open_api_models.OpenApiRequest(query=OpenApiUtilClient.query(query))
    params = open_api_models.Params(
        action="QueryBillDetail",
        version=api_version,
        protocol="HTTPS",
        pathname="/",
        method="POST",
        auth_type="AK",
        style="RPC",
        req_body_type="formData",
        body_type="json",
    )
    runtime = util_models.RuntimeOptions()
    return client.call_api(params, req, runtime)


def call_describe_split_item_bill(
    client: BssClient,
    billing_cycle: str,
    billing_date: str,
    product_code: Optional[str],
    subscription_type: Optional[str],
) -> Dict[str, Any]:
    query: Dict[str, Any] = {
        "BillingCycle": billing_cycle,
        "BillingDate": billing_date,
        "Granularity": "DAILY",
        "MaxResults": 300,
    }
    if product_code:
        query["ProductCode"] = product_code
    if subscription_type:
        query["SubscriptionType"] = subscription_type

    req = open_api_models.OpenApiRequest(query=OpenApiUtilClient.query(query))
    params = open_api_models.Params(
        action="DescribeSplitItemBill",
        version="2017-12-14",
        protocol="HTTPS",
        pathname="/",
        method="POST",
        auth_type="AK",
        style="RPC",
        req_body_type="formData",
        body_type="json",
    )
    runtime = util_models.RuntimeOptions()
    return client.call_api(params, req, runtime)


def call_query_instance_bill(
    client: BssClient,
    billing_cycle: str,
    billing_date: str,
    product_code: Optional[str],
    subscription_type: Optional[str],
) -> Dict[str, Any]:
    query: Dict[str, Any] = {
        "BillingCycle": billing_cycle,
        "BillingDate": billing_date,
        "Granularity": "DAILY",
        "PageNum": 1,
        "PageSize": 300,
    }
    if product_code:
        query["ProductCode"] = product_code
    if subscription_type:
        query["SubscriptionType"] = subscription_type

    req = open_api_models.OpenApiRequest(query=OpenApiUtilClient.query(query))
    params = open_api_models.Params(
        action="QueryInstanceBill",
        version="2017-12-14",
        protocol="HTTPS",
        pathname="/",
        method="POST",
        auth_type="AK",
        style="RPC",
        req_body_type="formData",
        body_type="json",
    )
    runtime = util_models.RuntimeOptions()
    return client.call_api(params, req, runtime)


def main() -> None:
    client = build_bss_client()

    start_time = os.getenv("ALIBABA_CLOUD_BILL_DETAIL_START_TIME")
    end_time = os.getenv("ALIBABA_CLOUD_BILL_DETAIL_END_TIME")
    granularity = os.getenv("ALIBABA_CLOUD_BILL_DETAIL_GRANULARITY", "HOURLY")
    if not start_time or not end_time:
        start_time, end_time = time_window(24)

    billing_cycle = os.getenv("ALIBABA_CLOUD_BILLING_CYCLE")
    billing_date = os.getenv("ALIBABA_CLOUD_BILLING_DATE")
    if not billing_cycle or not billing_date:
        billing_cycle, billing_date = billing_cycle_and_date()

    product_code = os.getenv("ALIBABA_CLOUD_PRODUCT_CODE")
    subscription_type = os.getenv("ALIBABA_CLOUD_SUBSCRIPTION_TYPE")
    bill_detail_version = os.getenv("ALIBABA_CLOUD_BILL_DETAIL_VERSION", "2017-12-14")

    print(
        f"QueryBillDetail {granularity} (version {bill_detail_version}): "
        f"{start_time} -> {end_time}"
    )
    try:
        payload = call_query_bill_detail(
            client,
            start_time,
            end_time,
            granularity,
            product_code,
            subscription_type,
            bill_detail_version,
        )
        summarize_response("QueryBillDetail", payload)
    except Exception as exc:
        print(f"QueryBillDetail error: {exc}", file=sys.stderr)

    print(f"DescribeSplitItemBill DAILY: {billing_cycle} {billing_date}")
    try:
        payload = call_describe_split_item_bill(
            client, billing_cycle, billing_date, product_code, subscription_type
        )
        summarize_response("DescribeSplitItemBill", payload)
    except Exception as exc:
        print(f"DescribeSplitItemBill error: {exc}", file=sys.stderr)

    print(f"QueryInstanceBill DAILY: {billing_cycle} {billing_date}")
    try:
        payload = call_query_instance_bill(
            client, billing_cycle, billing_date, product_code, subscription_type
        )
        summarize_response("QueryInstanceBill", payload)
        items = extract_items(payload)
        if items:
            print("QueryInstanceBill sample periods:")
            for item in items[:3]:
                billing_date_value = item.get("BillingDate")
                service_period = item.get("ServicePeriod")
                usage = item.get("Usage")
                usage_unit = item.get("UsageUnit")
                print(
                    f"  BillingDate={billing_date_value} "
                    f"ServicePeriod={service_period} "
                    f"Usage={usage} {usage_unit}"
                )
    except Exception as exc:
        print(f"QueryInstanceBill error: {exc}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise
