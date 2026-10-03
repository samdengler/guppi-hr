import json

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template
from hr_super_agent_infra.stack import HrSuperAgentStack

ACCOUNT = "123456789012"
REGION = "us-east-1"


def synth(**extra_context) -> Template:
    app = cdk.App(
        context={
            "image_uri": f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/hr-super-agent:test",
            **extra_context,
        }
    )
    stack = HrSuperAgentStack(
        app, "HrSuperAgent", env=cdk.Environment(account=ACCOUNT, region=REGION)
    )
    return Template.from_stack(stack)


@pytest.fixture(scope="module")
def template() -> Template:
    return synth()


@pytest.fixture(scope="module")
def singleton_template() -> Template:
    return synth(own_account_singletons="true")


def test_account_singletons_are_left_to_the_guppi_gpt_stack_by_default(template):
    template.resource_count_is("AWS::XRay::TransactionSearchConfig", 0)


def test_the_platform_owns_the_page_sign_in_and_edge(template):
    # Phase 8: the page, sign-in, CloudFront, WAF, the edge gateway and its limits, the
    # feedback API, and DNS belong to the GuppiGpt platform stack.
    for resource_type in (
        "AWS::Cognito::UserPool",
        "AWS::Cognito::UserPoolClient",
        "AWS::Cognito::UserPoolDomain",
        "AWS::CertificateManager::Certificate",
        "AWS::Route53::RecordSet",
        "AWS::CloudFront::Distribution",
        "AWS::CloudFront::ResponseHeadersPolicy",
        "AWS::WAFv2::WebACL",
        "AWS::WAFv2::WebACLAssociation",
        "AWS::BedrockAgentCore::GatewayRateLimit",
        "AWS::ApiGateway::RestApi",
        "AWS::Events::EventBus",
        "AWS::Events::Archive",
        "AWS::Events::Rule",
        "AWS::Events::ApiDestination",
        "AWS::SQS::Queue",
    ):
        template.resource_count_is(resource_type, 0)
    gateways = template.find_resources("AWS::BedrockAgentCore::Gateway")
    assert sorted(g["Properties"]["Name"] for g in gateways.values()) == [
        "hr-super-agent-agents",
        "hr-super-agent-tools",
    ]
    parameters = template.to_json().get("Parameters", {})
    for removed in ("GoogleClientId", "GoogleClientSecret", "DynatraceBeaconOrigin"):
        assert removed not in parameters
    outputs = template.to_json().get("Outputs", {})
    for removed in (
        "SiteBucketName",
        "DistributionId",
        "UserPoolId",
        "UserPoolClientId",
        "AuthDomain",
        "GatewayUrl",
        "GatewayArn",
        "FeedbackApiUrl",
        "FeedbackBusName",
        "RumScriptPath",
        "RumBeaconOrigin",
    ):
        assert removed not in outputs


def _ssm_parameter_ref(template, name: str) -> dict:
    """The Ref to the SSM-typed CloudFormation parameter that reads `name` at deploy time."""
    parameters = template.to_json()["Parameters"]
    (logical_id,) = [
        key
        for key, value in parameters.items()
        if value.get("Type") == "AWS::SSM::Parameter::Value<String>"
        and value.get("Default") == name
    ]
    return {"Ref": logical_id}


def test_every_authorizer_accepts_the_platform_token(template):
    discovery = _ssm_parameter_ref(template, "/guppi/platform/jwt-discovery-url")
    client = _ssm_parameter_ref(template, "/guppi/platform/user-pool-client-id")
    gateways = template.find_resources("AWS::BedrockAgentCore::Gateway")
    runtimes = template.find_resources("AWS::BedrockAgentCore::Runtime")
    authorizers = [
        g["Properties"]["AuthorizerConfiguration"]["CustomJWTAuthorizer"]
        for g in gateways.values()
    ] + [
        r["Properties"]["AuthorizerConfiguration"]["CustomJWTAuthorizer"]
        for r in runtimes.values()
        if "AuthorizerConfiguration" in r["Properties"]
    ]
    # Two gateways, the orchestrator, and three sub-agents; the HR tools runtime has no
    # authorizer of its own and verifies the forwarded token itself (D19).
    assert len(authorizers) == 6
    for authorizer in authorizers:
        assert authorizer["DiscoveryUrl"] == discovery
        assert authorizer["AllowedClients"] == [client]


def test_hr_tools_verify_the_platform_issuer_and_client(template):
    env = _hr_tools_runtime(template)["Properties"]["EnvironmentVariables"]
    discovery = _ssm_parameter_ref(template, "/guppi/platform/jwt-discovery-url")
    client = _ssm_parameter_ref(template, "/guppi/platform/user-pool-client-id")
    assert env["TOKEN_ISSUER"] == {
        "Fn::Select": [0, {"Fn::Split": ["/.well-known/openid-configuration", discovery]}]
    }
    # CDK folds a one-element Fn::Join to the element itself.
    assert env["TOKEN_ALLOWED_CLIENTS"] == client


def test_platform_gateway_role_may_invoke_the_orchestrator(template):
    role_arn = _ssm_parameter_ref(template, "/guppi/platform/edge-gateway-role-arn")
    policies = template.find_resources("AWS::IAM::Policy")
    (policy,) = [
        p for key, p in policies.items() if key.startswith("PlatformGatewayInvokePolicy")
    ]
    # The role name, cut from the ARN the platform publishes.
    (role,) = policy["Properties"]["Roles"]
    assert json.dumps(role_arn) in json.dumps(role)
    (statement,) = policy["Properties"]["PolicyDocument"]["Statement"]
    assert statement["Action"] == "bedrock-agentcore:InvokeAgentRuntime"
    resources = json.dumps(statement["Resource"])
    assert "Runtime" in resources and "runtime-endpoint/*" in resources


