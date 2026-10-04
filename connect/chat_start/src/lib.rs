//! hr-chat-start: the chat start for /p/hr/ (guppi-hr D55; docs/proposals/connect-chatjs.md).
//!
//! The page starts each Amazon Connect chat here and then talks to Connect's participant
//! service itself with amazon-connect-chatjs. Two routes, both POST, chosen by the path's
//! suffix, behind a Lambda function URL that streams its response (CloudFront sends
//! https://chat.dengler.io/api/hr/chat/* here with the path unchanged):
//!
//! - `/chat/start`: verifies the Okta access token, ends the caller's previous contact when
//!   asked, trades the token through AgentCore Identity for the hop tokens the designer
//!   carries (D47, D48), starts the contact with them as attributes, opens the customer's
//!   WebSocket so the flow runs, waits for the designer's greeting, blanks the token
//!   attributes (D42, D53) and only then streams line 1 with the participant token. The
//!   three sub-agent warm-ups (D41) run beside the greeting wait; line 2 says how many
//!   succeeded. These are the bridge's steps (connect_bridge/turn.py: `hop_tokens`,
//!   `start_contact`, `await_greeting`, `clear_token`, `warm_sub_agent`, `end_contact`),
//!   with the same scopes, attributes, limits and request bodies.
//! - `/chat/report`: the page's record of one turn, checked against the contact's
//!   `employeeId`, written as one run line, with `chat_problem` lines for the alarm.
//!
//! The function verifies the token itself, since a function URL has no JWT authorizer, with
//! the token issuer's RS256 verifier and Okta's keys built in (guppi-gpt's obo_issuer, D51).
//! Nothing logged or returned holds the Okta token or a hop token. This file decides;
//! `main.rs` reaches AWS. `tests.rs` replaces AWS and Okta with fakes.

use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::{Arc, Mutex as StdMutex};
use std::time::Duration;

use async_trait::async_trait;
use base64::Engine;
use base64::engine::general_purpose::{GeneralPurpose, GeneralPurposeConfig, STANDARD};
use base64::engine::DecodePaddingMode;
use num_bigint::BigUint;
use serde_json::{Map, Value, json};
use sha2::{Digest, Sha256};
use subtle::ConstantTimeEq;
use tokio::sync::Mutex;
use tokio::time::Instant;

pub const REGION: &str = "us-east-1";
pub const ACCESS_TOKEN_TYPE: &str = "urn:ietf:params:oauth:token-type:access_token";
/// The sub-agents, each with its own agents token (D48), and the designer's read-only tools
/// token: the bridge's AGENTS_TOKENS and CANVAS_TOKENS.
pub const DOMAINS: [&str; 3] = ["profile", "pay", "travel"];
pub const CANVAS_SCOPES: [&str; 3] = ["hr.tools.policy", "hr.tools.profile.read", "hr.tools.pay.statements.read"];
pub const TOOLS_ATTRIBUTE: &str = "hrToolsToken";
pub const CLEARED: &str = "cleared";
/// Connect's minimum; the default of 25 hours held chats against the quota (D42).
pub const CHAT_DURATION_MINUTES: i32 = 60;
/// The page restarts a chat this long before Connect would end it.
pub const CHAT_MARGIN_MS: i64 = 2 * 60 * 1000;
/// The designer drops a message sent before it greets, so no greeting in this long is a
/// failed start (the bridge's GREETING_LIMIT).
pub const GREETING_LIMIT: Duration = Duration::from_secs(12);
/// A quiet greeting socket this long sends the wait to the transcript once.
pub const GREETING_CHECK: Duration = Duration::from_secs(1);
pub const POLL_INTERVAL: Duration = Duration::from_millis(300);
/// The bridge's SUB_AGENT_WARM_TIMEOUT. The warm-ups start together, so line 2 comes at most
/// this long after StartChatContact returns.
pub const SUB_AGENT_WARM_TIMEOUT: Duration = Duration::from_secs(15);
const WARM_GUARD: Duration = Duration::from_secs(16);
pub const MAX_BODY_BYTES: usize = 16 * 1024;
const MAX_ID_CHARS: usize = 128;
const CACHE_MARGIN: f64 = 60.0;
const MAX_CACHED: usize = 256;
const MAX_SEEN_RUNS: usize = 1024;
/// How a page's turn can end (the transport's turn assembler).
pub const END_REASONS: [&str; 7] = ["end_mark", "closed", "ended", "quiet", "no_reply", "error", "aborted"];
pub const TRANSPORTS: [&str; 2] = ["connect", "bridge"];

// ---- the token verifier ------------------------------------------------------------------
//
// Copied from guppi-gpt infra/guppi_gpt_infra/lambdas/obo_issuer/src/lib.rs (b64u, unb64u,
// rs256_valid, Fetcher, OktaKeys, keys_by_kid, okta_key and the Okta half of verify), so the
// two functions accept the same tokens. Changes: Okta tokens only (no issuer-signed branch),
// refusals as a reason string, and the settings read from `App`.

pub const LEEWAY: f64 = 60.0;
/// A token this close to expiry is refused; the exchange would refuse it too.
pub const MIN_REMAINING: f64 = 60.0;
pub const JWKS_TTL: f64 = 3600.0;
pub const JWKS_REFETCH_MIN_INTERVAL: f64 = 60.0;
pub const MAX_TOKEN_LENGTH: usize = 8192;
const SHA256_DIGEST_INFO: [u8; 19] = [
    0x30, 0x31, 0x30, 0x0d, 0x06, 0x09, 0x60, 0x86, 0x48, 0x01, 0x65, 0x03, 0x04, 0x02, 0x01, 0x05, 0x00, 0x04, 0x20,
];

/// Okta's public keys as of the build: a copy of guppi-gpt's obo_issuer/okta-keys.json,
/// which guppi-gpt's scripts/okta.py writes.
pub const BUILT_IN_OKTA_KEYS: &str = include_str!("../okta-keys.json");

/// Base64url as JWTs use it: no padding on the way out, padding optional on the way in.
const B64U: GeneralPurpose = GeneralPurpose::new(
    &base64::alphabet::URL_SAFE,
    GeneralPurposeConfig::new()
        .with_encode_padding(false)
        .with_decode_padding_mode(DecodePaddingMode::Indifferent)
        .with_decode_allow_trailing_bits(true),
);

