//! hr-chat-start: token verification, routing, the two NDJSON lines, expiresAt, ownership,
//! greeting classification and the blanking order. AWS, Okta and the WebSocket are fakes;
//! Okta's key is generated here. Time is tokio's paused clock, so the 12 s greeting limit
//! takes no real time.

use std::cell::RefCell;
use std::collections::VecDeque;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Mutex as StdMutex, OnceLock};

use rsa::RsaPrivateKey;
use rsa::pkcs1v15::SigningKey;
use rsa::signature::{SignatureEncoding, Signer as _};
use rsa::traits::PublicKeyParts;

use super::*;

thread_local! {
    pub static LOGS: RefCell<Vec<Value>> = const { RefCell::new(Vec::new()) };
}

const OKTA: &str = "https://example.okta.com/oauth2/aus1";
const CHAT_APP: &str = "0oachat";
const HARNESS: &str = "0oaharness";
const UID: &str = "00u-employee";
const NOW: f64 = 1_800_000_000.0;
const CONTACT: &str = "11111111-2222-3333-4444-555555555555";
const GATEWAY: &str = "https://agents.example.com";

fn okta_private() -> &'static RsaPrivateKey {
    static KEY: OnceLock<RsaPrivateKey> = OnceLock::new();
    KEY.get_or_init(|| RsaPrivateKey::new(&mut rand::thread_rng(), 2048).expect("key"))
}

fn jwk_of(key: &RsaPrivateKey, kid: &str) -> Value {
    json!({"kty": "RSA", "kid": kid, "alg": "RS256", "n": b64u(&key.n().to_bytes_be()), "e": b64u(&key.e().to_bytes_be())})
}

fn signed(header: Value, claims: Value) -> String {
    let input = format!("{}.{}", b64u(header.to_string().as_bytes()), b64u(claims.to_string().as_bytes()));
    let signature = SigningKey::<Sha256>::new(okta_private().clone()).sign(input.as_bytes()).to_vec();
    format!("{input}.{}", b64u(&signature))
}

fn okta_token(overrides: Value) -> String {
    let mut claims = json!({"iss": OKTA, "aud": "api://guppi", "cid": CHAT_APP, "uid": UID, "sub": "person@example.com",
                            "iat": NOW - 10.0, "exp": NOW + 3000.0});
    for (key, value) in overrides.as_object().unwrap() {
        claims[key] = value.clone();
    }
    signed(json!({"alg": "RS256", "kid": "okta-kid"}), claims)
}

/// A hop token as the issuer would mint it, unsigned: only its `exp` is read here.
fn hop(scope: &str, exp: f64) -> String {
    format!("{}.{}.sig", b64u(b"{\"alg\":\"RS256\"}"), b64u(json!({"scope": scope, "exp": exp, "sub": UID}).to_string().as_bytes()))
}

#[derive(Default)]
struct FakeOkta {
    calls: AtomicUsize,
}

#[async_trait]
impl Fetcher for FakeOkta {
    async fn fetch_json(&self, _url: &str) -> Result<Value, String> {
        self.calls.fetch_add(1, Ordering::SeqCst);
        Ok(json!({"keys": [jwk_of(okta_private(), "okta-kid")]}))
    }
}

/// What the flow socket does on each receive.
#[derive(Clone)]
enum Frame {
    Text(String),
    Quiet,
    Fail,
}

fn greeting_frame(content: &str) -> Frame {
    let item = json!({"Id": "greet-1", "Type": "MESSAGE", "ParticipantRole": "SYSTEM", "Content": content,
                      "AbsoluteTime": "2026-10-04T12:00:01.000Z"});
    Frame::Text(json!({"topic": "aws/chat", "content": item.to_string()}).to_string())
}

/// Every call in order, so the tests can check what came before what.
type Events = Arc<StdMutex<Vec<String>>>;

struct FakeSocket {
    frames: VecDeque<Frame>,
    events: Events,
}

#[async_trait]
impl FlowSocket for FakeSocket {
    async fn receive(&mut self, wait: Duration) -> Result<Option<String>, String> {
        match self.frames.pop_front().unwrap_or(Frame::Quiet) {
            Frame::Text(text) => Ok(Some(text)),
            Frame::Quiet => {
                tokio::time::sleep(wait).await;
                Ok(None)
            }
            Frame::Fail => Err("io".into()),
        }
    }

    async fn close(&mut self) {
        self.events.lock().unwrap().push("socket closed".into());
    }
}

