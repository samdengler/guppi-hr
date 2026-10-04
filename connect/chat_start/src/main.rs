//! hr-chat-start in Lambda: the SDK clients, the WebSocket and the proxy response (lib.rs
//! decides). API Gateway's REST API invokes it through a standard Lambda proxy integration
//! (D57) and gets one buffered answer: `statusCode`, `headers` and a JSON `body`. A cold
//! start logs one `cold_start` line with each step's start and end in milliseconds, as the
//! token issuer does (guppi-gpt obo_issuer/src/main.rs).
//!
//! Until the function URL is removed (the last deploy of D57), a request through it is
//! read as the REST event and answered as before, streamed with its status in the prelude,
//! so the page CloudFront still serves keeps working while CloudFront moves to the API.

use std::collections::HashMap;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use async_trait::async_trait;
use aws_sdk_bedrockagentcore::types::Oauth2FlowType;
use aws_sdk_connect::error::ProvideErrorMetadata;
use aws_sdk_connectparticipant::types::{ConnectionType, SortKey};
use futures::{SinkExt, StreamExt};
use hr_chat_start::{
    App, Aws, AttributesError, Config, Connection, Fetcher, FlowSocket, Route, StartChat, Started, Timing, authorize,
    built_in_okta_keys, log, previous_contact, report, request_body, request_path, route, start,
};
use lambda_runtime::streaming::Body;
use lambda_runtime::{Error, FunctionResponse, LambdaEvent, MetadataPrelude, StreamResponse, service_fn};
use serde_json::{Map, Value, json};
use tokio_tungstenite::tungstenite::Message;

/// The bridge's `start_flow` connect timeout.
const FLOW_CONNECT_TIMEOUT: Duration = Duration::from_secs(20);

fn now() -> f64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs_f64()).unwrap_or(0.0)
}

/// The error's code, never its message: Identity's messages can quote claims.
fn code<E: ProvideErrorMetadata>(error: &aws_sdk_connect::error::SdkError<E>) -> String {
    match error {
        aws_sdk_connect::error::SdkError::ServiceError(inner) => inner.err().code().unwrap_or("ServiceError").to_string(),
        aws_sdk_connect::error::SdkError::TimeoutError(_) => "TimeoutError".into(),
        aws_sdk_connect::error::SdkError::DispatchFailure(_) => "DispatchFailure".into(),
        aws_sdk_connect::error::SdkError::ResponseError(_) => "ResponseError".into(),
        _ => "SdkError".into(),
    }
}

struct AwsClients {
    identity: aws_sdk_bedrockagentcore::Client,
    connect: aws_sdk_connect::Client,
    participant: aws_sdk_connectparticipant::Client,
}

#[async_trait]
impl Aws for AwsClients {
    async fn workload_token(&self, workload: &str, user_token: &str) -> Result<String, String> {
        let out = self
            .identity
            .get_workload_access_token_for_jwt()
            .workload_name(workload)
            .user_token(user_token)
            .send()
            .await
            .map_err(|e| code(&e))?;
        Ok(out.workload_access_token)
    }

    async fn hop_token(&self, workload_token: &str, provider: &str, scopes: &[String]) -> Result<String, String> {
        let out = self
            .identity
            .get_resource_oauth2_token()
            .workload_identity_token(workload_token)
            .resource_credential_provider_name(provider)
            .oauth2_flow(Oauth2FlowType::OnBehalfOfTokenExchange)
            .set_scopes(Some(scopes.to_vec()))
            .custom_parameters("subject_token_type", hr_chat_start::ACCESS_TOKEN_TYPE)
            .send()
            .await
            .map_err(|e| code(&e))?;
        out.access_token.ok_or_else(|| "no access token".to_string())
    }