def test_page_url_is_the_platform_project_path(template):
    site = _ssm_parameter_ref(template, "/guppi/platform/site-url")
    outputs = template.to_json()["Outputs"]
    assert outputs["SiteUrl"]["Value"] == {"Fn::Join": ["", [site, "p/hr-diy/"]]}
    assert outputs["AgentPath"]["Value"] == "/api/hr-diy/invocations"
    for kept in ("AgentsGatewayUrl", "ToolsGatewayUrl", "RuntimeArn", "KnowledgeBaseId"):
        assert kept in outputs


def test_runtime_is_agui_and_not_bound_to_gateway_by_default(template):
    template.has_resource_properties(
        "AWS::BedrockAgentCore::Runtime",
        {
            "ProtocolConfiguration": "AGUI",
            "NetworkConfiguration": {"NetworkMode": "PUBLIC"},
            "AuthorizerConfiguration": {
                "CustomJWTAuthorizer": Match.object_equals(
                    {
                        "DiscoveryUrl": Match.any_value(),
                        "AllowedClients": Match.any_value(),
                    }
                )
            },
        },
    )


def test_runtime_binds_to_gateway_when_asked():
    bound = synth(bind_runtime_to_gateway=True)
    gateway_arn = _ssm_parameter_ref(bound, "/guppi/platform/edge-gateway-arn")
    bound.has_resource_properties(
        "AWS::BedrockAgentCore::Runtime",
        {
            "AuthorizerConfiguration": {
                "CustomJWTAuthorizer": {
                    "AllowedWorkloadConfiguration": {
                        "HostingEnvironments": [{"Arn": gateway_arn}]
                    }
                }
            },
        },
    )


def test_the_gateway_arn_is_read_only_when_binding(template):
    parameters = template.to_json()["Parameters"]
    assert all(
        value.get("Default") != "/guppi/platform/edge-gateway-arn"
        for value in parameters.values()
    )


def _platform_target(template) -> dict:
    targets = template.find_resources("AWS::BedrockAgentCore::GatewayTarget")
    (target,) = [t for key, t in targets.items() if key.startswith("PlatformTarget")]
    return target


def test_target_is_runtime_with_jwt_passthrough(template):
    target = _platform_target(template)
    props = target["Properties"]
    assert props["Name"] == "hr-diy"
    assert props["GatewayIdentifier"] == _ssm_parameter_ref(
        template, "/guppi/platform/edge-gateway-id"
    )
    assert props["CredentialProviderConfigurations"] == [
        {"CredentialProviderType": "JWT_PASSTHROUGH"}
    ]
    runtime = props["TargetConfiguration"]["Http"]["AgentcoreRuntime"]
    assert runtime["Qualifier"] == "DEFAULT"
    assert runtime["Arn"]["Fn::GetAtt"][0].startswith("Runtime")
    assert any(d.startswith("PlatformGatewayInvokePolicy") for d in target["DependsOn"])


def test_no_lambda_functions(template):
    assert template.find_resources("AWS::Lambda::Function") == {}


def test_managed_knowledge_base_reads_the_content_bucket(template):
    template.has_resource_properties(
        "AWS::Bedrock::KnowledgeBase",
        {
            "KnowledgeBaseConfiguration": {
                "Type": "MANAGED",
                "ManagedKnowledgeBaseConfiguration": {"EmbeddingModelType": "MANAGED"},
            }
        },
    )
    template.has_resource_properties(
        "AWS::Bedrock::DataSource",
        {
            "DataDeletionPolicy": "DELETE",
            "DataSourceConfiguration": {
                "Type": "MANAGED_KNOWLEDGE_BASE_CONNECTOR",
                "ManagedKnowledgeBaseConnectorConfiguration": {
                    "ConnectorParameters": Match.object_like(
                        {
                            "type": "S3",
                            "filterConfiguration": {"inclusionPrefixes": ["docs/"]},
                        }
                    ),
                    "DeletionProtectionConfiguration": {"DeletionProtectionStatus": "DISABLED"},
                },
            },
        },
    )
    template.has_resource_properties(
        "AWS::S3::Bucket",
        Match.object_like({"VersioningConfiguration": {"Status": "Enabled"}}),
    )


def test_nightly_ingestion_is_a_scheduler_universal_target(template):
    template.has_resource_properties(
        "AWS::Scheduler::Schedule",
        {
            "ScheduleExpression": "cron(0 9 * * ? *)",
            "Target": Match.object_like({"Arn": Match.any_value(), "Input": Match.any_value()}),
        },
    )
    rendered = json.dumps(template.to_json())
    assert ":scheduler:::aws-sdk:bedrockagent:startIngestionJob" in rendered
    assert '{\\"KnowledgeBaseId\\":\\"' in rendered and '\\"DataSourceId\\":\\"' in rendered
    template.has_resource_properties(
        "AWS::IAM::Policy",
        Match.object_like(
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [Match.object_like({"Action": "bedrock:StartIngestionJob"})]
                    )
                }
            }
        ),
    )


def test_billing_alarm_has_the_cost_limit_and_the_alarm_topic(template):
    alarms = template.find_resources("AWS::CloudWatch::Alarm")
    (alarm,) = [
        a for a in alarms.values() if a["Properties"].get("MetricName") == "EstimatedCharges"
    ]
    props = alarm["Properties"]
    assert props["Namespace"] == "AWS/Billing"
    assert props["Dimensions"] == [{"Name": "Currency", "Value": "USD"}]
    assert props["Threshold"] == 50
    assert len(props["AlarmActions"]) == 1