struct FakeAws {
    events: Events,
    hop_exp: StdMutex<f64>,
    exchange_fails: AtomicBool,
    start_fails: AtomicBool,
    blank_fails: AtomicBool,
    frames: StdMutex<Vec<Frame>>,
    /// Transcript reads in turn; the last one repeats.
    transcripts: StdMutex<VecDeque<Vec<Value>>>,
    owners: StdMutex<HashMap<String, String>>,
    started: StdMutex<Vec<StartChat>>,
    scopes: StdMutex<Vec<Vec<String>>>,
    workloads: StdMutex<Vec<(String, String)>>,
    blanked: StdMutex<Vec<HashMap<String, String>>>,
    stopped: StdMutex<Vec<String>>,
    posts: StdMutex<Vec<(String, Vec<(String, String)>, Value)>>,
    exchanges: AtomicUsize,
}

impl FakeAws {
    fn new(events: Events) -> Self {
        FakeAws {
            events,
            hop_exp: StdMutex::new(NOW + 3000.0),
            exchange_fails: AtomicBool::new(false),
            start_fails: AtomicBool::new(false),
            blank_fails: AtomicBool::new(false),
            frames: StdMutex::new(vec![greeting_frame("Hi, I'm the HR assistant.\u{2063}")]),
            transcripts: StdMutex::new(VecDeque::from([Vec::new()])),
            owners: StdMutex::new(HashMap::new()),
            started: StdMutex::default(),
            scopes: StdMutex::default(),
            workloads: StdMutex::default(),
            blanked: StdMutex::default(),
            stopped: StdMutex::default(),
            posts: StdMutex::default(),
            exchanges: AtomicUsize::new(0),
        }
    }

    fn event(&self, text: &str) {
        self.events.lock().unwrap().push(text.to_string());
    }
}

#[async_trait]
impl Aws for FakeAws {
    async fn workload_token(&self, workload: &str, user_token: &str) -> Result<String, String> {
        self.event("workload token");
        self.workloads.lock().unwrap().push((workload.into(), user_token.into()));
        Ok("workload-token".into())
    }

    async fn hop_token(&self, workload_token: &str, provider: &str, scopes: &[String]) -> Result<String, String> {
        assert_eq!((workload_token, provider), ("workload-token", "guppi-obo-hr-bridge"));
        self.exchanges.fetch_add(1, Ordering::SeqCst);
        self.event("exchange");
        if self.exchange_fails.load(Ordering::SeqCst) {
            return Err("AccessDeniedException".into());
        }
        self.scopes.lock().unwrap().push(scopes.to_vec());
        Ok(hop(&scopes.join(" "), *self.hop_exp.lock().unwrap()))
    }

    async fn start_chat(&self, request: &StartChat) -> Result<Started, String> {
        self.event("StartChatContact");
        if self.start_fails.load(Ordering::SeqCst) {
            return Err("LimitExceededException".into());
        }
        self.started.lock().unwrap().push(request.clone());
        Ok(Started { contact_id: CONTACT.into(), participant_id: "participant-1".into(), participant_token: "participant-token".into() })
    }

    async fn create_connection(&self, participant_token: &str) -> Result<Connection, String> {
        assert_eq!(participant_token, "participant-token");
        self.event("CreateParticipantConnection");
        Ok(Connection { websocket_url: "wss://example/ws".into(), connection_token: "connection-token".into() })
    }

    async fn open_flow(&self, _url: &str) -> Result<Box<dyn FlowSocket>, String> {
        self.event("flow socket");
        let frames = self.frames.lock().unwrap().clone().into();
        Ok(Box::new(FakeSocket { frames, events: self.events.clone() }))
    }

    async fn transcript(&self, connection_token: &str) -> Result<Vec<Value>, String> {
        assert_eq!(connection_token, "connection-token");
        self.event("GetTranscript");
        let mut reads = self.transcripts.lock().unwrap();
        Ok(if reads.len() > 1 { reads.pop_front().unwrap() } else { reads.front().cloned().unwrap_or_default() })
    }

    async fn update_attributes(&self, instance_id: &str, contact_id: &str, attributes: &HashMap<String, String>) -> Result<(), String> {
        assert_eq!((instance_id, contact_id), ("instance-1", CONTACT));
        self.event("UpdateContactAttributes");
        if self.blank_fails.load(Ordering::SeqCst) {
            return Err("ThrottlingException".into());
        }
        self.blanked.lock().unwrap().push(attributes.clone());
        Ok(())
    }