    async fn start_chat(&self, request: &StartChat) -> Result<Started, String> {
        let details = aws_sdk_connect::types::ParticipantDetails::builder()
            .display_name(&request.display_name)
            .build()
            .map_err(|_| "ParticipantDetails".to_string())?;
        let out = self
            .connect
            .start_chat_contact()
            .instance_id(&request.instance_id)
            .contact_flow_id(&request.contact_flow_id)
            .participant_details(details)
            .set_attributes(Some(request.attributes.clone()))
            .set_supported_messaging_content_types(Some(request.content_types.clone()))
            .chat_duration_in_minutes(request.duration_minutes)
            .send()
            .await
            .map_err(|e| code(&e))?;
        Ok(Started {
            contact_id: out.contact_id.ok_or("no contact id")?,
            participant_id: out.participant_id.ok_or("no participant id")?,
            participant_token: out.participant_token.ok_or("no participant token")?,
        })
    }

    async fn create_connection(&self, participant_token: &str) -> Result<Connection, String> {
        let out = self
            .participant
            .create_participant_connection()
            .r#type(ConnectionType::Websocket)
            .r#type(ConnectionType::ConnectionCredentials)
            .participant_token(participant_token)
            .send()
            .await
            .map_err(|e| code(&e))?;
        Ok(Connection {
            websocket_url: out.websocket.and_then(|w| w.url).ok_or("no websocket url")?,
            connection_token: out.connection_credentials.and_then(|c| c.connection_token).ok_or("no connection token")?,
        })
    }

    async fn open_flow(&self, url: &str) -> Result<Box<dyn FlowSocket>, String> {
        let opened = tokio::time::timeout(FLOW_CONNECT_TIMEOUT, async {
            let (mut ws, _) = tokio_tungstenite::connect_async(url).await.map_err(|e| format!("connect: {}", kind(&e)))?;
            let subscribe = json!({"topic": "aws/subscribe", "content": {"topics": ["aws/chat"]}});
            ws.send(Message::text(subscribe.to_string())).await.map_err(|e| format!("subscribe: {}", kind(&e)))?;
            // Connect's acknowledgement of the subscription; the flow starts after it (C1).
            loop {
                match ws.next().await {
                    Some(Ok(Message::Text(_) | Message::Binary(_))) => break,
                    Some(Ok(_)) => continue,
                    Some(Err(e)) => return Err(format!("acknowledgement: {}", kind(&e))),
                    None => return Err("closed before the acknowledgement".to_string()),
                }
            }
            Ok::<_, String>(ws)
        })
        .await
        .map_err(|_| "flow socket timeout".to_string())??;
        Ok(Box::new(Socket(opened)))
    }

    async fn transcript(&self, connection_token: &str) -> Result<Vec<Value>, String> {
        let out = self
            .participant
            .get_transcript()
            .connection_token(connection_token)
            .sort_order(SortKey::Descending)
            .max_results(100)
            .send()
            .await
            .map_err(|e| code(&e))?;
        Ok(out
            .transcript
            .unwrap_or_default()
            .into_iter()
            .map(|item| {
                json!({
                    "Id": item.id,
                    "Type": item.r#type.map(|t| t.as_str().to_string()),
                    "ContentType": item.content_type,
                    "ParticipantRole": item.participant_role.map(|r| r.as_str().to_string()),
                    "Content": item.content,
                    "AbsoluteTime": item.absolute_time,
                })
            })
            .collect())
    }

    async fn update_attributes(&self, instance_id: &str, contact_id: &str, attributes: &HashMap<String, String>) -> Result<(), String> {
        self.connect
            .update_contact_attributes()
            .instance_id(instance_id)
            .initial_contact_id(contact_id)
            .set_attributes(Some(attributes.clone()))
            .send()
            .await
            .map(|_| ())
            .map_err(|e| code(&e))
    }

    async fn stop_contact(&self, instance_id: &str, contact_id: &str) -> Result<(), String> {
        self.connect.stop_contact().instance_id(instance_id).contact_id(contact_id).send().await.map(|_| ()).map_err(|e| code(&e))
    }

