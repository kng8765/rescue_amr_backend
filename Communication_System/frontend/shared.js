const SignalType = Object.freeze({
  REGISTER: "register",
  SESSION_CREATE: "session_create",
  OFFER: "offer",
  ANSWER: "answer",
  ICE_CANDIDATE: "ice_candidate",
  CALL_START: "call_start",
  CALL_END: "call_end",
  HEARTBEAT: "heartbeat",
  RECONNECT: "reconnect",
  STATUS: "status",
  ERROR: "error",
});

class SignalingClient {
  constructor({ url, onOpen, onClose, onMessage, onError }) {
    this.url = url;
    this.socket = null;
    this.heartbeatTimer = null;
    this.onOpen = onOpen;
    this.onClose = onClose;
    this.onMessage = onMessage;
    this.onError = onError;
  }

  connect() {
    this.disconnect();
    this.socket = new WebSocket(this.url);

    this.socket.addEventListener("open", () => {
      this.send({ type: SignalType.REGISTER });
      this.heartbeatTimer = window.setInterval(() => {
        this.send({ type: SignalType.HEARTBEAT });
      }, 5000);
      this.onOpen?.();
    });

    this.socket.addEventListener("message", (event) => {
      try {
        this.onMessage?.(JSON.parse(event.data));
      } catch (error) {
        this.onError?.(`Invalid JSON message: ${error.message}`);
      }
    });

    this.socket.addEventListener("close", () => {
      this.clearHeartbeat();
      this.onClose?.();
    });

    this.socket.addEventListener("error", () => {
      this.onError?.("WebSocket connection error");
    });
  }

  disconnect() {
    this.clearHeartbeat();
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  send(message) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.onError?.("WebSocket is not connected");
      return false;
    }
    this.socket.send(JSON.stringify(message));
    return true;
  }

  clearHeartbeat() {
    if (this.heartbeatTimer) {
      window.clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }
}

function formatTime(date = new Date()) {
  return date.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function appendLog(element, message, level = "info") {
  const row = document.createElement("div");
  row.className = `log-row log-${level}`;
  row.textContent = `[${formatTime()}] ${message}`;
  element.prepend(row);

  while (element.children.length > 80) {
    element.removeChild(element.lastChild);
  }
}

function setBadge(element, label, state) {
  element.textContent = label;
  element.dataset.state = state;
}

function defaultWsBase() {
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}`;
  }
  return "ws://127.0.0.1:8000";
}

class VoicePeer {
  constructor({ onIceCandidate, onRemoteStream, onStateChange, onError }) {
    this.peer = null;
    this.localStream = null;
    this.onIceCandidate = onIceCandidate;
    this.onRemoteStream = onRemoteStream;
    this.onStateChange = onStateChange;
    this.onError = onError;
  }

  async ensurePeer() {
    if (this.peer) {
      return this.peer;
    }

    if (!window.isSecureContext) {
      throw new Error("Microphone access requires HTTPS, localhost, or adb reverse.");
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("This browser does not support microphone access on the current page.");
    }

    if (!window.RTCPeerConnection) {
      throw new Error("This browser does not support WebRTC.");
    }

    this.peer = new RTCPeerConnection({ iceServers: [] });
    this.peer.addEventListener("icecandidate", (event) => {
      if (event.candidate) {
        this.onIceCandidate?.(event.candidate.toJSON());
      }
    });
    this.peer.addEventListener("track", (event) => {
      this.onRemoteStream?.(event.streams[0]);
    });
    this.peer.addEventListener("connectionstatechange", () => {
      this.onStateChange?.(this.peer.connectionState);
    });

    this.localStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });
    this.localStream.getTracks().forEach((track) => {
      this.peer.addTrack(track, this.localStream);
    });

    return this.peer;
  }

  async createOffer() {
    try {
      const peer = await this.ensurePeer();
      const offer = await peer.createOffer({ offerToReceiveAudio: true });
      await peer.setLocalDescription(offer);
      return peer.localDescription.toJSON();
    } catch (error) {
      this.onError?.(error.message);
      throw error;
    }
  }

  async createAnswer(offer) {
    try {
      const peer = await this.ensurePeer();
      await peer.setRemoteDescription(new RTCSessionDescription(offer));
      const answer = await peer.createAnswer();
      await peer.setLocalDescription(answer);
      return peer.localDescription.toJSON();
    } catch (error) {
      this.onError?.(error.message);
      throw error;
    }
  }

  async acceptAnswer(answer) {
    try {
      await this.peer?.setRemoteDescription(new RTCSessionDescription(answer));
    } catch (error) {
      this.onError?.(error.message);
      throw error;
    }
  }

  async addIceCandidate(candidate) {
    try {
      if (!candidate || !this.peer) {
        return;
      }
      await this.peer.addIceCandidate(new RTCIceCandidate(candidate));
    } catch (error) {
      this.onError?.(error.message);
    }
  }

  close() {
    this.localStream?.getTracks().forEach((track) => track.stop());
    this.localStream = null;
    this.peer?.close();
    this.peer = null;
  }
}