pub fn b64u(data: &[u8]) -> String {
    B64U.encode(data)
}

pub fn unb64u(text: &str) -> Option<Vec<u8>> {
    B64U.decode(text).ok()
}

/// RSASSA-PKCS1-v1_5 with SHA-256 (RFC 8017 8.2.2), by re-encoding and comparing.
pub fn rs256_valid(jwk: &Value, signing_input: &[u8], signature: &[u8]) -> bool {
    let part = |name: &str| jwk.get(name).and_then(Value::as_str).and_then(unb64u);
    let (Some(n), Some(e)) = (part("n"), part("e")) else { return false };
    let n = BigUint::from_bytes_be(&n);
    let e = BigUint::from_bytes_be(&e);
    let k = n.bits().div_ceil(8) as usize;
    if n.bits() < 2048 || signature.len() != k {
        return false;
    }
    let s = BigUint::from_bytes_be(signature);
    if s >= n {
        return false;
    }
    let m = s.modpow(&e, &n).to_bytes_be();
    let mut em = vec![0u8; k - m.len()];
    em.extend_from_slice(&m);
    let mut t = SHA256_DIGEST_INFO.to_vec();
    t.extend_from_slice(&Sha256::digest(signing_input));
    let mut expected = vec![0x00, 0x01];
    expected.resize(k - t.len() - 1, 0xff);
    expected.push(0x00);
    expected.extend_from_slice(&t);
    em.ct_eq(&expected).into()
}

/// Fetches a JSON document (Okta's keys).
#[async_trait]
pub trait Fetcher: Send + Sync {
    async fn fetch_json(&self, url: &str) -> Result<Value, String>;
}

/// Okta's keys by kid, when they were fetched, and when a fetch was last tried.
#[derive(Default)]
pub struct OktaKeys {
    pub keys: HashMap<String, Value>,
    pub fetched_at: f64,
    pub refetch_at: f64,
}

/// The keys of a JWKS document, by kid.
pub fn keys_by_kid(jwks: &Value) -> Option<HashMap<String, Value>> {
    let keys = jwks.get("keys")?.as_array()?;
    Some(
        keys.iter()
            .filter_map(|k| Some((k.get("kid")?.as_str()?.to_string(), k.clone())))
            .collect(),
    )
}

/// The Okta key named `kid`. A key the function does not have is fetched before answering,
/// at most once a minute; keys older than an hour are refreshed in the background, so a
/// known key never waits on Okta.
async fn okta_key(app: &App, kid: &str) -> Option<Value> {
    let now = app.now();
    let url = format!("{}/v1/keys", app.config.okta_issuer);
    let mut okta = app.okta.lock().await;
    let stale = now - okta.fetched_at > JWKS_TTL;
    let unknown = !okta.keys.contains_key(kid);
    if (stale || unknown) && now - okta.refetch_at >= JWKS_REFETCH_MIN_INTERVAL {
        okta.refetch_at = now;
        if unknown {
            if let Some(keys) = app.fetcher.fetch_json(&url).await.ok().as_ref().and_then(keys_by_kid) {
                okta.keys = keys;
                okta.fetched_at = now;
            }
        } else {
            let (fetcher, shared) = (app.fetcher.clone(), app.okta.clone());
            tokio::spawn(async move {
                if let Some(keys) = fetcher.fetch_json(&url).await.ok().as_ref().and_then(keys_by_kid) {
                    let mut okta = shared.lock().await;
                    okta.keys = keys;
                    okta.fetched_at = now;
                }
            });
        }
    }
    okta.keys.get(kid).cloned()
}

fn number(claims: &Map<String, Value>, name: &str) -> Option<f64> {
    claims.get(name).and_then(Value::as_f64)
}

/// The Okta access token's claims, or why it was refused: the issuer's checks for an Okta
/// subject token (issuer, RS256 signature by a known key, exp, iat, nbf, a minute left,
/// audience, a chat client in `cid`, and a `uid`).
pub async fn verify(token: &str, app: &App) -> Result<Map<String, Value>, &'static str> {
    if token.is_empty() || token.chars().count() > MAX_TOKEN_LENGTH || token.matches('.').count() != 2 {
        return Err("malformed token");
    }
    let mut parts = token.split('.');
    let (head, body, sig) = (parts.next().unwrap_or(""), parts.next().unwrap_or(""), parts.next().unwrap_or(""));
    let decoded = |part: &str| unb64u(part).and_then(|bytes| serde_json::from_slice::<Value>(&bytes).ok());
    let (Some(header), Some(claims), Some(signature)) = (decoded(head), decoded(body), unb64u(sig)) else {
        return Err("undecodable token");
    };
    let (Value::Object(header), Value::Object(claims)) = (header, claims) else {
        return Err("malformed token");
    };
    if header.get("alg").and_then(Value::as_str) != Some("RS256") || header.contains_key("crit") {
        return Err("unsupported token header");
    }
    if claims.get("iss").and_then(Value::as_str) != Some(app.config.okta_issuer.as_str()) {
        return Err("untrusted issuer");
    }
    let kid = match header.get("kid") {
        Some(Value::String(kid)) => kid.clone(),
        Some(other) => other.to_string(),
        None => String::new(),
    };
    let key = okta_key(app, &kid).await;
    let signing_input = format!("{head}.{body}");
    if !key.is_some_and(|key| rs256_valid(&key, signing_input.as_bytes(), &signature)) {
        return Err("bad signature");
    }
    let now = app.now();
    let (Some(exp), Some(iat)) = (number(&claims, "exp"), number(&claims, "iat")) else {
        return Err(if number(&claims, "exp").is_none() { "missing exp" } else { "missing iat" });
    };
    let nbf = match claims.get("nbf") {
        None => 0.0,
        Some(value) => value.as_f64().ok_or("malformed nbf")?,
    };
    if exp <= now - LEEWAY {
        return Err("expired");
    }
    if iat > now + LEEWAY || nbf > now + LEEWAY {
        return Err("not yet valid");
    }
    if exp - now < MIN_REMAINING {
        return Err("expires too soon");
    }
    if claims.get("aud").and_then(Value::as_str) != Some(app.config.okta_audience.as_str()) {
        return Err("okta audience");
    }
    if !claims.get("cid").and_then(Value::as_str).is_some_and(|cid| app.config.okta_clients.contains(cid)) {
        return Err("okta client");
    }
    if !claims.get("uid").and_then(Value::as_str).is_some_and(|uid| !uid.is_empty()) {
        return Err("okta token without uid");
    }
    Ok(claims)
}