    async fn contact_attributes(&self, instance_id: &str, contact_id: &str) -> Result<HashMap<String, String>, AttributesError> {
        match self.connect.get_contact_attributes().instance_id(instance_id).initial_contact_id(contact_id).send().await {
            Ok(out) => Ok(out.attributes.unwrap_or_default()),
            Err(e) => match code(&e).as_str() {
                "ResourceNotFoundException" => Err(AttributesError::NotFound),
                other => Err(AttributesError::Failed(other.to_string())),
            },
        }
    }
}

/// A WebSocket error's kind, without its text (which can carry the URL and its token).
fn kind(error: &tokio_tungstenite::tungstenite::Error) -> &'static str {
    use tokio_tungstenite::tungstenite::Error as E;
    match error {
        E::ConnectionClosed | E::AlreadyClosed => "closed",
        E::Io(_) => "io",
        E::Tls(_) => "tls",
        E::Http(_) | E::HttpFormat(_) => "http",
        E::Url(_) => "url",
        E::Protocol(_) => "protocol",
        _ => "other",
    }
}

struct Socket(tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>);

#[async_trait]
impl FlowSocket for Socket {
    async fn receive(&mut self, wait: Duration) -> Result<Option<String>, String> {
        let deadline = tokio::time::Instant::now() + wait;
        loop {
            match tokio::time::timeout_at(deadline, self.0.next()).await {
                Err(_) => return Ok(None),
                Ok(Some(Ok(Message::Text(text)))) => return Ok(Some(text.to_string())),
                Ok(Some(Ok(Message::Binary(data)))) => return Ok(Some(String::from_utf8_lossy(&data).into_owned())),
                Ok(Some(Ok(Message::Close(_)))) | Ok(None) => return Err("closed".to_string()),
                Ok(Some(Ok(_))) => continue,
                Ok(Some(Err(e))) => return Err(kind(&e).to_string()),
            }
        }
    }

    async fn close(&mut self) {
        let _ = tokio::time::timeout(Duration::from_millis(500), self.0.close(None)).await;
    }
}

struct HttpFetcher(reqwest::Client);

#[async_trait]
impl Fetcher for HttpFetcher {
    async fn fetch_json(&self, url: &str) -> Result<Value, String> {
        let response = self.0.get(url).send().await.map_err(|e| e.to_string())?;
        response.error_for_status().map_err(|e| e.to_string())?.json().await.map_err(|e| e.to_string())
    }
}

/// API Gateway's proxy response: the status, the headers and the body as JSON text.
fn proxy_answer(status: u16, body: &Value) -> Value {
    json!({
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": body.to_string(),
        "isBase64Encoded": false,
    })
}

/// A function URL's event (it has `rawPath`) in the REST proxy event's fields, or None.
/// Removed with the function URL.
fn from_function_url(event: &Value) -> Option<Value> {
    let path = event.get("rawPath")?.clone();
    Some(json!({
        "path": path,
        "httpMethod": event.pointer("/requestContext/http/method").cloned().unwrap_or(Value::Null),
        "headers": event.get("headers").cloned().unwrap_or(Value::Null),
        "body": event.get("body").cloned().unwrap_or(Value::Null),
        "isBase64Encoded": event.get("isBase64Encoded").cloned().unwrap_or(Value::Bool(false)),
    }))
}

/// The answer through the function URL as the page before D57 reads it: streamed, the status
/// in the prelude, the body one NDJSON line. Removed with the function URL.
fn streamed_answer(status: u16, body: &Value) -> StreamResponse<Body> {
    let mut headers = http::HeaderMap::new();
    let content_type = if status == 200 && body.get("ok").is_none() { "application/x-ndjson" } else { "application/json" };
    headers.insert(http::header::CONTENT_TYPE, http::HeaderValue::from_static(content_type));
    headers.insert(http::header::CACHE_CONTROL, http::HeaderValue::from_static("no-store"));
    let metadata_prelude =
        MetadataPrelude { status_code: http::StatusCode::from_u16(status).unwrap_or(http::StatusCode::OK), headers, cookies: Vec::new() };
    StreamResponse { metadata_prelude, stream: Body::from(format!("{body}\n")) }
}

