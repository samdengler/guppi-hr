#!/usr/bin/env python
"""Create, update, list and delete the test runtimes of the Runtime V2 cold start study
(docs/runtime-v2-experiments.md). Needs boto3 1.43.95 or newer for `platformVersion`:

    uv run --no-project --with 'boto3>=1.43.95' python scripts/v2study/create.py ...

Every runtime gets the study's role, image repository and APPLICATION_LOGS delivery, and
a line in docs/runtime-v2-evidence/runtimes.jsonl with its create and READY times.

    create.py create NAME --image TAG --protocol HTTP|MCP|A2A --platform V1|V2 \
        [--env K=V ...] [--idle SECONDS] [--jwt-discovery URL --jwt-client ID] \
        [--vpc SUBNET,SUBNET --sg SG] --experiment E1
    create.py update NAME --env K=V ...        (a new version and a new snapshot)
    create.py list
    create.py delete NAME | --all
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import boto3

REGION = "us-east-1"
STUDY_TAG = {"hr-v2-study": "2026-10-04"}
REPO = "hr-v2-study"
ROLE = "hr-v2-study-runtime"
LOG_GROUP = "/aws/vendedlogs/bedrock-agentcore/hr-v2-study"
DEST = "hr-v2-study-logs"
EVIDENCE = pathlib.Path(__file__).resolve().parents[2] / "docs" / "runtime-v2-evidence" / "runtimes.jsonl"

ctl = boto3.client("bedrock-agentcore-control", region_name=REGION)
logs = boto3.client("logs", region_name=REGION)
ACCOUNT = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
REPO_URI = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{REPO}"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/{ROLE}"
DEST_ARN = f"arn:aws:logs:{REGION}:{ACCOUNT}:delivery-destination:{DEST}"


def record(line: dict) -> None:
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open("a") as f:
        f.write(json.dumps(line, default=str) + "\n")


def find(name: str) -> dict | None:
    token = None
    while True:
        kw = {"nextToken": token} if token else {}
        resp = ctl.list_agent_runtimes(maxResults=100, **kw)
        for rt in resp["agentRuntimes"]:
            if rt["agentRuntimeName"] == name:
                return rt
        token = resp.get("nextToken")
        if not token:
            return None


def wait_ready(runtime_id: str, timeout: float = 1200) -> tuple[dict, float]:
    start = time.time()
    while True:
        rt = ctl.get_agent_runtime(agentRuntimeId=runtime_id)
        status = rt["status"]
        if status == "READY":
            return rt, time.time()
        if status.endswith("FAILED") or status == "DELETING":
            raise SystemExit(f"{runtime_id}: {status} {rt.get('failureReason') or rt.get('statusReason') or ''}")
        if time.time() - start > timeout:
            raise SystemExit(f"{runtime_id}: still {status} after {timeout} s")
        time.sleep(5)


def attach_logs(name: str, arn: str) -> None:
    source = f"hr-v2-study-{name}"
    try:
        logs.put_delivery_source(name=source, resourceArn=arn, logType="APPLICATION_LOGS", tags=STUDY_TAG)
    except logs.exceptions.ConflictException:
        pass
    try:
        logs.create_delivery(deliverySourceName=source, deliveryDestinationArn=DEST_ARN, tags=STUDY_TAG)
    except logs.exceptions.ConflictException:
        pass


def detach_logs(name: str) -> None:
    source = f"hr-v2-study-{name}"
    for d in logs.describe_deliveries().get("deliveries", []):
        if d["deliverySourceName"] == source:
            logs.delete_delivery(id=d["id"])
    try:
        logs.delete_delivery_source(name=source)
    except logs.exceptions.ResourceNotFoundException:
        pass


def parse_env(items: list[str] | None) -> dict:
    env = {}
    for item in items or []:
        k, _, v = item.partition("=")
        env[k] = v
    return env


def cmd_create(a: argparse.Namespace) -> None:
    if find(a.name):
        raise SystemExit(f"{a.name} exists")
    env = parse_env(a.env)
    env.setdefault("VARIANT", a.name)
    spec: dict = {
        "agentRuntimeName": a.name,
        "description": f"hr-v2-study {a.experiment}",
        "agentRuntimeArtifact": {"containerConfiguration": {"containerUri": f"{REPO_URI}:{a.image}"}},
        "roleArn": ROLE_ARN,
        "networkConfiguration": {"networkMode": "PUBLIC"},
        "protocolConfiguration": {"serverProtocol": a.protocol},
        "platformVersion": a.platform,
        "environmentVariables": env,
        "lifecycleConfiguration": {"idleRuntimeSessionTimeout": a.idle, "maxLifetime": a.max_lifetime},
        "tags": {**STUDY_TAG, "experiment": a.experiment},
    }
    if a.vpc:
        spec["networkConfiguration"] = {
            "networkMode": "VPC",
            "networkModeConfig": {"subnets": a.vpc.split(","), "securityGroups": a.sg.split(",")},
        }
    if a.jwt_discovery:
        auth: dict = {"discoveryUrl": a.jwt_discovery}
        if a.jwt_client:
            auth["allowedClients"] = a.jwt_client.split(",")
        if a.jwt_audience:
            auth["allowedAudience"] = a.jwt_audience.split(",")
        spec["authorizerConfiguration"] = {"customJWTAuthorizer": auth}
    t_create = time.time()
    resp = ctl.create_agent_runtime(**spec)
    rt, t_ready = wait_ready(resp["agentRuntimeId"])
    attach_logs(a.name, rt["agentRuntimeArn"])
    line = {
        "op": "create", "name": a.name, "id": rt["agentRuntimeId"], "arn": rt["agentRuntimeArn"],
        "version": rt.get("agentRuntimeVersion"), "platform": rt.get("platformVersion"), "protocol": a.protocol,
        "image": a.image, "env": env, "idle": a.idle, "network": spec["networkConfiguration"]["networkMode"],
        "auth": "jwt" if a.jwt_discovery else "sigv4", "experiment": a.experiment,
        "created_at": t_create, "ready_at": t_ready, "build_s": round(t_ready - t_create, 1),
    }
    record(line)
    print(json.dumps(line))


def cmd_update(a: argparse.Namespace) -> None:
    rt = find(a.name)
    if not rt:
        raise SystemExit(f"{a.name} not found")
    cur = ctl.get_agent_runtime(agentRuntimeId=rt["agentRuntimeId"])
    env = dict(cur.get("environmentVariables") or {})
    env.update(parse_env(a.env))
    spec = {
        "agentRuntimeId": cur["agentRuntimeId"],
        "agentRuntimeArtifact": cur["agentRuntimeArtifact"],
        "roleArn": cur["roleArn"],
        "networkConfiguration": cur["networkConfiguration"],
        "protocolConfiguration": cur["protocolConfiguration"],
        "environmentVariables": env,
        "lifecycleConfiguration": cur["lifecycleConfiguration"],
        "platformVersion": a.platform or cur.get("platformVersion"),
    }
    if a.image:
        spec["agentRuntimeArtifact"] = {"containerConfiguration": {"containerUri": f"{REPO_URI}:{a.image}"}}
    if cur.get("authorizerConfiguration"):
        spec["authorizerConfiguration"] = cur["authorizerConfiguration"]
    if a.idle:
        spec["lifecycleConfiguration"] = {"idleRuntimeSessionTimeout": a.idle, "maxLifetime": cur["lifecycleConfiguration"]["maxLifetime"]}
    t_update = time.time()
    ctl.update_agent_runtime(**spec)
    time.sleep(3)
    rt2, t_ready = wait_ready(cur["agentRuntimeId"])
    line = {
        "op": "update", "name": a.name, "id": cur["agentRuntimeId"], "arn": cur["agentRuntimeArn"],
        "version": rt2.get("agentRuntimeVersion"), "platform": rt2.get("platformVersion"), "env": env,
        "updated_at": t_update, "ready_at": t_ready, "build_s": round(t_ready - t_update, 1),
    }
    record(line)
    print(json.dumps(line))


def cmd_list(a: argparse.Namespace) -> None:
    token = None
    while True:
        kw = {"nextToken": token} if token else {}
        resp = ctl.list_agent_runtimes(maxResults=100, **kw)
        for rt in resp["agentRuntimes"]:
            if rt["agentRuntimeName"].startswith("hr_v2_"):
                full = ctl.get_agent_runtime(agentRuntimeId=rt["agentRuntimeId"])
                print(rt["agentRuntimeName"], rt["agentRuntimeId"], rt["status"], full.get("platformVersion"),
                      full["protocolConfiguration"]["serverProtocol"], "v" + str(full.get("agentRuntimeVersion")), rt["agentRuntimeArn"])
        token = resp.get("nextToken")
        if not token:
            return


def cmd_delete(a: argparse.Namespace) -> None:
    names = []
    if a.all:
        token = None
        while True:
            kw = {"nextToken": token} if token else {}
            resp = ctl.list_agent_runtimes(maxResults=100, **kw)
            names += [rt["agentRuntimeName"] for rt in resp["agentRuntimes"] if rt["agentRuntimeName"].startswith("hr_v2_")]
            token = resp.get("nextToken")
            if not token:
                break
    else:
        names = [a.name]
    for name in names:
        rt = find(name)
        if rt:
            ctl.delete_agent_runtime(agentRuntimeId=rt["agentRuntimeId"])
            record({"op": "delete", "name": name, "id": rt["agentRuntimeId"], "at": time.time()})
            print("deleting", name, rt["agentRuntimeId"])
        detach_logs(name)
    if a.wait:
        for name in names:
            while find(name):
                time.sleep(5)
        print("deleted", len(names))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("name")
    c.add_argument("--image", required=True)
    c.add_argument("--protocol", required=True, choices=["HTTP", "MCP", "A2A"])
    c.add_argument("--platform", required=True, choices=["V1", "V2"])
    c.add_argument("--env", action="append")
    c.add_argument("--idle", type=int, default=900)
    c.add_argument("--max-lifetime", type=int, default=28800)
    c.add_argument("--jwt-discovery")
    c.add_argument("--jwt-client")
    c.add_argument("--jwt-audience")
    c.add_argument("--vpc", help="comma separated subnet ids")
    c.add_argument("--sg", help="comma separated security group ids")
    c.add_argument("--experiment", required=True)
    c.set_defaults(fn=cmd_create)
    u = sub.add_parser("update")
    u.add_argument("name")
    u.add_argument("--env", action="append")
    u.add_argument("--image")
    u.add_argument("--platform", choices=["V1", "V2"])
    u.add_argument("--idle", type=int)
    u.set_defaults(fn=cmd_update)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    d = sub.add_parser("delete")
    d.add_argument("name", nargs="?")
    d.add_argument("--all", action="store_true")
    d.add_argument("--wait", action="store_true")
    d.set_defaults(fn=cmd_delete)
    a = p.parse_args()
    if a.cmd == "delete" and not (a.name or a.all):
        p.error("delete needs a name or --all")
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