// ---- what the function reaches -----------------------------------------------------------

/// StartChatContact's request, as the bridge's `start_contact` sends it.
#[derive(Clone, Debug)]
pub struct StartChat {
    pub instance_id: String,
    pub contact_flow_id: String,
    pub display_name: String,
    pub attributes: HashMap<String, String>,
    pub content_types: Vec<String>,
    pub duration_minutes: i32,
}

#[derive(Clone, Debug)]
pub struct Started {
    pub contact_id: String,
    pub participant_id: String,
    pub participant_token: String,
}

#[derive(Clone, Debug)]
pub struct Connection {
    pub websocket_url: String,
    pub connection_token: String,
}

#[derive(Debug)]
pub enum AttributesError {
    NotFound,
    Failed(String),
}

/// Every AWS and HTTP call; main.rs implements it with the SDK, the tests with fakes.
/// Errors are an error class or code only: Identity's messages can quote claims.
#[async_trait]
pub trait Aws: Send + Sync {
    async fn workload_token(&self, workload: &str, user_token: &str) -> Result<String, String>;
    async fn hop_token(&self, workload_token: &str, provider: &str, scopes: &[String]) -> Result<String, String>;
    async fn start_chat(&self, request: &StartChat) -> Result<Started, String>;
    async fn create_connection(&self, participant_token: &str) -> Result<Connection, String>;
    /// The customer's WebSocket, connected, subscribed to `aws/chat` and acknowledged. The
    /// flow starts once Connect acknowledges the subscription (C1).
    async fn open_flow(&self, url: &str) -> Result<Box<dyn FlowSocket>, String>;
    /// Transcript items, newest first, as Connect's JSON (Id, Type, ContentType,
    /// ParticipantRole, Content, AbsoluteTime).
    async fn transcript(&self, connection_token: &str) -> Result<Vec<Value>, String>;
    async fn update_attributes(&self, instance_id: &str, contact_id: &str, attributes: &HashMap<String, String>) -> Result<(), String>;
    async fn stop_contact(&self, instance_id: &str, contact_id: &str) -> Result<(), String>;
    async fn contact_attributes(&self, instance_id: &str, contact_id: &str) -> Result<HashMap<String, String>, AttributesError>;
    async fn post_json(&self, url: &str, headers: &[(String, String)], body: &Value, timeout: Duration) -> Result<u16, String>;
}

#[async_trait]
pub trait FlowSocket: Send {
    /// The next text frame; None when none came within `wait`; Err when the socket failed.
    async fn receive(&mut self, wait: Duration) -> Result<Option<String>, String>;
    async fn close(&mut self);
}

/// Where the start route writes its NDJSON lines.
#[async_trait]
pub trait Lines: Send {
    async fn line(&mut self, value: &Value);
}

pub struct Config {
    pub okta_issuer: String,
    pub okta_audience: String,
    pub okta_clients: HashSet<String>,
    pub instance_id: String,
    pub contact_flow_id: String,
    pub agents_gateway_url: String,
    pub warm_domains: Vec<String>,
    pub provider: String,
    pub workload: String,
}

impl Config {
    pub fn from_env() -> Result<Self, String> {
        let var = |name: &str| std::env::var(name).map_err(|_| format!("{name} is not set"));
        let list = |text: String| text.split(',').map(str::trim).filter(|s| !s.is_empty()).map(String::from).collect::<Vec<_>>();
        Ok(Config {
            okta_issuer: var("OKTA_ISSUER")?.trim_end_matches('/').to_string(),
            okta_audience: var("OKTA_AUDIENCE")?,
            okta_clients: list(var("OKTA_CLIENTS")?).into_iter().collect(),
            instance_id: var("CONNECT_INSTANCE_ID")?,
            contact_flow_id: var("CONTACT_FLOW_ID")?,
            agents_gateway_url: var("AGENTS_GATEWAY_URL").unwrap_or_default().trim_end_matches('/').to_string(),
            warm_domains: list(var("WARM_DOMAINS").unwrap_or_else(|_| DOMAINS.join(","))),
            // Without both an exchange fails, so the Okta token never reaches a contact (D48).
            provider: var("OBO_PROVIDER").unwrap_or_default(),
            workload: var("OBO_WORKLOAD").unwrap_or_default(),
        })
    }
}

/// The hop tokens of one Okta token.
#[derive(Clone)]
pub struct HopTokens {
    /// By sub-agent, in DOMAINS order.
    pub agents: Vec<(String, String)>,
    pub tools: String,
}

impl HopTokens {
    pub fn agents_token(&self, domain: &str) -> Option<&str> {
        self.agents.iter().find(|(d, _)| d == domain).map(|(_, t)| t.as_str())
    }

    /// The earliest `exp` of the four, in epoch seconds.
    pub fn min_exp(&self, now: f64) -> f64 {
        self.agents.iter().map(|(_, t)| t).chain([&self.tools]).map(|t| expires_at(t, now)).fold(f64::INFINITY, f64::min)
    }
}

pub struct App {
    pub config: Config,
    pub aws: Arc<dyn Aws>,
    pub fetcher: Arc<dyn Fetcher>,
    pub okta: Arc<Mutex<OktaKeys>>,
    /// Epoch seconds.
    pub clock: Arc<dyn Fn() -> f64 + Send + Sync>,
    /// Hop tokens by the Okta token's hash, as the bridge's exchangers cache them, so a new
    /// chat on the same sign-in makes no issuer call while this instance lives.
    pub hop_cache: StdMutex<HashMap<[u8; 32], HopTokens>>,
    pub seen_runs: StdMutex<VecDeque<String>>,
}

impl App {
    pub fn new(config: Config, aws: Arc<dyn Aws>, fetcher: Arc<dyn Fetcher>, okta: OktaKeys, clock: Arc<dyn Fn() -> f64 + Send + Sync>) -> Self {
        App {
            config,
            aws,
            fetcher,
            okta: Arc::new(Mutex::new(okta)),
            clock,
            hop_cache: StdMutex::new(HashMap::new()),
            seen_runs: StdMutex::new(VecDeque::new()),
        }
    }