def test_alarm_email_subscription_is_conditional(template):
    template.has_parameter("AlarmEmail", {"Default": ""})
    subscriptions = template.find_resources("AWS::SNS::Subscription")
    (subscription,) = subscriptions.values()
    assert subscription["Properties"]["Protocol"] == "email"
    assert "Condition" in subscription
    conditions = template.to_json().get("Conditions", {})
    assert subscription["Condition"] in conditions


def test_runtime_environment_variables_point_at_the_tools_gateway(template):
    template.has_resource_properties(
        "AWS::BedrockAgentCore::Runtime",
        {
            "EnvironmentVariables": Match.object_like(
                {
                    "LOG_LEVEL": "INFO",
                    "MODEL_ID": "us.anthropic.claude-sonnet-4-6",
                    "OTEL_PYTHON_EXCLUDED_URLS": "/ping$",
                    "RETRIEVE_TOOL": "docs___Retrieve",
                    "TOOLS_GATEWAY_URL": Match.any_value(),
                }
            )
        },
    )


def test_runtime_role_grants_only_the_one_inference_profile(template):
    template.has_resource_properties(
        "AWS::IAM::Policy",
        Match.object_like(
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": [
                                        "bedrock:InvokeModel",
                                        "bedrock:InvokeModelWithResponseStream",
                                    ],
                                    "Resource": [
                                        "arn:aws:bedrock:*::foundation-model/*",
                                        Match.string_like_regexp(
                                            r"arn:aws:bedrock:.*:inference-profile/"
                                            r"us\.anthropic\.claude-haiku-4-5-20251001-v1:0"
                                        ),
                                    ],
                                }
                            )
                        ]
                    )
                }
            }
        ),
    )


def test_tools_gateway_is_mcp_with_cognito_jwt_and_kb_connector(template):
    template.has_resource_properties(
        "AWS::BedrockAgentCore::Gateway",
        {"Name": "hr-super-agent-tools", "ProtocolType": "MCP", "AuthorizerType": "CUSTOM_JWT"},
    )
    template.has_resource_properties(
        "AWS::BedrockAgentCore::GatewayTarget",
        {
            "Name": "docs",
            "CredentialProviderConfigurations": [{"CredentialProviderType": "GATEWAY_IAM_ROLE"}],
            "TargetConfiguration": {
                "Mcp": {
                    "Connector": {
                        "Source": {"ConnectorId": "bedrock-knowledge-bases"},
                        "Configurations": Match.array_with(
                            [Match.object_like({"Name": "Retrieve"})]
                        ),
                    }
                }
            },
        },
    )
    template.has_resource_properties(
        "AWS::IAM::Policy",
        Match.object_like(
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {"Action": ["bedrock:GetKnowledgeBase", "bedrock:Retrieve"]}
                            )
                        ]
                    )
                }
            }
        ),
    )


def test_runtime_forwards_the_bearer_and_the_trace_context_to_the_container(template):
    template.has_resource_properties(
        "AWS::BedrockAgentCore::Runtime",
        {
            "RequestHeaderConfiguration": {
                "RequestHeaderAllowlist": ["Authorization", "traceparent"]
            }
        },
    )


def test_edge_target_forwards_the_session_id_and_the_trace_context(template):
    props = _platform_target(template)["Properties"]
    assert props["MetadataConfiguration"] == {
        "AllowedRequestHeaders": [
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id",
            "traceparent",
        ]
    }


def test_runtime_role_can_let_xray_write_spans_to_its_own_log_group(template):
    template.has_resource_properties(
        "AWS::IAM::Policy",
        Match.object_like(
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": "logs:PutResourcePolicy",
                                    "Resource": Match.string_like_regexp(
                                        r"arn:aws:logs:.*:log-group:"
                                        r"/aws/bedrock-agentcore/runtimes/hr_super_agent-\*"
                                    ),
                                }
                            )
                        ]
                    )
                }
            }
        ),
    )


def test_dynatrace_otlp_parameters_and_condition(template):
    template.has_parameter("DynatraceOtlpEndpoint", {"Default": ""})
    template.has_parameter("DynatraceApiToken", {"NoEcho": True, "Default": ""})
    conditions = template.to_json().get("Conditions", {})
    assert "HasDynatraceOtlp" in conditions
    # Both parameters must be non-empty; an Fn::And of two Fn::Not/Fn::Equals checks.
    expression = conditions["HasDynatraceOtlp"]
    assert "Fn::And" in expression
    assert len(expression["Fn::And"]) == 2


def test_runtime_env_omits_dynatrace_otlp_vars_until_both_parameters_are_set(template):
    template.has_resource_properties(
        "AWS::BedrockAgentCore::Runtime",
        {
            "EnvironmentVariables": Match.object_like(
                {
                    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": {
                        "Fn::If": [
                            "HasDynatraceOtlp",
                            Match.object_like(
                                {
                                    "Fn::Join": [
                                        "",
                                        [{"Ref": "DynatraceOtlpEndpoint"}, "/v1/traces"],
                                    ]
                                }
                            ),
                            {"Ref": "AWS::NoValue"},
                        ]
                    },
                    "DYNATRACE_TOKEN_SECRET_ARN": {
                        "Fn::If": [
                            "HasDynatraceOtlp",
                            {"Ref": Match.string_like_regexp("DynatraceTokenSecret")},
                            {"Ref": "AWS::NoValue"},
                        ]
                    },
                }
            )
        },
    )