    async fn stop_contact(&self, _instance_id: &str, contact_id: &str) -> Result<(), String> {
        self.event(&format!("StopContact {contact_id}"));
        self.stopped.lock().unwrap().push(contact_id.into());
        Ok(())
    }

    async fn contact_attributes(&self, _instance_id: &str, contact_id: &str) -> Result<HashMap<String, String>, AttributesError> {
        self.event(&format!("GetContactAttributes {contact_id}"));
        match self.owners.lock().unwrap().get(contact_id) {
            Some(owner) => Ok(HashMap::from([("employeeId".to_string(), owner.clone()), ("hrToolsToken".to_string(), CLEARED.into())])),
            None => Err(AttributesError::NotFound),
        }
    }

    async fn post_json(&self, url: &str, headers: &[(String, String)], body: &Value, _timeout: Duration) -> Result<u16, String> {
        self.event("warm-up");
        self.posts.lock().unwrap().push((url.into(), headers.to_vec(), body.clone()));
        tokio::time::sleep(Duration::from_millis(1500)).await;
        Ok(200)
    }
}

struct Collected {
    lines: Vec<Value>,
    events: Events,
}

#[async_trait]
impl Lines for Collected {
    async fn line(&mut self, value: &Value) {
        self.events.lock().unwrap().push(format!("line {}", self.lines.len() + 1));
        self.lines.push(value.clone());
    }
}

struct Env {
    app: Arc<App>,
    aws: Arc<FakeAws>,
    okta: Arc<FakeOkta>,
    events: Events,
}

fn env() -> Env {
    LOGS.with(|logs| logs.borrow_mut().clear());
    let events: Events = Arc::default();
    let aws = Arc::new(FakeAws::new(events.clone()));
    let okta = Arc::new(FakeOkta::default());
    let config = Config {
        okta_issuer: OKTA.into(),
        okta_audience: "api://guppi".into(),
        okta_clients: [CHAT_APP, HARNESS].iter().map(|s| s.to_string()).collect(),
        instance_id: "instance-1".into(),
        contact_flow_id: "flow-1".into(),
        agents_gateway_url: GATEWAY.into(),
        warm_domains: DOMAINS.iter().map(|d| d.to_string()).collect(),
        provider: "guppi-obo-hr-bridge".into(),
        workload: "hr-chat-start".into(),
    };
    let app = App::new(config, aws.clone(), okta.clone(), OktaKeys::default(), Arc::new(|| NOW));
    Env { app: Arc::new(app), aws, okta, events }
}

fn event(path: &str, token: Option<&str>, body: &str) -> Value {
    let mut headers = json!({"content-type": "application/json"});
    if let Some(token) = token {
        headers["authorization"] = json!(format!("Bearer {token}"));
    }
    json!({"rawPath": path, "requestContext": {"http": {"method": "POST"}}, "headers": headers, "body": body, "isBase64Encoded": false})
}

fn caller(_env: &Env) -> Caller {
    Caller { token: okta_token(json!({})), uid: UID.into(), exp: NOW + 3000.0 }
}

async fn run_start(env: &Env, previous: Option<&str>) -> Vec<Value> {
    let mut sink = Collected { lines: Vec::new(), events: env.events.clone() };
    start(env.app.clone(), caller(env), previous.map(String::from), Timing::new(Instant::now()), false, &mut sink).await;
    sink.lines
}

fn logs() -> Vec<Value> {
    LOGS.with(|logs| logs.borrow().clone())
}

fn problems() -> Vec<String> {
    logs().iter().filter(|l| l["event"] == "chat_problem").map(|l| l["kind"].as_str().unwrap().to_string()).collect()
}

fn events(env: &Env) -> Vec<String> {
    env.events.lock().unwrap().clone()
}

fn position(events: &[String], name: &str) -> usize {
    events.iter().position(|e| e == name).unwrap_or_else(|| panic!("{name} not in {events:?}"))
}

// ---- token verification -----------------------------------------------------------------

#[tokio::test]
async fn a_chat_token_is_accepted_and_names_the_caller() {
    let env = env();
    let found = authorize(&env.app, &event("/api/hr/chat/start", Some(&okta_token(json!({}))), "")).await.unwrap();
    assert_eq!(found.uid, UID);
    assert_eq!(found.exp, NOW + 3000.0);
}

#[tokio::test]
async fn the_harness_client_is_accepted() {
    let env = env();
    assert!(verify(&okta_token(json!({"cid": HARNESS})), &env.app).await.is_ok());
}