    pub fn now(&self) -> f64 {
        (self.clock)()
    }

    fn now_ms(&self) -> i64 {
        (self.now() * 1000.0).floor() as i64
    }
}

/// The built-in Okta keys, as the issuer loads them.
pub fn built_in_okta_keys(now: f64) -> OktaKeys {
    let keys = serde_json::from_str::<Value>(BUILT_IN_OKTA_KEYS).ok().as_ref().and_then(keys_by_kid).unwrap_or_default();
    OktaKeys { keys, fetched_at: now, refetch_at: 0.0 }
}

// ---- logging -----------------------------------------------------------------------------

pub fn log(fields: Value) {
    println!("{fields}");
    #[cfg(test)]
    tests::LOGS.with(|logs| logs.borrow_mut().push(fields));
}

/// One line the stack's alarm counts: `chat_problem` and its kind (no_greeting,
/// token_not_cleared, exchange_failed, contact_not_ended; from reports no_reply,
/// designer_error, socket_failed). The bridge's `problem`.
pub fn problem(kind: &str, contact: &str, detail: &str) {
    log(json!({"event": "chat_problem", "kind": kind, "contact": contact, "detail": detail}));
}

// ---- timing ------------------------------------------------------------------------------

/// The request's steps in milliseconds from the function taking it, in the guppi.timing
/// shape (D54): name, start_ms, end_ms (None for a point) and lane. Shared by the tasks of
/// one request.
#[derive(Clone)]
pub struct Timing {
    t0: Instant,
    steps: Arc<StdMutex<Vec<Value>>>,
    notes: Arc<StdMutex<Vec<String>>>,
}

pub const LANE: &str = "chat-start";

impl Timing {
    pub fn new(t0: Instant) -> Self {
        Timing { t0, steps: Arc::default(), notes: Arc::default() }
    }

    pub fn ms(&self) -> u64 {
        self.t0.elapsed().as_millis() as u64
    }

    pub fn add(&self, name: &str, start_ms: u64, end_ms: Option<u64>, lane: &str) {
        if let Ok(mut steps) = self.steps.lock() {
            steps.push(json!({"name": name, "start_ms": start_ms, "end_ms": end_ms.map(|e| e.max(start_ms)), "lane": lane}));
        }
    }

    pub fn point(&self, name: &str, lane: &str) -> u64 {
        let at = self.ms();
        self.add(name, at, None, lane);
        at
    }

    /// `step` recorded as one step, " (failed)" when it returns an error.
    pub async fn timed<T, E>(&self, name: &str, lane: &str, step: impl Future<Output = Result<T, E>>) -> Result<T, E> {
        let start = self.ms();
        let out = step.await;
        let name = if out.is_ok() { name.to_string() } else { format!("{name} (failed)") };
        self.add(&name, start, Some(self.ms()), lane);
        out
    }

    pub fn note(&self, text: &str) {
        if let Ok(mut notes) = self.notes.lock() {
            if !notes.iter().any(|n| n == text) {
                notes.push(text.to_string());
            }
        }
    }

    pub fn steps(&self) -> Vec<Value> {
        let mut steps = self.steps.lock().map(|s| s.clone()).unwrap_or_default();
        steps.sort_by_key(|s| (s["start_ms"].as_u64().unwrap_or(0), s["end_ms"].is_null()));
        steps
    }

    pub fn value(&self, contact: Option<&str>) -> Value {
        let total = self.ms();
        let mut steps = self.steps();
        steps.push(json!({"name": "total", "start_ms": 0, "end_ms": total, "lane": LANE}));
        let notes = self.notes.lock().map(|n| n.clone()).unwrap_or_default();
        json!({"steps": steps, "total_ms": total, "ids": {"contact": contact}, "notes": notes})
    }
}

// ---- requests ----------------------------------------------------------------------------

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Route {
    Start,
    Report,
    NotFound,
    NotAllowed,
}

/// The route, by the path's suffix (CloudFront passes /api/hr/chat/... through unchanged).
pub fn route(event: &Value) -> Route {
    let path = event.get("rawPath").and_then(Value::as_str).unwrap_or("");
    let method = event.pointer("/requestContext/http/method").and_then(Value::as_str).unwrap_or("");
    let found = if path.ends_with("/chat/start") {
        Route::Start
    } else if path.ends_with("/chat/report") {
        Route::Report
    } else {
        return Route::NotFound;
    };
    if method == "POST" { found } else { Route::NotAllowed }
}

/// A request header by name, whatever its case.
pub fn header<'a>(event: &'a Value, name: &str) -> &'a str {
    event
        .get("headers")
        .and_then(Value::as_object)
        .and_then(|headers| headers.iter().find(|(key, _)| key.to_lowercase() == name))
        .and_then(|(_, value)| value.as_str())
        .unwrap_or("")
}

/// The request body as a JSON object; an empty body is `{}`.
pub fn request_body(event: &Value) -> Result<Map<String, Value>, &'static str> {
    let raw = event.get("body").and_then(Value::as_str).unwrap_or("");
    let bytes = if event.get("isBase64Encoded").and_then(Value::as_bool).unwrap_or(false) {
        STANDARD.decode(raw).map_err(|_| "body")?
    } else {
        raw.as_bytes().to_vec()
    };
    if bytes.len() > MAX_BODY_BYTES {
        return Err("body too large");
    }
    if bytes.iter().all(u8::is_ascii_whitespace) {
        return Ok(Map::new());
    }
    match serde_json::from_slice::<Value>(&bytes) {
        Ok(Value::Object(map)) => Ok(map),
        _ => Err("body is not a JSON object"),
    }
}

/// The signed-in employee: the verified Okta token, its `uid` and `exp`.
pub struct Caller {
    pub token: String,
    pub uid: String,
    pub exp: f64,
}

pub async fn authorize(app: &App, event: &Value) -> Result<Caller, &'static str> {
    let authorization = header(event, "authorization");
    let token = match authorization.get(..7) {
        Some(prefix) if prefix.eq_ignore_ascii_case("bearer ") => authorization[7..].trim(),
        _ => return Err("no bearer token"),
    };
    let claims = verify(token, app).await?;
    Ok(Caller {
        token: token.to_string(),
        uid: claims.get("uid").and_then(Value::as_str).unwrap_or("").to_string(),
        exp: number(&claims, "exp").unwrap_or(0.0),
    })
}

