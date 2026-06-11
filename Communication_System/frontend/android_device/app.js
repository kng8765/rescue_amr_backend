const state = {
  client: null,
  clientId: `android-${Math.floor(Math.random() * 10000)}`,
  sessionId: null,
  voicePeer: null,
};

const elements = {
  serverInput: document.querySelector("#serverInput"),
  deviceIdInput: document.querySelector("#deviceIdInput"),
  connectButton: document.querySelector("#connectButton"),
  disconnectButton: document.querySelector("#disconnectButton"),
  serverState: document.querySelector("#serverState"),
  callState: document.querySelector("#callState"),
  micState: document.querySelector("#micState"),
  speakerState: document.querySelector("#speakerState"),
  remoteAudio: document.querySelector("#remoteAudio"),
  log: document.querySelector("#log"),
};

elements.serverInput.value = defaultWsBase();

function buildUrl() {
  const base = elements.serverInput.value.replace(/\/$/, "");
  const deviceId = encodeURIComponent(elements.deviceIdInput.value);
  return `${base}/ws/${state.clientId}?role=android&device_id=${deviceId}`;
}

function connect() {
  state.client = new SignalingClient({
    url: buildUrl(),
    onOpen: () => {
      setBadge(elements.serverState, "SERVER ONLINE", "online");
      elements.callState.textContent = "연결 대기";
      appendLog(elements.log, "Connected to signaling server", "ok");
    },
    onClose: () => {
      setBadge(elements.serverState, "SERVER OFFLINE", "offline");
      elements.callState.textContent = "대기 중";
      elements.micState.textContent = "대기";
      elements.speakerState.textContent = "대기";
      appendLog(elements.log, "Disconnected from signaling server");
    },
    onMessage: handleMessage,
    onError: (message) => {
      setBadge(elements.serverState, "SERVER ERROR", "error");
      appendLog(elements.log, message, "error");
    },
  });
  state.client.connect();
}

function handleMessage(message) {
  appendLog(elements.log, `${message.type}: ${JSON.stringify(message.payload ?? {})}`);

  if (message.session_id) {
    state.sessionId = message.session_id;
  }

  if (message.type === SignalType.CALL_START || message.type === SignalType.OFFER) {
    elements.callState.textContent = "통화 요청";
    elements.micState.textContent = "준비";
    elements.speakerState.textContent = "준비";
  }

  if (message.type === SignalType.OFFER) {
    answerOffer(message.payload);
    return;
  }

  if (message.type === SignalType.CALL_END) {
    state.voicePeer?.close();
    state.voicePeer = null;
    elements.callState.textContent = "통화 종료";
    elements.micState.textContent = "대기";
    elements.speakerState.textContent = "대기";
  }

  if (message.type === SignalType.ICE_CANDIDATE) {
    state.voicePeer?.addIceCandidate(message.payload.candidate);
  }

  if (message.type === SignalType.ERROR) {
    elements.callState.textContent = "오류";
  }
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
      elements.speakerState.textContent = "수신";
    },
    onStateChange: (connectionState) => {
      appendLog(elements.log, `WebRTC state: ${connectionState}`);
      if (connectionState === "connected") {
        elements.callState.textContent = "통화 중";
        elements.micState.textContent = "활성";
        elements.speakerState.textContent = "활성";
      }
      if (["failed", "closed", "disconnected"].includes(connectionState)) {
        elements.callState.textContent = "연결 불안정";
      }
    },
    onError: (message) => appendLog(elements.log, `WebRTC error: ${message}`, "error"),
  });

  return state.voicePeer;
}

async function answerOffer(offer) {
  try {
    elements.callState.textContent = "응답 중";
    elements.micState.textContent = "권한 확인";
    const answer = await ensureVoicePeer().createAnswer(offer);
    elements.micState.textContent = "송신";
    state.client?.send({
      type: SignalType.ANSWER,
      session_id: state.sessionId,
      payload: answer,
    });
  } catch (error) {
    elements.callState.textContent = "통화 실패";
    elements.micState.textContent = "차단";
    appendLog(elements.log, `Answer failed: ${error.message}`, "error");
  }
}

elements.connectButton.addEventListener("click", connect);
elements.disconnectButton.addEventListener("click", () => state.client?.disconnect());

appendLog(elements.log, "Android device UI ready");