#[tokio::test]
async fn tokens_are_refused_for_each_failed_check() {
    let env = env();
    let cases = [
        (json!({"iss": "https://elsewhere.okta.com"}), "untrusted issuer"),
        (json!({"aud": "api://other"}), "okta audience"),
        (json!({"cid": "0oaother"}), "okta client"),
        (json!({"uid": ""}), "okta token without uid"),
        (json!({"exp": NOW - 120.0}), "expired"),
        (json!({"exp": NOW + 30.0}), "expires too soon"),
        (json!({"iat": NOW + 600.0}), "not yet valid"),
    ];
    for (overrides, reason) in cases {
        assert_eq!(verify(&okta_token(overrides.clone()), &env.app).await.unwrap_err(), reason, "{overrides}");
    }
    let token = okta_token(json!({}));
    let at = token.len() - 20;
    let swapped = if &token[at..at + 1] == "A" { "B" } else { "A" };
    let tampered = format!("{}{swapped}{}", &token[..at], &token[at + 1..]);
    assert!(verify(&tampered, &env.app).await.is_err());
    let unsigned = format!("{}.{}.", b64u(b"{\"alg\":\"none\"}"), token.split('.').nth(1).unwrap());
    assert_eq!(verify(&unsigned, &env.app).await.unwrap_err(), "unsupported token header");
    assert_eq!(verify("not-a-token", &env.app).await.unwrap_err(), "malformed token");
}

#[tokio::test]
async fn an_unknown_key_is_fetched_at_most_once_a_minute() {
    let env = env();
    let other = signed(json!({"alg": "RS256", "kid": "rotated"}), json!({"iss": OKTA, "exp": NOW + 3000.0, "iat": NOW}));
    assert_eq!(verify(&other, &env.app).await.unwrap_err(), "bad signature");
    assert_eq!(verify(&other, &env.app).await.unwrap_err(), "bad signature");
    assert_eq!(env.okta.calls.load(Ordering::SeqCst), 1);
}

#[tokio::test]
async fn the_built_in_keys_are_okta_rsa_keys() {
    let keys = built_in_okta_keys(NOW);
    assert!(!keys.keys.is_empty());
    assert!(keys.keys.values().all(|k| k["kty"] == "RSA" && k.get("n").is_some()));
}

#[tokio::test]
async fn a_request_without_a_bearer_is_refused() {
    let env = env();
    assert_eq!(authorize(&env.app, &event("/api/hr/chat/start", None, "")).await.err(), Some("no bearer token"));
}

// ---- routing and bodies ------------------------------------------------------------------

#[test]
fn routes_go_by_the_path_suffix_and_post_only() {
    assert_eq!(route(&event("/api/hr/chat/start", None, "")), Route::Start);
    assert_eq!(route(&event("/api/hr/chat/report", None, "")), Route::Report);
    assert_eq!(route(&event("/chat/start", None, "")), Route::Start);
    assert_eq!(route(&event("/api/hr/chat/other", None, "")), Route::NotFound);
    assert_eq!(route(&event("/api/hr/invocations", None, "")), Route::NotFound);
    let mut get = event("/api/hr/chat/start", None, "");
    get["requestContext"]["http"]["method"] = json!("GET");
    assert_eq!(route(&get), Route::NotAllowed);
}

#[test]
fn bodies_are_json_objects_plain_or_base64() {
    assert_eq!(request_body(&event("/x", None, "")).unwrap(), Map::new());
    let body = request_body(&event("/x", None, "{\"previousContactId\":\"abc-1\"}")).unwrap();
    assert_eq!(previous_contact(&body).unwrap().as_deref(), Some("abc-1"));
    let mut encoded = event("/x", None, &STANDARD.encode("{\"previousContactId\":\"abc-2\"}"));
    encoded["isBase64Encoded"] = json!(true);
    assert_eq!(previous_contact(&request_body(&encoded).unwrap()).unwrap().as_deref(), Some("abc-2"));
    assert!(request_body(&event("/x", None, "[1]")).is_err());
    assert!(request_body(&event("/x", None, &"x".repeat(MAX_BODY_BYTES + 1))).is_err());
    let odd = request_body(&event("/x", None, "{\"previousContactId\":\"a b\"}")).unwrap();
    assert!(previous_contact(&odd).is_err());
}

// ---- the start ---------------------------------------------------------------------------