fn short_id(value: Option<&Value>, required: bool) -> Result<Option<String>, &'static str> {
    match value {
        None | Some(Value::Null) if !required => Ok(None),
        Some(Value::String(text))
            if !text.is_empty()
                && text.len() <= MAX_ID_CHARS
                && text.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_' || c == '.' || c == ':') =>
        {
            Ok(Some(text.clone()))
        }
        _ => Err("bad id"),
    }
}

/// `previousContactId`, when the body names one.
pub fn previous_contact(body: &Map<String, Value>) -> Result<Option<String>, &'static str> {
    short_id(body.get("previousContactId"), false)
}

// ---- the chat start ----------------------------------------------------------------------

pub fn agents_attribute(domain: &str) -> String {
    let mut chars = domain.chars();
    let capital: String = chars.next().map(|c| c.to_uppercase().chain(chars).collect()).unwrap_or_default();
    format!("hr{capital}Token")
}

/// The four token attributes the bridge blanks (HOP_ATTRIBUTES).
pub fn hop_attributes() -> Vec<String> {
    DOMAINS.iter().map(|d| agents_attribute(d)).chain([TOOLS_ATTRIBUTE.to_string()]).collect()
}

/// A JWT's `exp`, read without verification (the issuer signed it), or `now`.
pub fn expires_at(token: &str, now: f64) -> f64 {
    token
        .split('.')
        .nth(1)
        .and_then(unb64u)
        .and_then(|bytes| serde_json::from_slice::<Value>(&bytes).ok())
        .and_then(|claims| claims.get("exp").and_then(Value::as_f64))
        .unwrap_or(now)
}

/// The earlier of the hop tokens' expiry and the chat's duration less two minutes, in
/// epoch milliseconds.
pub fn expires_at_ms(hop_min_exp: f64, started_at_ms: i64) -> i64 {
    let chat_end = started_at_ms + i64::from(CHAT_DURATION_MINUTES) * 60_000 - CHAT_MARGIN_MS;
    ((hop_min_exp * 1000.0).floor() as i64).min(chat_end)
}

fn token_key(token: &str) -> [u8; 32] {
    Sha256::digest(token.as_bytes()).into()
}

/// The three agents tokens and the designer's tools token for `token`, from this instance's
/// cache or through AgentCore Identity's on-behalf-of exchange with the hr-bridge credential
/// provider (the bridge's `hop_tokens`). One workload access token serves the four
/// exchanges, which run at once. The bool says whether they came from the cache.
pub async fn exchange(app: &App, token: &str) -> Result<(HopTokens, bool), String> {
    let key = token_key(token);
    let now = app.now();
    if let Some(found) = app.hop_cache.lock().ok().and_then(|cache| cache.get(&key).cloned()) {
        if now < found.min_exp(now) - CACHE_MARGIN {
            return Ok((found, true));
        }
    }
    let (provider, workload) = (&app.config.provider, &app.config.workload);
    if provider.is_empty() || workload.is_empty() {
        return Err("OBO_PROVIDER or OBO_WORKLOAD is not set".into());
    }
    let workload_token = app.aws.workload_token(workload, token).await?;
    let agent_scopes: Vec<Vec<String>> = DOMAINS.iter().map(|d| vec![format!("hr.agents.{d}")]).collect();
    let agents = futures::future::join_all(agent_scopes.iter().map(|scopes| app.aws.hop_token(&workload_token, provider, scopes)));
    let canvas: Vec<String> = CANVAS_SCOPES.iter().map(|s| s.to_string()).collect();
    let (agents, tools) = tokio::join!(agents, app.aws.hop_token(&workload_token, provider, &canvas));
    let mut tokens = Vec::new();
    for (domain, result) in DOMAINS.iter().zip(agents) {
        tokens.push((domain.to_string(), result?));
    }
    let hop = HopTokens { agents: tokens, tools: tools? };
    if let Ok(mut cache) = app.hop_cache.lock() {
        cache.retain(|_, held| held.min_exp(now) - CACHE_MARGIN > now);
        while cache.len() >= MAX_CACHED {
            let Some(first) = cache.keys().next().copied() else { break };
            cache.remove(&first);
        }
        cache.insert(key, hop.clone());
    }
    Ok((hop, false))
}

/// A transcript item an `aws/chat` frame carries, or None for any other frame.
pub fn chat_item(frame: &str) -> Option<Map<String, Value>> {
    let message: Value = serde_json::from_str(frame).ok()?;
    if message.get("topic").and_then(Value::as_str) != Some("aws/chat") {
        return None;
    }
    let item = match message.get("content")? {
        Value::String(text) => serde_json::from_str::<Value>(text).ok()?,
        other => other.clone(),
    };
    match item {
        Value::Object(map) => Some(map),
        _ => None,
    }
}

pub const END_MARK: char = '\u{2063}';
pub const CLOSED_MARK: char = '\u{2064}';
const END_OF_TURN: &str = "[flow] end";
const CONVERSATION_CLOSED: &str = "[flow] closed";
const ESCALATION_PREFIX: &str = "[flow] Escalation";
const DESIGNER_ERROR_PREFIX: &str = "[flow] The Agentic CX block returned an error";
const FLOW_MESSAGE_PREFIX: &str = "[flow]";
const ENDED_CONTENT_TYPES: [&str; 2] = [
    "application/vnd.amazonaws.connect.event.chat.ended",
    "application/vnd.amazonaws.connect.event.participant.left",
];

/// A transcript item as the bridge's `classify` sees it: a reply ("text", "end", "closed",
/// "escalated", "error", "ended"), or None for the customer's own messages, hidden flow
/// lines and other events. Any reply ends the greeting wait, as in the bridge.
pub fn classify(item: &Map<String, Value>) -> Option<&'static str> {
    let text = |name: &str| item.get(name).and_then(Value::as_str).unwrap_or("");
    if text("Type") == "EVENT" && ENDED_CONTENT_TYPES.contains(&text("ContentType")) {
        return Some("ended");
    }
    if text("Type") != "MESSAGE" || text("ParticipantRole") == "CUSTOMER" {
        return None;
    }
    let content = text("Content");
    if content.trim() == END_OF_TURN {
        return Some("end");
    }
    if content.trim() == CONVERSATION_CLOSED {
        return Some("closed");
    }
    if content.starts_with(ESCALATION_PREFIX) {
        return Some("escalated");
    }
    if content.starts_with(DESIGNER_ERROR_PREFIX) {
        return Some("error");
    }
    if content.starts_with(FLOW_MESSAGE_PREFIX) {
        return None;
    }
    Some("text")
}

