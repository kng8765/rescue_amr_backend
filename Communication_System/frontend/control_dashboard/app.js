const state = {
  client: null,
  sessionId: null,
  voicePeer: null,
};

const elements = {
  serverInput: document.querySelector("#serverInput"),
  clientIdInput: document.querySelector("#clientIdInput"),
  deviceIdInput: document.querySelector("#deviceIdInput"),
  connectButton: document.querySelector("#connectButton"),
  disconnectButton: document.querySelector("#disconnectButton"),
  createSessionButton: document.querySelector("#createSessionButton"),
  startCallButton: document.querySelector("#startCallButton"),
  endCallButton: document.querySelector("#endCallButton"),
  serverBadge: document.querySelector("#serverBadge"),
  callBadge: document.querySelector("#callBadge"),
  sessionId: document.querySelector("#sessionId"),
  androidDevice: document.querySelector("#androidDevice"),
  micState: document.querySelector("#micState"),
  speakerState: document.querySelector("#speakerState"),
  remoteAudio: document.querySelector("#remoteAudio"),
  log: document.querySelector("#log"),
};

elements.serverInput.value = defaultWsBase();

function buildUrl() {
  const base = elements.serverInput.value.replace(/\/$/, "");
  const clientId = encodeURIComponent(elements.clientIdInput.value);
  const deviceId = encodeURIComponent(elements.deviceIdInput.value);
  return `${base}/ws/${clientId}?role=control&device_id=${deviceId}`;
}

function connect() {
  state.client = new SignalingClient({
    url: buildUrl(),
    onOpen: () => {
      setBadge(elements.serverBadge, "Server Connected", "online");
      appendLog(elements.log, "Connected to signaling server", "ok");
    },
    onClose: () => {
      setBadge(elements.serverBadge, "Server Disconnected", "offline");
      setBadge(elements.callBadge, "Call Idle", "idle");
      appendLog(elements.log, "Disconnected from signaling server");
    },
    onMessage: handleMessage,
    onError: (message) => appendLog(elements.log, message, "error"),
  });
  state.client.connect();
}

function handleMessage(message) {
  appendLog(elements.log, `${message.type}: ${JSON.stringify(message.payload ?? {})}`);

  if (message.type === SignalType.REGISTER) {
    return;
  }

  if (message.type === SignalType.ERROR) {
    setBadge(elements.callBadge, "Error", "error");
    return;
  }

  if (message.session_id) {
    state.sessionId = message.session_id;
    elements.sessionId.textContent = message.session_id;
  }

  if (message.type === SignalType.STATUS) {
    updateStatus(message.payload);
    return;
  }

  if (message.type === SignalType.ANSWER) {
    state.voicePeer?.acceptAnswer(message.payload);
    setBadge(elements.callBadge, "Call Connected", "connected");
    elements.micState.textContent = "Active";
    elements.speakerState.textContent = "Active";
    return;
  }

  if (message.type === SignalType.ICE_CANDIDATE) {
    state.voicePeer?.addIceCandidate(message.payload.candidate);
  }
}

function updateStatus(payload = {}) {
  const sessions = Object.values(payload.sessions ?? {});
  const clients = Object.values(payload.clients ?? {});
  const android = clients.find((client) => client.role === "android");
  const liveSessions = sessions
    .filter((item) => item.state !== "ended")
    .reverse();
  const session = liveSessions.find((item) => (
    android?.client_id && item.android_client_id === android.client_id
  )) ?? liveSessions[0] ?? [...sessions].reverse()[0];

  if (android) {
    elements.androidDevice.textContent = android.device_id;
  }

  if (session) {
    state.sessionId = session.session_id;
    elements.sessionId.textContent = session.session_id;
    if (session.state === "connected") {
      setBadge(elements.callBadge, "Call Connected", "connected");
      elements.micState.textContent = "Active";
      elements.speakerState.textContent = "Active";
    } else if (session.state === "calling") {
      setBadge(elements.callBadge, "Calling", "calling");
    } else if (session.state === "ready") {
      setBadge(elements.callBadge, "Call Ready", "online");
    } else {
      setBadge(elements.callBadge, `Call ${session.state}`, "idle");
    }
  }
}

function send(type) {
  state.client?.send({
    type,
    session_id: state.sessionId,
  });
}

function ensureVoicePeer() {
  if (state.voicePeer) {
    return state.voicePeer;
  }

  state.voicePeer = new VoicePeer({
    onIceCandidate: (candidate) => {
      state.client?.send({
        type: SignalType.ICE_CANDIDATE,
        session_id: state.sessionId,
        payload: { candidate },
      });
    },
    onRemoteStream: (stream) => {
      elements.remoteAudio.srcObject = stream;
      elements.speakerState.textContent = "Receiving";
    },
    onStateChange: (connectionState) => {
      appendLog(elements.log, `WebRTC state: ${connectionState}`);
      if (connectionState === "connected") {
        setBadge(elements.callBadge, "Call Connected", "connected");
      }
      if (["failed", "closed", "disconnected"].includes(connectionState)) {
        setBadge(elements.callBadge, `Call ${connectionState}`, "error");
      }
    },
    onError: (message) => appendLog(elements.log, `WebRTC error: ${message}`, "error"),
  });

  return state.voicePeer;
}

async function startCall() {
  if (!state.sessionId) {
    appendLog(elements.log, "Create a session before starting a call", "error");
    return;
  }

  try {
    setBadge(elements.callBadge, "Calling", "calling");
    elements.micState.textContent = "Requesting";
    const offer = await ensureVoicePeer().createOffer();
    elements.micState.textContent = "Sending";
    state.client?.send({
      type: SignalType.OFFER,
      session_id: state.sessionId,
      payload: offer,
    });
  } catch (error) {
    setBadge(elements.callBadge, "Call Failed", "error");
    elements.micState.textContent = "Blocked";
    appendLog(elements.log, `Start call failed: ${error.message}`, "error");
  }
}

function endCall() {
  setBadge(elements.callBadge, "Call Ended", "idle");
  elements.micState.textContent = "Standby";
  elements.speakerState.textContent = "Standby";
  state.voicePeer?.close();
  state.voicePeer = null;
  send(SignalType.CALL_END);
}

elements.connectButton.addEventListener("click", connect);
elements.disconnectButton.addEventListener("click", () => state.client?.disconnect());
elements.createSessionButton.addEventListener("click", () => send(SignalType.SESSION_CREATE));
elements.startCallButton.addEventListener("click", startCall);
elements.endCallButton.addEventListener("click", endCall);

appendLog(elements.log, "Dashboard ready");