#[tokio::test(start_paused = true)]
async fn a_start_streams_the_credentials_then_the_warm_up_count() {
    let env = env();
    let lines = run_start(&env, None).await;
    assert_eq!(lines.len(), 2);
    let first = &lines[0];
    assert_eq!(
        first["data"]["startChatResult"],
        json!({"ContactId": CONTACT, "ParticipantId": "participant-1", "ParticipantToken": "participant-token"})
    );
    assert_eq!(first["region"], "us-east-1");
    assert_eq!(first["restarted"], false);
    assert_eq!(first["startedAt"], json!((NOW * 1000.0) as i64));
    let steps = first["timing"]["steps"].as_array().unwrap();
    for step in steps {
        assert!(step["name"].is_string() && step["start_ms"].is_u64() && step["lane"].is_string(), "{step}");
    }
    let names: Vec<&str> = steps.iter().map(|s| s["name"].as_str().unwrap()).collect();
    for name in ["hop token exchanges", "StartChatContact", "CreateParticipantConnection", "flow socket", "greeting wait", "token blanking"] {
        assert!(names.contains(&name), "{name} in {names:?}");
    }
    assert_eq!(lines[1]["warmed"], 3);
    assert!(lines[1]["timing"]["steps"].as_array().unwrap().iter().any(|s| s["name"] == "warming pay"));
    let run = logs().into_iter().find(|l| l["event"] == "chat_start").unwrap();
    assert_eq!((run["outcome"].as_str(), run["contact"].as_str(), run["warmed"].as_u64()), (Some("ok"), Some(CONTACT), Some(3)));
    assert!(problems().is_empty());
}

#[tokio::test(start_paused = true)]
async fn the_contact_carries_the_hop_tokens_and_the_employee_id_for_an_hour() {
    let env = env();
    run_start(&env, None).await;
    let started = env.aws.started.lock().unwrap()[0].clone();
    assert_eq!((started.instance_id.as_str(), started.contact_flow_id.as_str()), ("instance-1", "flow-1"));
    assert_eq!(started.display_name, "Employee");
    assert_eq!(started.content_types, vec!["text/plain"]);
    assert_eq!(started.duration_minutes, 60);
    let mut names: Vec<&str> = started.attributes.keys().map(String::as_str).collect();
    names.sort();
    assert_eq!(names, ["employeeId", "hrPayToken", "hrProfileToken", "hrToolsToken", "hrTravelToken"]);
    assert_eq!(started.attributes["employeeId"], UID);
    assert!(started.attributes["hrPayToken"].starts_with(&hop("hr.agents.pay", NOW + 3000.0)[..20]));
    let okta = okta_token(json!({}));
    assert!(started.attributes.values().all(|v| v != &okta), "the Okta token never reaches the contact");
    // The bridge's scopes, through the hr-bridge provider, as the function's own workload.
    let mut scopes = env.aws.scopes.lock().unwrap().clone();
    scopes.sort();
    assert_eq!(
        scopes,
        vec![
            vec!["hr.agents.pay".to_string()],
            vec!["hr.agents.profile".to_string()],
            vec!["hr.agents.travel".to_string()],
            CANVAS_SCOPES.iter().map(|s| s.to_string()).collect(),
        ]
    );
    assert_eq!(env.aws.workloads.lock().unwrap()[0], ("hr-chat-start".to_string(), okta));
}

#[tokio::test(start_paused = true)]
async fn line_one_comes_after_the_greeting_and_the_blanking() {
    let env = env();
    run_start(&env, None).await;
    let order = events(&env);
    let greeted = position(&order, "socket closed");
    let blanked = position(&order, "UpdateContactAttributes");
    let line = position(&order, "line 1");
    assert!(position(&order, "StartChatContact") < position(&order, "flow socket"));
    assert!(greeted < blanked && blanked < line, "{order:?}");
    assert!(position(&order, "line 2") > line);
    let blanked = env.aws.blanked.lock().unwrap()[0].clone();
    let mut names: Vec<&String> = blanked.keys().collect();
    names.sort();
    assert_eq!(names, ["hrPayToken", "hrProfileToken", "hrToolsToken", "hrTravelToken"]);
    assert!(blanked.values().all(|v| v == CLEARED));
}