/// Transcript items not seen before, oldest first, from the newest 100.
async fn new_items(app: &App, connection_token: &str, seen: &mut HashSet<String>) -> Result<Vec<Map<String, Value>>, String> {
    let items = app.aws.transcript(connection_token).await?;
    let mut fresh = Vec::new();
    for item in items.into_iter().rev() {
        let Value::Object(item) = item else { continue };
        let id = item.get("Id").and_then(Value::as_str).unwrap_or("").to_string();
        if !id.is_empty() && !seen.insert(id) {
            continue;
        }
        fresh.push(item);
    }
    Ok(fresh)
}

/// Waits for the designer's greeting on the socket that started the flow, then closes the
/// socket (the bridge's `await_greeting`): the transcript is read whenever the socket is
/// quiet for GREETING_CHECK, and a socket that fails leaves the rest of the wait to polling.
/// No greeting within GREETING_LIMIT is a failed start.
pub async fn await_greeting(app: &App, timing: &Timing, mut socket: Box<dyn FlowSocket>, connection_token: &str, contact: &str) -> Result<(), String> {
    let start = timing.ms();
    let deadline = Instant::now() + GREETING_LIMIT;
    let mut seen = HashSet::new();
    // Ok(true): greeted; Ok(false): no greeting in time; Err: the socket or a read failed.
    let outcome: Result<bool, String> = async {
        loop {
            let left = deadline.saturating_duration_since(Instant::now());
            if left.is_zero() {
                return Ok(false);
            }
            let items = match socket.receive(left.min(GREETING_CHECK)).await? {
                Some(frame) => vec![chat_item(&frame).unwrap_or_default()],
                None => new_items(app, connection_token, &mut seen).await?,
            };
            for item in &items {
                if let Some(id) = item.get("Id").and_then(Value::as_str) {
                    seen.insert(id.to_string());
                }
                if classify(item).is_some() {
                    return Ok(true);
                }
            }
        }
    }
    .await;
    socket.close().await;
    let result = match outcome {
        Ok(true) => Ok(()),
        Ok(false) => Err("no greeting".to_string()),
        Err(reason) => {
            log(json!({"event": "greeting_socket_failed", "contact": contact, "reason": reason}));
            poll_greeting(app, connection_token, &mut seen, deadline).await
        }
    };
    timing.add("greeting wait", start, Some(timing.ms()), "connect");
    if matches!(&result, Err(reason) if reason == "no greeting") {
        problem("no_greeting", contact, "");
    }
    result
}

/// The bridge's `skip_greeting`: the transcript every POLL_INTERVAL until the deadline.
async fn poll_greeting(app: &App, connection_token: &str, seen: &mut HashSet<String>, deadline: Instant) -> Result<(), String> {
    while Instant::now() < deadline {
        if new_items(app, connection_token, seen).await?.iter().any(|item| classify(item).is_some()) {
            return Ok(());
        }
        tokio::time::sleep(POLL_INTERVAL).await;
    }
    Err("no greeting".to_string())
}

/// Blanks the four token attributes (the bridge's `clear_token`); false on failure, which
/// is logged as `token_not_cleared`.
pub async fn blank_tokens(app: &App, timing: &Timing, contact: &str) -> bool {
    let attributes: HashMap<String, String> = hop_attributes().into_iter().map(|name| (name, CLEARED.to_string())).collect();
    match timing.timed("token blanking", "connect", app.aws.update_attributes(&app.config.instance_id, contact, &attributes)).await {
        Ok(()) => true,
        Err(error) => {
            problem("token_not_cleared", contact, &error);
            false
        }
    }
}

/// Ends a contact (the bridge's `end_contact`). One that has already ended is no problem.
pub async fn end_contact(app: &App, timing: &Timing, contact: &str) -> &'static str {
    match timing.timed("StopContact", "connect", app.aws.stop_contact(&app.config.instance_id, contact)).await {
        Ok(()) => "ended",
        Err(code) if code == "ContactNotFoundException" => "already ended",
        Err(code) => {
            problem("contact_not_ended", contact, &code);
            "failed"
        }
    }
}

/// Ends the chat the page left, if it is the caller's: its `employeeId` must be the
/// caller's `uid`.
pub async fn end_previous(app: &App, timing: &Timing, previous: &str, uid: &str) -> &'static str {
    let found = timing.timed("GetContactAttributes", "connect", app.aws.contact_attributes(&app.config.instance_id, previous));
    match found.await {
        Ok(attributes) if attributes.get("employeeId").is_some_and(|id| id == uid) => end_contact(app, timing, previous).await,
        Ok(_) => "not the caller's",
        Err(AttributesError::NotFound) => "not found",
        Err(AttributesError::Failed(code)) => {
            problem("contact_not_ended", previous, &code);
            "failed"
        }
    }
}

/// One sub-agent's warm message, as the designer would address it (the bridge's
/// `warm_sub_agent`): on the runtime session `{contact}-{domain}` and the thread `contact`.
pub async fn warm_sub_agent(app: Arc<App>, timing: Timing, contact: String, domain: String, token: Option<String>) -> bool {
    let Some(token) = token else { return false };
    let body = json!({
        "jsonrpc": "2.0",
        "id": format!("warm-{domain}"),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": uuid::Uuid::new_v4().simple().to_string(),
                "contextId": contact,
                "parts": [{"kind": "text", "text": "warm"}],
                "metadata": {"warm": true},
            }
        },
    });
    let headers = vec![
        ("Authorization".to_string(), format!("Bearer {token}")),
        ("Content-Type".to_string(), "application/json".to_string()),
        ("X-Amzn-Bedrock-AgentCore-Runtime-Session-Id".to_string(), format!("{contact}-{domain}")),
    ];
    let url = format!("{}/{domain}/invocations", app.config.agents_gateway_url);
    let start = timing.ms();
    let warmed = match app.aws.post_json(&url, &headers, &body, SUB_AGENT_WARM_TIMEOUT).await {
        Ok(status) => status == 200,
        Err(reason) => {
            log(json!({"event": "warm_failed", "contact": contact, "domain": domain, "reason": reason}));
            false
        }
    };
    let name = if warmed { format!("warming {domain}") } else { format!("warming {domain} (failed)") };
    timing.add(&name, start, Some(timing.ms()), "agents");
    warmed
}