fn ms(since: Instant) -> u64 {
    since.elapsed().as_millis() as u64
}

async fn load() -> Result<(Arc<App>, u64), Error> {
    let t0 = Instant::now();
    let mut steps = Map::new();
    let started = Instant::now();
    let config = aws_config::defaults(aws_config::BehaviorVersion::latest())
        .timeout_config(
            aws_config::timeout::TimeoutConfig::builder()
                .connect_timeout(Duration::from_secs(2))
                .read_timeout(Duration::from_secs(5))
                .build(),
        )
        .retry_config(aws_config::retry::RetryConfig::standard().with_max_attempts(2))
        .load()
        .await;
    steps.insert("config".into(), json!([0, ms(started)]));
    let clients_at = ms(t0);
    let aws = AwsClients {
        identity: aws_sdk_bedrockagentcore::Client::new(&config),
        connect: aws_sdk_connect::Client::new(&config),
        participant: aws_sdk_connectparticipant::Client::new(&config),
    };
    steps.insert("clients".into(), json!([clients_at, ms(t0)]));
    let settings = Config::from_env()?;
    let fetcher = HttpFetcher(reqwest::Client::builder().timeout(Duration::from_secs(3)).build()?);
    let app = App::new(settings, Arc::new(aws), Arc::new(fetcher), built_in_okta_keys(now()), Arc::new(now));
    let load_ms = ms(t0);
    log(json!({"event": "cold_start", "load_ms": load_ms, "steps": steps}));
    Ok((Arc::new(app), load_ms))
}

/// The status and the JSON body for one request.
async fn handle(app: Arc<App>, event: Value, cold: bool) -> (u16, Value) {
    let t0 = tokio::time::Instant::now();
    let which = route(&event);
    let path = request_path(&event).chars().take(64).collect::<String>();
    match which {
        Route::NotFound => return (404, json!({"error": "not_found"})),
        Route::NotAllowed => return (405, json!({"error": "method_not_allowed"})),
        Route::Start | Route::Report => {}
    }
    let caller = match authorize(&app, &event).await {
        Ok(caller) => caller,
        Err(reason) => {
            log(json!({"event": "chat_unauthorized", "path": path, "reason": reason, "cold": cold}));
            return (401, json!({"error": "unauthorized"}));
        }
    };
    let body = match request_body(&event) {
        Ok(body) => body,
        Err(reason) => {
            log(json!({"event": "chat_bad_request", "path": path, "reason": reason}));
            return (400, json!({"error": "bad_request"}));
        }
    };
    let timing = Timing::new(t0);
    if which == Route::Report {
        let (status, body) = report(&app, &caller, &body, &timing).await;
        return (status, body.unwrap_or_else(|| json!({})));
    }
    let previous = match previous_contact(&body) {
        Ok(previous) => previous,
        Err(reason) => {
            log(json!({"event": "chat_bad_request", "path": path, "reason": reason}));
            return (400, json!({"error": "bad_request"}));
        }
    };
    (200, start(&app, &caller, previous, &timing, cold).await)
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    // reqwest and the AWS SDK bring their own TLS settings; the WebSocket uses the default.
    let _ = rustls::crypto::ring::default_provider().install_default();
    let (app, load_ms) = load().await?;
    let first = Arc::new(AtomicBool::new(true));
    lambda_runtime::run(service_fn(move |event: LambdaEvent<Value>| {
        let (app, first) = (app.clone(), first.clone());
        async move {
            let cold = first.swap(false, Ordering::Relaxed);
            if cold {
                log(json!({"event": "first_request", "load_ms": load_ms}));
            }
            match from_function_url(&event.payload) {
                Some(event) => {
                    let (status, body) = handle(app, event, cold).await;
                    Ok::<_, Error>(FunctionResponse::StreamingResponse(streamed_answer(status, &body)))
                }
                None => {
                    let (status, body) = handle(app, event.payload, cold).await;
                    Ok(FunctionResponse::BufferedResponse(proxy_answer(status, &body)))
                }
            }
        }
    }))
    .await
}