def test_transaction_search_is_enabled_with_the_span_log_policy(singleton_template):
    singleton_template.has_resource_properties(
        "AWS::XRay::TransactionSearchConfig", {"IndexingPercentage": 1}
    )
    policies = [
        p["Properties"]["PolicyDocument"]
        for p in singleton_template.find_resources("AWS::Logs::ResourcePolicy").values()
        if "xray.amazonaws.com" in p["Properties"]["PolicyDocument"]
    ]
    (document,) = policies
    assert "log-group:aws/spans:*" in document
    searches = singleton_template.find_resources("AWS::XRay::TransactionSearchConfig")
    (search,) = searches.values()
    assert any(dep.startswith("TransactionSearchLogsPolicy") for dep in search.get("DependsOn", []))


def test_operational_alarms_report_metrics_and_notify_the_alarm_topic(template):
    (topic_id,) = template.find_resources("AWS::SNS::Topic").keys()
    alarms = template.find_resources("AWS::CloudWatch::Alarm")

    # docs/proposals/operations.md explains each threshold. Every alarm here is either a
    # plain metric (MetricName/Namespace at the top level) or a math expression (a Metrics
    # list of MetricStat entries), so both shapes are read the same way below.
    expected_metrics = {
        "ToolsGateway5xxAlarm": {("AWS/Bedrock-AgentCore", "SystemErrors")},
        "Runtime5xxAlarm": {("AWS/Bedrock-AgentCore", "SystemErrors")},
        "RuntimeLatencyP90Alarm": {("AWS/Bedrock-AgentCore", "Latency")},
        "BedrockThrottlingAlarm": {("AWS/Bedrock", "InvocationThrottles")},
    }

    matched = {}
    for logical_id, resource in alarms.items():
        for prefix in expected_metrics:
            if logical_id.startswith(prefix):
                matched[prefix] = resource["Properties"]
                break
    assert set(matched) == set(expected_metrics)

    for prefix, props in matched.items():
        assert {"Ref": topic_id} in props["AlarmActions"]
        if "MetricName" in props:
            found = {(props["Namespace"], props["MetricName"])}
        else:
            found = {
                (m["MetricStat"]["Metric"]["Namespace"], m["MetricStat"]["Metric"]["MetricName"])
                for m in props["Metrics"]
                if "MetricStat" in m
            }
        assert found == expected_metrics[prefix]
        assert props["TreatMissingData"] == "notBreaching"


# ---- Conversation log ----------------------------------------------------------------


def conversation_bucket(template) -> dict:
    buckets = template.find_resources("AWS::S3::Bucket")
    (bucket,) = [
        b
        for b in buckets.values()
        if "LifecycleConfiguration" in b["Properties"]
        and b["Properties"]["LifecycleConfiguration"]["Rules"][0]["Id"] == "ExpireThreadRecords"
    ]
    return bucket


def statements(template, logical_id_prefix: str) -> list[dict]:
    policies = template.find_resources("AWS::IAM::Policy")
    found = []
    for logical_id, policy in policies.items():
        if logical_id.startswith(logical_id_prefix):
            found.extend(policy["Properties"]["PolicyDocument"]["Statement"])
    return found