/// What one start did, for its run line.
#[derive(Default)]
struct StartRecord {
    outcome: &'static str,
    contact: Option<String>,
    cached: Option<bool>,
    started_at: Option<i64>,
    expires_at: Option<i64>,
    token_cleared: Option<bool>,
    line1_ms: Option<u64>,
    warmed: Option<usize>,
    error: Option<String>,
}

/// POST /chat/start after the token is verified: line 1 and line 2 to `lines`, then one run
/// line to the log. `previous` is the chat the page left.
pub async fn start(app: Arc<App>, caller: Caller, previous: Option<String>, timing: Timing, cold: bool, lines: &mut dyn Lines) {
    let restarted = previous.is_some();
    // Ending the left contact does not hold up the new one (L27).
    let ending = async {
        match &previous {
            Some(id) => Some(end_previous(&app, &timing, id, &caller.uid).await),
            None => None,
        }
    };
    let (previous_outcome, record) = tokio::join!(ending, start_contact(app.clone(), &caller, restarted, &timing, lines));
    log(json!({
        "event": "chat_start",
        "outcome": record.outcome,
        "contact": record.contact,
        "restarted": restarted,
        "previous": previous,
        "previous_outcome": previous_outcome,
        "cold": cold,
        "exchange_cached": record.cached,
        "token_cleared": record.token_cleared,
        "started_at": record.started_at,
        "expires_at": record.expires_at,
        "line1_ms": record.line1_ms,
        "warmed": record.warmed,
        "error": record.error,
        "total_ms": timing.ms(),
        "steps": timing.steps(),
    }));
}

async fn start_contact(app: Arc<App>, caller: &Caller, restarted: bool, timing: &Timing, lines: &mut dyn Lines) -> StartRecord {
    let mut record = StartRecord::default();
    // The designer reads its attributes once, when the flow reaches it (C2), so the
    // exchange comes first.
    let exchange_start = timing.ms();
    let hop = match exchange(&app, &caller.token).await {
        Ok((hop, cached)) => {
            timing.add("hop token exchanges", exchange_start, Some(timing.ms()), "exchange");
            timing.note(if cached { "issuer exchanges cached" } else { "issuer exchanges made by this request" });
            record.cached = Some(cached);
            hop
        }
        Err(error) => {
            // Fail closed: no contact starts with the Okta token in place of the hop tokens.
            timing.add("hop token exchanges (failed)", exchange_start, Some(timing.ms()), "exchange");
            problem("exchange_failed", "-", &error);
            lines.line(&json!({"error": "signin"})).await;
            record.outcome = "signin";
            record.error = Some(error);
            return record;
        }
    };
    let mut attributes: HashMap<String, String> =
        hop.agents.iter().map(|(domain, token)| (agents_attribute(domain), token.clone())).collect();
    attributes.insert(TOOLS_ATTRIBUTE.to_string(), hop.tools.clone());
    attributes.insert("employeeId".to_string(), caller.uid.clone());
    let request = StartChat {
        instance_id: app.config.instance_id.clone(),
        contact_flow_id: app.config.contact_flow_id.clone(),
        display_name: "Employee".to_string(),
        attributes,
        content_types: vec!["text/plain".to_string()],
        duration_minutes: CHAT_DURATION_MINUTES,
    };
    let started = match timing.timed("StartChatContact", "connect", app.aws.start_chat(&request)).await {
        Ok(started) => started,
        Err(error) => {
            lines.line(&json!({"error": "unavailable"})).await;
            record.outcome = "unavailable";
            record.error = Some(error);
            return record;
        }
    };
    let contact = started.contact_id.clone();
    record.contact = Some(contact.clone());
    let started_at = app.now_ms();
    record.started_at = Some(started_at);
    // The sub-agents need only the contact id, so they warm during the greeting (L13).
    let warming: Vec<tokio::task::JoinHandle<bool>> = if app.config.agents_gateway_url.is_empty() {
        Vec::new()
    } else {
        app.config
            .warm_domains
            .iter()
            .map(|domain| {
                let token = hop.agents_token(domain).map(String::from);
                tokio::spawn(warm_sub_agent(app.clone(), timing.clone(), contact.clone(), domain.clone(), token))
            })
            .collect()
    };
    let greeted: Result<(), String> = async {
        let connection =
            timing.timed("CreateParticipantConnection", "connect", app.aws.create_connection(&started.participant_token)).await?;
        let socket = timing.timed("flow socket", "connect", app.aws.open_flow(&connection.websocket_url)).await?;
        await_greeting(&app, timing, socket, &connection.connection_token, &contact).await
    }
    .await;
    if let Err(error) = greeted {
        // The designer may have read the tokens; the record no longer needs them, so they are
        // blanked before the contact ends (D42, D53).
        for handle in &warming {
            handle.abort();
        }
        record.token_cleared = Some(blank_tokens(&app, timing, &contact).await);
        end_contact(&app, timing, &contact).await;
        lines.line(&json!({"error": "unavailable"})).await;
        record.outcome = "unavailable";
        record.error = Some(error);
        return record;
    }
    let cleared = blank_tokens(&app, timing, &contact).await;
    record.token_cleared = Some(cleared);
    let expires_at = expires_at_ms(hop.min_exp(app.now()), started_at);
    record.expires_at = Some(expires_at);
    let line1_ms = timing.point("credentials sent", LANE);
    record.line1_ms = Some(line1_ms);
    lines
        .line(&json!({
            "data": {"startChatResult": {
                "ContactId": started.contact_id,
                "ParticipantId": started.participant_id,
                "ParticipantToken": started.participant_token,
            }},
            "region": REGION,
            "startedAt": started_at,
            "expiresAt": expires_at,
            "restarted": restarted,
            "timing": timing.value(Some(&contact)),
        }))
        .await;
    let count = warming.len();
    let warmed = match tokio::time::timeout(WARM_GUARD, futures::future::join_all(warming)).await {
        Ok(done) => done.into_iter().filter(|r| matches!(r, Ok(true))).count(),
        Err(_) => 0,
    };
    if warmed < count {
        timing.note("a sub-agent warm-up failed");
    }
    record.warmed = Some(warmed);
    record.outcome = "ok";
    lines.line(&json!({"warmed": warmed, "timing": timing.value(Some(&contact))})).await;
    record
}