#[tokio::test(start_paused = true)]
async fn the_warm_ups_go_out_beside_the_greeting_wait_as_the_bridge_sends_them() {
    let env = env();
    // The greeting arrives after a quiet second, so the warm-ups start before it.
    *env.aws.frames.lock().unwrap() = vec![Frame::Quiet, greeting_frame("Hello\u{2063}")];
    run_start(&env, None).await;
    let order = events(&env);
    assert!(position(&order, "warm-up") < position(&order, "socket closed"), "{order:?}");
    let posts = env.aws.posts.lock().unwrap().clone();
    assert_eq!(posts.len(), 3);
    let (url, headers, body) = posts.iter().find(|(url, ..)| url.contains("/travel/")).unwrap();
    assert_eq!(url, &format!("{GATEWAY}/travel/invocations"));
    let header = |name: &str| headers.iter().find(|(n, _)| n == name).map(|(_, v)| v.clone()).unwrap();
    assert_eq!(header("X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"), format!("{CONTACT}-travel"));
    assert_eq!(header("Content-Type"), "application/json");
    assert_eq!(header("Authorization"), format!("Bearer {}", hop("hr.agents.travel", NOW + 3000.0)));
    assert_eq!(body["method"], "message/send");
    assert_eq!(body["id"], "warm-travel");
    assert_eq!(body["params"]["message"]["contextId"], CONTACT);
    assert_eq!(body["params"]["message"]["metadata"], json!({"warm": true}));
    assert_eq!(body["params"]["message"]["parts"], json!([{"kind": "text", "text": "warm"}]));
}

#[tokio::test(start_paused = true)]
async fn expires_at_is_the_hop_tokens_expiry_when_it_comes_first() {
    let env = env();
    *env.aws.hop_exp.lock().unwrap() = NOW + 1200.0;
    let lines = run_start(&env, None).await;
    assert_eq!(lines[0]["expiresAt"], json!(((NOW + 1200.0) * 1000.0) as i64));
}

#[test]
fn expires_at_is_otherwise_the_chat_duration_less_two_minutes() {
    let started = (NOW * 1000.0) as i64;
    assert_eq!(expires_at_ms(NOW + 3600.0, started), started + 58 * 60 * 1000);
    assert_eq!(expires_at_ms(NOW + 600.0, started), started + 600 * 1000);
}

#[tokio::test(start_paused = true)]
async fn a_failed_exchange_answers_signin_and_starts_nothing() {
    let env = env();
    env.aws.exchange_fails.store(true, Ordering::SeqCst);
    let lines = run_start(&env, None).await;
    assert_eq!(lines, vec![json!({"error": "signin"})]);
    assert!(env.aws.started.lock().unwrap().is_empty());
    assert_eq!(problems(), ["exchange_failed"]);
}

#[tokio::test(start_paused = true)]
async fn a_failed_start_chat_answers_unavailable() {
    let env = env();
    env.aws.start_fails.store(true, Ordering::SeqCst);
    let lines = run_start(&env, None).await;
    assert_eq!(lines, vec![json!({"error": "unavailable"})]);
    assert!(env.aws.stopped.lock().unwrap().is_empty());
}

#[tokio::test(start_paused = true)]
async fn no_greeting_blanks_the_tokens_then_ends_the_contact() {
    let env = env();
    *env.aws.frames.lock().unwrap() = Vec::new();
    let begun = Instant::now();
    let lines = run_start(&env, None).await;
    assert!(begun.elapsed() >= GREETING_LIMIT);
    assert_eq!(lines, vec![json!({"error": "unavailable"})]);
    let order = events(&env);
    assert!(position(&order, "UpdateContactAttributes") < position(&order, &format!("StopContact {CONTACT}")), "{order:?}");
    assert!(position(&order, &format!("StopContact {CONTACT}")) < position(&order, "line 1"));
    assert_eq!(problems(), ["no_greeting"]);
    assert_eq!(logs().into_iter().find(|l| l["event"] == "chat_start").unwrap()["outcome"], "unavailable");
}

#[tokio::test(start_paused = true)]
async fn a_quiet_socket_reads_the_transcript_for_the_greeting() {
    let env = env();
    *env.aws.frames.lock().unwrap() = Vec::new();
    let greeting = json!({"Id": "g", "Type": "MESSAGE", "ParticipantRole": "SYSTEM", "Content": "Hi\u{2063}"});
    let joined = json!({"Id": "j", "Type": "EVENT", "ContentType": "application/vnd.amazonaws.connect.event.participant.joined"});
    *env.aws.transcripts.lock().unwrap() = VecDeque::from([vec![joined.clone()], vec![greeting, joined]]);
    let lines = run_start(&env, None).await;
    assert!(lines[0].get("data").is_some(), "{lines:?}");
    assert_eq!(events(&env).iter().filter(|e| *e == "GetTranscript").count(), 2);
}