def test_conversation_bucket_is_versioned_kms_encrypted_and_expires_at_30_days(template):
    props = conversation_bucket(template)["Properties"]
    assert props["VersioningConfiguration"] == {"Status": "Enabled"}
    encryption = props["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]
    assert encryption["BucketKeyEnabled"] is True
    assert encryption["ServerSideEncryptionByDefault"]["SSEAlgorithm"] == "aws:kms"
    assert "KMSMasterKeyID" in encryption["ServerSideEncryptionByDefault"]
    assert props["PublicAccessBlockConfiguration"] == {
        "BlockPublicAcls": True,
        "BlockPublicPolicy": True,
        "IgnorePublicAcls": True,
        "RestrictPublicBuckets": True,
    }
    (rule,) = props["LifecycleConfiguration"]["Rules"]
    assert rule["Prefix"] == "threads/"
    assert rule["ExpirationInDays"] == 30
    assert rule["NoncurrentVersionExpiration"] == {"NoncurrentDays": 30}


def test_conversation_bucket_policy_denies_readers_other_than_the_two_roles(template):
    policies = template.find_resources("AWS::S3::BucketPolicy")
    documents = [p["Properties"]["PolicyDocument"]["Statement"] for p in policies.values()]
    (document,) = [d for d in documents if any(s.get("Sid") == "DenyOtherReaders" for s in d)]
    sids = {statement.get("Sid") for statement in document}
    assert {"RuntimeThreadRecords", "InvestigatorReads", "DenyOtherReaders"} <= sids
    (deny,) = [s for s in document if s.get("Sid") == "DenyOtherReaders"]
    assert deny["Effect"] == "Deny"
    assert deny["Action"] == ["s3:GetObject", "s3:GetObjectVersion"]
    assert deny["Principal"] == {"AWS": "*"}
    assert len(deny["Condition"]["StringNotEquals"]["aws:PrincipalArn"]) == 2
    # enforce_ssl adds its own deny to the same document.
    assert any(
        s.get("Condition", {}).get("Bool", {}).get("aws:SecureTransport") == "false"
        for s in document
    )


def test_runtime_role_reads_writes_and_lists_thread_objects_only(template):
    document = statements(template, "RuntimeRole")
    (thread_statement,) = [
        s for s in document if s.get("Action") == ["s3:GetObject", "s3:PutObject"]
    ]
    assert "threads/*" in json.dumps(thread_statement["Resource"])
    # ListBucket is scoped to the threads/ prefix: without it S3 answers a GET on a
    # missing key with 403 rather than 404, and the first write of a thread never happens.
    (listing,) = [s for s in document if s.get("Action") == "s3:ListBucket"]
    assert listing["Condition"] == {"StringLike": {"s3:prefix": ["threads/*"]}}
    actions = json.dumps([s.get("Action") for s in document])
    assert "s3:DeleteObject" not in actions
    assert any(s.get("Action") == "secretsmanager:GetSecretValue" for s in document)
    assert any(s.get("Action") == ["kms:Decrypt", "kms:GenerateDataKey"] for s in document)


def test_investigator_role_reads_the_bucket_the_key_and_the_pool_and_nothing_else(template):
    document = statements(template, "ConversationInvestigatorRole")
    actions = sorted(
        action
        for statement in document
        for action in (
            statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
        )
    )
    assert actions == [
        "cognito-idp:ListUsers",
        "kms:Decrypt",
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:ListBucket",
        "s3:ListBucketVersions",
        "secretsmanager:GetSecretValue",
    ]


def test_investigator_trust_is_the_account_root_until_the_parameter_is_set(template):
    template.has_parameter("InvestigatorPrincipalArn", {"Default": ""})
    roles = template.find_resources("AWS::IAM::Role")
    (role,) = [
        r for r in roles.values() if "resolves a subject" in r["Properties"].get("Description", "")
    ]
    principal = role["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]["Principal"]["AWS"]
    condition_name, when_set, when_blank = principal["Fn::If"]
    assert condition_name == "HasInvestigatorPrincipal"
    assert when_set == {"Ref": "InvestigatorPrincipalArn"}
    assert when_blank == f"arn:aws:iam::{ACCOUNT}:root"
    assert role["Properties"]["MaxSessionDuration"] == 3600


def test_runtime_carries_the_conversation_log_variables_with_the_switch_on(template):
    template.has_resource_properties(
        "AWS::BedrockAgentCore::Runtime",
        {
            "EnvironmentVariables": Match.object_like(
                {
                    "CONVERSATION_LOG_ENABLED": "true",
                    "CONVERSATION_LOG_BUCKET": Match.any_value(),
                    "CONVERSATION_LOG_KEY_SECRET_ARN": Match.any_value(),
                }
            )
        },
    )


def test_vended_log_groups_have_30_day_retention_under_the_shared_prefix(template):
    groups = template.find_resources("AWS::Logs::LogGroup")
    names = {g["Properties"]["LogGroupName"] for g in groups.values()}
    assert names == {
        "/aws/vendedlogs/bedrock-agentcore/hr-super-agent-tools",
        "/aws/vendedlogs/bedrock-agentcore/hr_super_agent",
        "/aws/vendedlogs/bedrock-agentcore/hr_super_agent_tools",
        "/aws/vendedlogs/bedrock-agentcore/hr-super-agent-agents",
        "/aws/vendedlogs/bedrock-agentcore/hr_super_agent_profile",
        "/aws/vendedlogs/bedrock-agentcore/hr_super_agent_pay",
        "/aws/vendedlogs/bedrock-agentcore/hr_super_agent_travel",
    }
    for group in groups.values():
        assert group["Properties"]["RetentionInDays"] == 30


def test_vended_log_delivery_sources_cover_application_logs_and_traces(template):
    sources = template.find_resources("AWS::Logs::DeliverySource")
    log_types_by_resource = {}
    for source in sources.values():
        props = source["Properties"]
        resource_key = json.dumps(props["ResourceArn"])
        log_types_by_resource.setdefault(resource_key, set()).add(props["LogType"])

    # Every resource gets APPLICATION_LOGS only: a CloudWatch Logs destination for the
    # gateways' TRACES log type was rejected by CloudFormation on 4 Sep 2026.
    assert len(log_types_by_resource) == 7
    assert all(v == {"APPLICATION_LOGS"} for v in log_types_by_resource.values())

    # Each delivery depends explicitly on its source and its destination, since the
    # delivery source name that links them is a plain string, not a CloudFormation
    # reference CDK would otherwise infer a dependency from.
    deliveries = template.find_resources("AWS::Logs::Delivery")
    assert len(deliveries) == len(sources)
    for delivery in deliveries.values():
        assert len(delivery.get("DependsOn", [])) == 2


def test_vended_log_delivery_resource_policy_grants_the_delivery_service(template):
    policies = [
        p["Properties"]["PolicyDocument"]
        for p in template.find_resources("AWS::Logs::ResourcePolicy").values()
        if "delivery.logs.amazonaws.com" in p["Properties"]["PolicyDocument"]
    ]
    (raw,) = policies
    document = json.loads(raw)
    (statement,) = document["Statement"]
    assert statement["Principal"] == {"Service": "delivery.logs.amazonaws.com"}
    assert set(statement["Action"]) == {"logs:CreateLogStream", "logs:PutLogEvents"}
    assert "/aws/vendedlogs/bedrock-agentcore/*" in statement["Resource"]


def test_conversation_key_secret_has_no_template(template):
    secrets = template.find_resources("AWS::SecretsManager::Secret")
    (secret,) = [
        s for s in secrets.values() if "HMAC key" in s["Properties"].get("Description", "")
    ]
    generator = secret["Properties"]["GenerateSecretString"]
    assert generator["PasswordLength"] == 32
    assert "SecretStringTemplate" not in generator and "GenerateStringKey" not in generator


def test_dynatrace_token_reaches_the_runtime_only_through_secrets_manager(template):
    # D35: the token sits in a secret; no runtime environment variable carries it.
    secrets = {
        logical_id: resource
        for logical_id, resource in template.find_resources("AWS::SecretsManager::Secret").items()
        if logical_id.startswith("DynatraceTokenSecret")
    }
    assert len(secrets) == 1
    (logical_id, secret), = secrets.items()
    assert secret["Properties"]["SecretString"]["Fn::If"][0] == "HasDynatraceOtlp"
    assert secret["Properties"]["SecretString"]["Fn::If"][1] == {"Ref": "DynatraceApiToken"}
    for runtime in template.find_resources("AWS::BedrockAgentCore::Runtime").values():
        rendered = json.dumps(runtime["Properties"].get("EnvironmentVariables", {}))
        assert "DynatraceApiToken" not in rendered
        assert "OTEL_EXPORTER_OTLP_TRACES_HEADERS" not in rendered
    policies = json.dumps(template.find_resources("AWS::IAM::Policy"))
    assert f'"Ref": "{logical_id}"' in policies


def test_every_hr_runtime_exports_traces_to_dynatrace_through_the_secret(template):
    # D36: the tools server and the sub-agents send their traces where the orchestrator's
    # go, so one trace covers a whole turn; each role can read the token's secret.
    (secret_id,) = [
        k for k in template.find_resources("AWS::SecretsManager::Secret") if k.startswith("DynatraceTokenSecret")
    ]
    runtimes = template.find_resources("AWS::BedrockAgentCore::Runtime")
    assert len(runtimes) == 5
    policies = template.find_resources("AWS::IAM::Policy")
    for runtime in runtimes.values():
        env = runtime["Properties"]["EnvironmentVariables"]
        assert env["DYNATRACE_TOKEN_SECRET_ARN"]["Fn::If"][1] == {"Ref": secret_id}
        assert env["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"]["Fn::If"][0] == "HasDynatraceOtlp"
        role_ref = runtime["Properties"]["RoleArn"]["Fn::GetAtt"][0]
        role_policies = [
            p for p in policies.values()
            if {"Ref": role_ref} in p["Properties"].get("Roles", [])
        ]
        assert any(
            json.dumps({"Ref": secret_id}) in json.dumps(p["Properties"]["PolicyDocument"])
            for p in role_policies
        ), role_ref


def test_dynatrace_monitoring_role_is_gone(template):
    # The role-based Dynatrace AWS integration was removed on 7 Sep 2026: Dynatrace's own
    # push-based activation stack, deployed outside this repo, polls CloudWatch on its own.
    roles = template.find_resources("AWS::IAM::Role")
    names = {r["Properties"].get("RoleName") for r in roles.values()}
    assert "HrSuperAgentDynatraceMonitoring" not in names
    rendered = template.to_json()
    assert "DynatraceAwsAccountId" not in rendered.get("Parameters", {})
    assert "DynatraceExternalId" not in rendered.get("Parameters", {})
    assert "HasDynatraceAws" not in rendered.get("Conditions", {})
    assert "DynatraceMonitoringRoleArn" not in rendered.get("Outputs", {})


def test_dynatrace_logs_condition_reuses_the_otlp_parameters(template):
    conditions = template.to_json().get("Conditions", {})
    assert "HasDynatraceLogs" in conditions
    expression = conditions["HasDynatraceLogs"]
    assert "Fn::And" in expression
    assert len(expression["Fn::And"]) == 2
    rendered = json.dumps(expression)
    assert "DynatraceOtlpEndpoint" in rendered
    assert "DynatraceApiToken" in rendered


def test_dynatrace_log_backup_bucket_is_small_and_conditional(template):
    buckets = template.find_resources("AWS::S3::Bucket")
    (backup,) = [
        b
        for b in buckets.values()
        if b["Properties"].get("LifecycleConfiguration", {}).get("Rules", [{}])[0].get("Id")
        == "ExpireFailedDeliveries"
    ]
    assert backup["Condition"] == "HasDynatraceLogs"
    (rule,) = backup["Properties"]["LifecycleConfiguration"]["Rules"]
    assert rule["ExpirationInDays"] == 7
    # Not the content or conversation log buckets.
    assert len(buckets) == 3


def test_dynatrace_firehose_stream_targets_the_dynatrace_http_endpoint(template):
    streams = template.find_resources("AWS::KinesisFirehose::DeliveryStream")
    (stream,) = streams.values()
    assert stream["Condition"] == "HasDynatraceLogs"
    config = stream["Properties"]["HttpEndpointDestinationConfiguration"]
    assert config["EndpointConfiguration"]["Name"] == "Dynatrace"
    assert config["EndpointConfiguration"]["AccessKey"] == {"Ref": "DynatraceApiToken"}
    # The ingest URL is derived from DynatraceOtlpEndpoint: split off its fixed
    # "/api/v2/otlp" suffix to recover the tenant's base URL, then append the logs
    # ingest path, rather than a separate parameter naming the same tenant again.
    assert config["EndpointConfiguration"]["Url"] == {
        "Fn::Join": [
            "",
            [
                {
                    "Fn::Select": [
                        0,
                        {"Fn::Split": ["/api/v2/otlp", {"Ref": "DynatraceOtlpEndpoint"}]},
                    ]
                },
                "/api/v2/logs/ingest/aws_firehose",
            ],
        ]
    }
    assert config["BufferingHints"] == {"IntervalInSeconds": 60, "SizeInMBs": 1}
    assert config["RequestConfiguration"]["ContentEncoding"] == "GZIP"
    assert config["S3BackupMode"] == "FailedDataOnly"


def test_dynatrace_subscription_filters_target_every_vended_log_group(template):
    filters = template.find_resources("AWS::Logs::SubscriptionFilter")
    dynatrace_filters = {
        k: v for k, v in filters.items() if v.get("Condition") == "HasDynatraceLogs"
    }
    assert len(dynatrace_filters) == 7
    (stream_logical_id,) = template.find_resources("AWS::KinesisFirehose::DeliveryStream").keys()
    log_group_refs = set()
    for f in dynatrace_filters.values():
        props = f["Properties"]
        assert props["DestinationArn"] == {"Fn::GetAtt": [stream_logical_id, "Arn"]}
        log_group_refs.add(props["LogGroupName"]["Ref"])
    vended_log_group_ids = set(
        template.find_resources(
            "AWS::Logs::LogGroup",
            Match.object_like({"Properties": {"LogGroupName": Match.any_value()}}),
        ).keys()
    )
    assert log_group_refs == vended_log_group_ids


def test_runtime_waits_for_the_runtime_role_policy(template):
    (runtime,) = template.find_resources(
        "AWS::BedrockAgentCore::Runtime", {"Properties": {"AgentRuntimeName": "hr_super_agent"}}
    ).values()
    assert any(dep.startswith("RuntimeRoleDefaultPolicy") for dep in runtime.get("DependsOn", []))


# ---- HR tools (phase 2) ---------------------------------------------------------------


def _hr_tools_runtime(template):
    runtimes = template.find_resources(
        "AWS::BedrockAgentCore::Runtime", {"Properties": {"ProtocolConfiguration": "MCP"}}
    )
    (runtime,) = runtimes.values()
    return runtime


def test_forwarded_headers_match_the_tools_server():
    from hr_agent.tools.identity import FORWARDED_HEADERS as SERVER_HEADERS
    from hr_super_agent_infra.hr_tools import FORWARDED_HEADERS

    assert [h.lower() for h in FORWARDED_HEADERS] == list(SERVER_HEADERS)


def test_hr_tools_runtime_is_an_mcp_server_signed_with_iam(template):
    runtime = _hr_tools_runtime(template)
    props = runtime["Properties"]
    assert props["AgentRuntimeName"] == "hr_super_agent_tools"
    assert "AuthorizerConfiguration" not in props  # SigV4 inbound (D19)
    assert props["RequestHeaderConfiguration"]["RequestHeaderAllowlist"] == [
        "X-Hr-User-Token",
        "X-Hr-Thread-Id",
        "traceparent",
    ]
    env = props["EnvironmentVariables"]
    assert env["AGENT_ROLE"] == "tools"
    assert set(env) >= {
        "EMPLOYEES_TABLE",
        "PROPOSALS_TABLE",
        "TICKETS_TABLE",
        "AUDIT_TABLE",
        "TOKEN_ISSUER",
        "TOKEN_ALLOWED_CLIENTS",
    }
    assert any(dep.startswith("ToolsRuntimeRoleDefaultPolicy") for dep in runtime["DependsOn"])


def test_hr_target_signs_with_the_gateway_role_and_forwards_the_headers(template):
    targets = template.find_resources(
        "AWS::BedrockAgentCore::GatewayTarget", {"Properties": {"Name": "hr"}}
    )
    (target,) = [t for t in targets.values() if "Mcp" in t["Properties"]["TargetConfiguration"]]
    props = target["Properties"]
    (credential,) = props["CredentialProviderConfigurations"]
    assert credential["CredentialProviderType"] == "GATEWAY_IAM_ROLE"
    assert credential["CredentialProvider"]["IamCredentialProvider"]["Service"] == (
        "bedrock-agentcore"
    )
    assert props["MetadataConfiguration"]["AllowedRequestHeaders"] == [
        "X-Hr-User-Token",
        "X-Hr-Thread-Id",
        "traceparent",
    ]
    assert props["Description"].startswith("HR self-service tools, source ")
    endpoint = json.dumps(props["TargetConfiguration"]["Mcp"]["McpServer"]["Endpoint"])
    assert "runtime%2F" in endpoint and "invocations?qualifier=DEFAULT" in endpoint
    deps = target["DependsOn"]
    assert any(d.startswith("HrToolsRuntime") for d in deps)
    assert any(d.startswith("ToolsGatewayRoleDefaultPolicy") for d in deps)


def test_tools_gateway_role_may_invoke_the_hr_tools_runtime(template):
    policies = [
        p
        for name, p in template.find_resources("AWS::IAM::Policy").items()
        if name.startswith("ToolsGatewayRoleDefaultPolicy")
    ]
    (policy,) = policies
    statements = policy["Properties"]["PolicyDocument"]["Statement"]
    assert any(s["Action"] == "bedrock-agentcore:InvokeAgentRuntime" for s in statements)


def test_hr_tables_are_on_demand_and_proposals_expire(template):
    tables = template.find_resources("AWS::DynamoDB::Table")
    assert len(tables) == 4
    for table in tables.values():
        assert table["Properties"]["BillingMode"] == "PAY_PER_REQUEST"
        assert "TableName" not in table["Properties"]  # generated names (D18)
    ttl = [t["Properties"].get("TimeToLiveSpecification") for t in tables.values()]
    assert {"AttributeName": "expires_at", "Enabled": True} in ttl


def test_orchestrator_routes_to_the_agents_gateway_on_sonnet(template):
    runtimes = template.find_resources(
        "AWS::BedrockAgentCore::Runtime", {"Properties": {"AgentRuntimeName": "hr_super_agent"}}
    )
    (runtime,) = runtimes.values()
    env = runtime["Properties"]["EnvironmentVariables"]
    assert env["ROUTER_MODEL_ID"] == env["MODEL_ID"] == "us.anthropic.claude-sonnet-4-6"
    assert env["ORCHESTRATOR_EXTRA_TOOLS"] == "hr___open_ticket"
    assert "HR_TOOL_PREFIX" not in env  # the write tools moved to the sub-agents (D22 ended)
    assert "SubAgentsGateway" in json.dumps(env["AGENTS_GATEWAY_URL"])
    policies = [
        p
        for name, p in template.find_resources("AWS::IAM::Policy").items()
        if name.startswith("RuntimeRoleDefaultPolicy")
    ]
    (policy,) = policies
    body = json.dumps(policy)
    assert "inference-profile/us.anthropic.claude-sonnet-4-6" in body
    assert "claude-haiku" not in body


def test_tools_role_scopes_its_logs_to_its_own_runtime(template):
    policies = [
        p
        for name, p in template.find_resources("AWS::IAM::Policy").items()
        if name.startswith("ToolsRuntimeRoleDefaultPolicy")
    ]
    (policy,) = policies
    body = json.dumps(policy)
    assert "runtimes/hr_super_agent_tools-*" in body
    assert "bedrock:InvokeModel" not in body
    assert "dynamodb:PutItem" in body


# ---- Sub-agents (phase 3) --------------------------------------------------------------


def _sub_agent_runtimes(template):
    return {
        r["Properties"]["AgentRuntimeName"]: r
        for r in template.find_resources(
            "AWS::BedrockAgentCore::Runtime", {"Properties": {"ProtocolConfiguration": "A2A"}}
        ).values()
    }


def test_three_a2a_sub_agents_with_jwt_authorizers(template):
    runtimes = _sub_agent_runtimes(template)
    assert set(runtimes) == {
        "hr_super_agent_profile",
        "hr_super_agent_pay",
        "hr_super_agent_travel",
    }
    for name, runtime in runtimes.items():
        props = runtime["Properties"]
        assert props["AuthorizerConfiguration"]["CustomJWTAuthorizer"]["DiscoveryUrl"]
        assert props["RequestHeaderConfiguration"]["RequestHeaderAllowlist"] == [
            "Authorization",
            "traceparent",
        ]
        env = props["EnvironmentVariables"]
        assert env["AGENT_ROLE"] == name.removeprefix("hr_super_agent_")
        assert env["HR_TOOL_PREFIX"] == "hr___"
        assert f"/{env['AGENT_ROLE']}/invocations/" in json.dumps(env["AGENTCORE_RUNTIME_URL"])
        assert any("RoleDefaultPolicy" in dep for dep in runtime["DependsOn"])


def test_agents_gateway_fronts_each_sub_agent_with_token_passthrough(template):
    gateways = template.find_resources(
        "AWS::BedrockAgentCore::Gateway", {"Properties": {"Name": "hr-super-agent-agents"}}
    )
    (gateway,) = gateways.values()
    assert "ProtocolType" not in gateway["Properties"]
    targets = [
        t
        for t in template.find_resources("AWS::BedrockAgentCore::GatewayTarget").values()
        if t["Properties"]["Name"] in ("profile", "pay", "travel")
    ]
    assert len(targets) == 3
    for target in targets:
        props = target["Properties"]
        assert props["CredentialProviderConfigurations"] == [
            {"CredentialProviderType": "JWT_PASSTHROUGH"}
        ]
        assert "AgentcoreRuntime" in props["TargetConfiguration"]["Http"]


def test_sub_agent_roles_reach_only_their_model(template):
    policies = [
        p
        for name, p in template.find_resources("AWS::IAM::Policy").items()
        if name.startswith("SubAgentsTravelRoleDefaultPolicy")
    ]
    (policy,) = policies
    body = json.dumps(policy)
    assert "claude-haiku-4-5" in body
    assert "runtimes/hr_super_agent_travel-*" in body
    assert "dynamodb" not in body


def test_every_new_runtime_and_the_agents_gateway_have_a_5xx_alarm(template):
    descriptions = {
        a["Properties"].get("AlarmDescription", "")
        for a in template.find_resources("AWS::CloudWatch::Alarm").values()
    }
    for subject in (
        "HR tools runtime",
        "agents gateway",
        "profile sub-agent runtime",
        "pay sub-agent runtime",
        "travel sub-agent runtime",
    ):
        assert any(subject in d and "5xx" in d for d in descriptions), subject


def test_log_delivery_names_are_unique_in_the_account(template):
    names = [
        r["Properties"]["Name"]
        for kind in ("AWS::Logs::DeliverySource", "AWS::Logs::DeliveryDestination")
        for r in template.find_resources(kind).values()
    ]
    assert len(names) == len(set(names))
    # The existing deliveries keep their names, so the deploy does not replace them.
    assert "hr-super-agent-tools-application-logs" in names
    assert "hr-super-agent-tools-runtime-application-logs" in names


def test_the_agents_gateway_url_is_published_for_the_connect_bridge(template):
    params = template.find_resources(
        "AWS::SSM::Parameter", {"Properties": {"Name": "/guppi-hr/agents-gateway-url"}}
    )
    assert len(params) == 1
    value = next(iter(params.values()))["Properties"]["Value"]
    assert "GatewayUrl" in json.dumps(value)