// ---- the turn report ---------------------------------------------------------------------

/// A Connect AbsoluteTime (ISO 8601, for example 2026-10-04T12:00:00.123Z), or None.
fn absolute_time(value: Option<&Value>) -> Result<Option<String>, &'static str> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(text))
            if text.len() >= 20
                && text.len() <= 40
                && text.as_bytes()[4] == b'-'
                && text.as_bytes()[10] == b'T'
                && text.chars().all(|c| c.is_ascii_digit() || "-:.TZ+".contains(c)) =>
        {
            Ok(Some(text.clone()))
        }
        _ => Err("bad time"),
    }
}

fn one_of(value: Option<&Value>, allowed: &[&str]) -> Result<String, &'static str> {
    value.and_then(Value::as_str).filter(|v| allowed.contains(v)).map(String::from).ok_or("bad value")
}

/// The page's own steps, kept to the guppi.timing fields with names and lanes cut short.
fn page_timing(value: Option<&Value>) -> Value {
    let Some(Value::Object(timing)) = value else { return Value::Null };
    let text = |v: &Value, max: usize| v.as_str().map(|s| s.chars().take(max).collect::<String>());
    let steps: Vec<Value> = timing
        .get("steps")
        .and_then(Value::as_array)
        .map(|steps| {
            steps
                .iter()
                .take(40)
                .filter_map(|step| {
                    Some(json!({
                        "name": text(step.get("name")?, 80)?,
                        "start_ms": step.get("start_ms").and_then(Value::as_f64),
                        "end_ms": step.get("end_ms").and_then(Value::as_f64),
                        "lane": step.get("lane").and_then(|l| text(l, 24)),
                    }))
                })
                .collect()
        })
        .unwrap_or_default();
    json!({"steps": steps, "total_ms": timing.get("total_ms").and_then(Value::as_f64)})
}

/// The report's fields, checked; Err for a 400.
struct Report {
    contact: String,
    run: String,
    thread: Option<String>,
    sent_at: Option<String>,
    first_item_at: Option<String>,
    last_item_at: Option<String>,
    end_reason: String,
    error: Option<String>,
    transport: String,
    timing: Value,
}

fn parse_report(body: &Map<String, Value>) -> Result<Report, &'static str> {
    let error = match body.get("error") {
        None | Some(Value::Null) => None,
        Some(Value::String(text)) if text.len() <= 64 && text.chars().all(|c| c.is_ascii_alphanumeric() || "_-.:".contains(c)) => {
            Some(text.clone())
        }
        _ => return Err("bad error"),
    };
    Ok(Report {
        contact: short_id(body.get("contactId"), true)?.unwrap_or_default(),
        run: short_id(body.get("runId"), true)?.unwrap_or_default(),
        thread: short_id(body.get("threadId"), false)?,
        sent_at: absolute_time(body.get("sentAt"))?,
        first_item_at: absolute_time(body.get("firstItemAt"))?,
        last_item_at: absolute_time(body.get("lastItemAt"))?,
        end_reason: one_of(body.get("endReason"), &END_REASONS)?,
        error,
        transport: one_of(body.get("transport"), &TRANSPORTS)?,
        timing: page_timing(body.get("timing")),
    })
}

/// The alarm's kinds for a report: no reply, the designer's error, a failed socket.
pub fn report_problems(end_reason: &str, error: Option<&str>) -> Vec<&'static str> {
    let mut kinds = Vec::new();
    if end_reason == "no_reply" {
        kinds.push("no_reply");
    }
    if end_reason == "error" {
        kinds.push("designer_error");
    }
    if error.is_some_and(|e| e.to_ascii_lowercase().contains("socket")) {
        kinds.push("socket_failed");
    }
    kinds
}

/// POST /chat/report after the token is verified: the status and body to answer.
pub async fn report(app: &App, caller: &Caller, body: &Map<String, Value>, timing: &Timing) -> (u16, Option<Value>) {
    let received_at = app.now_ms();
    let report = match parse_report(body) {
        Ok(report) => report,
        Err(reason) => {
            log(json!({"event": "chat_report_refused", "status": 400, "reason": reason}));
            return (400, Some(json!({"error": "bad_request"})));
        }
    };
    let owner = timing
        .timed("GetContactAttributes", "connect", async {
            app.aws.contact_attributes(&app.config.instance_id, &report.contact).await
        })
        .await;
    match owner {
        Ok(attributes) if attributes.get("employeeId").is_some_and(|id| id == &caller.uid) => {}
        Ok(_) | Err(AttributesError::NotFound) => {
            log(json!({"event": "chat_report_refused", "status": 403, "contact": report.contact, "run": report.run}));
            return (403, Some(json!({"error": "forbidden"})));
        }
        Err(AttributesError::Failed(code)) => {
            log(json!({"event": "chat_report_refused", "status": 503, "contact": report.contact, "reason": code}));
            return (503, Some(json!({"error": "unavailable"})));
        }
    }
    // One run line per run id, while this instance lives.
    if let Ok(mut seen) = app.seen_runs.lock() {
        if seen.contains(&report.run) {
            return (204, None);
        }
        if seen.len() >= MAX_SEEN_RUNS {
            seen.pop_front();
        }
        seen.push_back(report.run.clone());
    }
    log(json!({
        "event": "chat_report",
        "contact": report.contact,
        "run": report.run,
        "thread": report.thread,
        "transport": report.transport,
        "end_reason": report.end_reason,
        "error": report.error,
        "sent_at": report.sent_at,
        "first_item_at": report.first_item_at,
        "last_item_at": report.last_item_at,
        "received_at": received_at,
        "timing": report.timing,
        "ms": timing.ms(),
    }));
    for kind in report_problems(&report.end_reason, report.error.as_deref()) {
        problem(kind, &report.contact, &report.run);
    }
    (204, None)
}

#[cfg(test)]
mod tests;