#[tokio::test(start_paused = true)]
async fn a_failed_socket_leaves_the_greeting_to_polling() {
    let env = env();
    *env.aws.frames.lock().unwrap() = vec![Frame::Fail];
    let greeting = json!({"Id": "g", "Type": "MESSAGE", "ParticipantRole": "SYSTEM", "Content": "Hi\u{2063}"});
    *env.aws.transcripts.lock().unwrap() = VecDeque::from([Vec::new(), vec![greeting]]);
    let lines = run_start(&env, None).await;
    assert!(lines[0].get("data").is_some(), "{lines:?}");
    assert!(logs().iter().any(|l| l["event"] == "greeting_socket_failed"));
    assert!(problems().is_empty());
}

#[tokio::test(start_paused = true)]
async fn a_failed_blanking_is_a_problem_but_the_chat_goes_on() {
    let env = env();
    env.aws.blank_fails.store(true, Ordering::SeqCst);
    let lines = run_start(&env, None).await;
    assert!(lines[0].get("data").is_some());
    assert_eq!(problems(), ["token_not_cleared"]);
}

#[tokio::test(start_paused = true)]
async fn the_previous_contact_is_ended_only_when_it_is_the_callers() {
    let env = env();
    env.aws.owners.lock().unwrap().insert("old-mine".into(), UID.into());
    env.aws.owners.lock().unwrap().insert("old-theirs".into(), "00u-someone-else".into());
    let lines = run_start(&env, Some("old-mine")).await;
    assert_eq!(lines[0]["restarted"], true);
    assert_eq!(env.aws.stopped.lock().unwrap().clone(), ["old-mine"]);
    run_start(&env, Some("old-theirs")).await;
    run_start(&env, Some("old-unknown")).await;
    assert_eq!(env.aws.stopped.lock().unwrap().clone(), ["old-mine"]);
    let outcomes: Vec<Value> = logs().into_iter().filter(|l| l["event"] == "chat_start").map(|l| l["previous_outcome"].clone()).collect();
    assert_eq!(outcomes, [json!("ended"), json!("not the caller's"), json!("not found")]);
}

#[tokio::test(start_paused = true)]
async fn a_second_start_on_the_same_sign_in_reuses_the_hop_tokens() {
    let env = env();
    run_start(&env, None).await;
    run_start(&env, None).await;
    assert_eq!(env.aws.exchanges.load(Ordering::SeqCst), 4);
    let cached: Vec<Value> = logs().into_iter().filter(|l| l["event"] == "chat_start").map(|l| l["exchange_cached"].clone()).collect();
    assert_eq!(cached, [json!(false), json!(true)]);
}

#[tokio::test(start_paused = true)]
async fn no_log_line_holds_a_token() {
    let env = env();
    run_start(&env, None).await;
    let okta = okta_token(json!({}));
    let logged = serde_json::to_string(&logs()).unwrap();
    assert!(!logged.contains(&okta[..40]));
    assert!(!logged.contains("participant-token"));
    for scope in ["hr.agents.pay", "hr.agents.profile", "hr.agents.travel"] {
        assert!(!logged.contains(&hop(scope, NOW + 3000.0)[..60]));
    }
}

// ---- greeting classification -------------------------------------------------------------

fn item(value: Value) -> Map<String, Value> {
    value.as_object().unwrap().clone()
}

#[test]
fn the_greeting_is_the_first_designer_message_that_is_not_a_flow_line() {
    let message = |role: &str, content: &str| item(json!({"Type": "MESSAGE", "ParticipantRole": role, "Content": content}));
    assert_eq!(classify(&message("SYSTEM", "Hi, how can I help?\u{2063}")), Some("text"));
    assert_eq!(classify(&message("BOT", "Hi")), Some("text"));
    assert_eq!(classify(&message("CUSTOMER", "hello")), None);
    assert_eq!(classify(&message("SYSTEM", "[flow] starting")), None);
    assert_eq!(classify(&message("SYSTEM", "[flow] end")), Some("end"));
    assert_eq!(classify(&message("SYSTEM", "[flow] The Agentic CX block returned an error")), Some("error"));
    let event = |content_type: &str| item(json!({"Type": "EVENT", "ContentType": content_type}));
    assert_eq!(classify(&event("application/vnd.amazonaws.connect.event.participant.joined")), None);
    assert_eq!(classify(&event("application/vnd.amazonaws.connect.event.chat.ended")), Some("ended"));
}

#[test]
fn chat_frames_carry_items_and_other_topics_do_not() {
    let frame = json!({"topic": "aws/chat", "content": "{\"Id\":\"a\",\"Type\":\"MESSAGE\"}"}).to_string();
    assert_eq!(chat_item(&frame).unwrap()["Id"], "a");
    assert!(chat_item(&json!({"topic": "aws/subscribe", "content": {"status": 200}}).to_string()).is_none());
    assert!(chat_item("not json").is_none());
}

#[test]
fn the_blanked_attributes_are_the_four_token_attributes() {
    assert_eq!(hop_attributes(), ["hrProfileToken", "hrPayToken", "hrTravelToken", "hrToolsToken"]);
}

// ---- the report --------------------------------------------------------------------------

fn report_body(overrides: Value) -> Map<String, Value> {
    let mut body = json!({"contactId": CONTACT, "runId": "run-1", "threadId": "thread-1",
                          "sentAt": "2026-10-04T12:00:00.100Z", "firstItemAt": "2026-10-04T12:00:01.200Z",
                          "lastItemAt": "2026-10-04T12:00:02.300Z", "endReason": "end_mark", "transport": "connect",
                          "timing": {"steps": [{"name": "send", "start_ms": 0, "end_ms": 90, "lane": "page"}], "total_ms": 2300}});
    for (key, value) in overrides.as_object().unwrap() {
        body[key] = value.clone();
    }
    body.as_object().unwrap().clone()
}

async fn send_report(env: &Env, overrides: Value) -> (u16, Option<Value>) {
    report(&env.app, &caller(env), &report_body(overrides), &Timing::new(Instant::now())).await
}

#[tokio::test]
async fn a_report_on_the_callers_contact_is_one_run_line() {
    let env = env();
    env.aws.owners.lock().unwrap().insert(CONTACT.into(), UID.into());
    assert_eq!(send_report(&env, json!({})).await, (204, None));
    let line = logs().into_iter().find(|l| l["event"] == "chat_report").unwrap();
    assert_eq!(line["contact"], CONTACT);
    assert_eq!(line["run"], "run-1");
    assert_eq!(line["end_reason"], "end_mark");
    assert_eq!(line["transport"], "connect");
    assert_eq!(line["sent_at"], "2026-10-04T12:00:00.100Z");
    assert_eq!(line["last_item_at"], "2026-10-04T12:00:02.300Z");
    assert_eq!(line["received_at"], json!((NOW * 1000.0) as i64));
    assert_eq!(line["timing"]["steps"][0]["name"], "send");
    assert!(problems().is_empty());
    // The same run again writes nothing more.
    assert_eq!(send_report(&env, json!({})).await, (204, None));
    assert_eq!(logs().iter().filter(|l| l["event"] == "chat_report").count(), 1);
}

#[tokio::test]
async fn reports_raise_problems_for_no_reply_designer_errors_and_sockets() {
    let env = env();
    env.aws.owners.lock().unwrap().insert(CONTACT.into(), UID.into());
    send_report(&env, json!({"runId": "a", "endReason": "no_reply"})).await;
    send_report(&env, json!({"runId": "b", "endReason": "error", "error": "designer"})).await;
    send_report(&env, json!({"runId": "c", "endReason": "quiet", "error": "socket_failed", "transport": "bridge"})).await;
    send_report(&env, json!({"runId": "d", "endReason": "closed"})).await;
    assert_eq!(problems(), ["no_reply", "designer_error", "socket_failed"]);
}

#[tokio::test]
async fn a_report_on_someone_elses_contact_is_forbidden() {
    let env = env();
    env.aws.owners.lock().unwrap().insert(CONTACT.into(), "00u-someone-else".into());
    assert_eq!(send_report(&env, json!({})).await.0, 403);
    assert_eq!(send_report(&env, json!({"contactId": "unknown-contact"})).await.0, 403);
    assert!(!logs().iter().any(|l| l["event"] == "chat_report"));
}

#[tokio::test]
async fn a_malformed_report_is_refused() {
    let env = env();
    env.aws.owners.lock().unwrap().insert(CONTACT.into(), UID.into());
    for overrides in [
        json!({"endReason": "finished"}),
        json!({"transport": "carrier pigeon"}),
        json!({"contactId": null}),
        json!({"runId": ""}),
        json!({"sentAt": "yesterday"}),
        json!({"error": "a message with spaces"}),
    ] {
        assert_eq!(send_report(&env, overrides.clone()).await.0, 400, "{overrides}");
    }
    assert!(!events(&env).iter().any(|e| e.starts_with("GetContactAttributes")));
}

#[test]
fn every_end_reason_and_transport_in_the_contract_is_accepted() {
    for reason in ["end_mark", "closed", "ended", "quiet", "no_reply", "error", "aborted"] {
        assert!(END_REASONS.contains(&reason));
    }
    assert_eq!(TRANSPORTS, ["connect", "bridge"]);
}
