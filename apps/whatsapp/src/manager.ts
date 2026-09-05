import makeWASocket, {
  Browsers,
  DEFAULT_CONNECTION_CONFIG,
  DisconnectReason,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
  fetchLatestWaWebVersion,
  type WASocket,
  type WAMessage,
  type WAVersion,
} from "@whiskeysockets/baileys";
import pino from "pino";
import QRCode from "qrcode";
import { backend, setStatus } from "./api.js";
import { createDatabaseAuth } from "./auth.js";
import { incomingMedia, incomingText, isDirectIncoming } from "./messages.js";

// Skip forwarding media larger than this; the backend also caps at 20 MB.
const MAX_MEDIA_BYTES = 18 * 1024 * 1024;

// How long a resolved WhatsApp Web build is reused. Reconnects can be frequent
// and the build changes every few days, so re-fetching per connection would be
// wasted traffic against web.whatsapp.com.
const WA_VERSION_TTL_MS = 6 * 60 * 60 * 1000;

let cachedVersion: { value: WAVersion; fetchedAt: number } | undefined;

// --- Typing indicator ------------------------------------------------------
// An account that answers long messages instantly, around the clock, reads as
// automation. Showing "typing…" for a beat before every reply costs nothing and
// makes the account behave like the person it is standing in for.
//
// Length-aware rather than fixed: two seconds of typing for "Sí" looks as wrong
// as two seconds for a full paragraph. Set MIN and MAX to the same value for a
// fixed delay.
const typingEnabled = (process.env.WHATSAPP_TYPING_ENABLED || "true").toLowerCase() !== "false";
const typingMsPerChar = Number(process.env.WHATSAPP_TYPING_MS_PER_CHAR || 30);
const typingMinMs = Number(process.env.WHATSAPP_TYPING_MIN_MS || 1000);
const typingMaxMs = Number(process.env.WHATSAPP_TYPING_MAX_MS || 4000);

function typingDurationFor(text: string): number {
  if (!typingEnabled) return 0;
  const perChar = Number.isFinite(typingMsPerChar) ? typingMsPerChar : 30;
  const min = Number.isFinite(typingMinMs) ? typingMinMs : 1000;
  const max = Number.isFinite(typingMaxMs) ? typingMaxMs : 4000;
  return Math.max(0, Math.min(Math.max(min, text.length * perChar), Math.max(min, max)));
}

/** Show "typing…" for a moment, then send.
 *
 * The presence sequence mirrors what Baileys documents: subscribe, compose,
 * pause. Presence is cosmetic, so every step is best-effort — a chat state the
 * server rejects must never cost the customer their reply.
 */
async function sendTyped(socket: WASocket, remoteJid: string, text: string) {
  const pause = typingDurationFor(text);
  if (pause > 0) {
    try {
      await socket.presenceSubscribe(remoteJid);
      await socket.sendPresenceUpdate("composing", remoteJid);
    } catch {
      // Keep the pause anyway: the delay itself is half the point.
    }
    await new Promise((done) => setTimeout(done, pause));
    try {
      await socket.sendPresenceUpdate("paused", remoteJid);
    } catch {}
  }
  return socket.sendMessage(remoteJid, { text });
}

type ChannelConfig = {
  id: string;
  client_id: string;
  agent_id: string;
  enabled: boolean;
  auth_state: unknown | null;
};

type ChannelRuntime = {
  socket: WASocket;
  stopRequested: boolean;
  reconnectTimer?: NodeJS.Timeout;
};

type InboundResult = {
  accepted: boolean;
  reply?: string | null;
  outbound_message_id?: string | null;
};

const logger = pino({ level: process.env.WHATSAPP_LOG_LEVEL || "silent" });
const runtimes = new Map<string, ChannelRuntime>();

function errorCode(error: unknown): number | undefined {
  return (error as { output?: { statusCode?: number } } | undefined)?.output?.statusCode;
}

function cleanNumber(jid?: string | null): string | null {
  if (!jid) return null;
  return jid.split(":")[0]?.split("@")[0] || null;
}

async function processIncoming(channelId: string, socket: WASocket, message: WAMessage): Promise<void> {
  if (!isDirectIncoming(message)) return;
  const text = incomingText(message);
  const media = incomingMedia(message);
  const remoteJid = message.key.remoteJid;
  const externalMessageId = message.key.id;
  if ((!text && !media) || !remoteJid || !externalMessageId) return;

  const body: Record<string, unknown> = {
    external_message_id: externalMessageId,
    remote_jid: remoteJid,
    sender_name: message.pushName || null,
    text: text || "",
  };
  if (media) {
    try {
      const buffer = (await downloadMediaMessage(
        message,
        "buffer",
        {},
        { logger, reuploadRequest: socket.updateMediaMessage },
      )) as Buffer;
      if (buffer.length <= MAX_MEDIA_BYTES) {
        body.media_kind = media.kind;
        body.media_mime = media.mimetype;
        body.media_base64 = buffer.toString("base64");
      }
    } catch (error) {
      console.error(`[WhatsApp ${channelId}] Could not download media:`, (error as Error).message);
    }
  }

  const result = await backend<InboundResult>(`/channels/${channelId}/inbound`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!result.reply) return;
  const sent = await sendTyped(socket, remoteJid, result.reply);
  if (result.outbound_message_id && sent?.key.id) {
    await backend(`/channels/${channelId}/outbound-confirm`, {
      method: "POST",
      body: JSON.stringify({
        message_id: result.outbound_message_id,
        external_message_id: sent.key.id,
      }),
    });
  }
}

/** The WhatsApp Web build to advertise on the wire.
 *
 * Baileys ships a hardcoded build that only moves when a new release is
 * published, so it drifts behind the real one within days and WhatsApp then
 * labels our messages as sent from an outdated version. Sources are tried
 * newest-first: the live build scraped from web.whatsapp.com, then the list
 * Baileys maintains, then the bundled constant.
 *
 * A lookup failure never blocks a connection — an old build still connects,
 * and refusing to come online would be far worse than an outdated label.
 */
async function resolveWaVersion(): Promise<WAVersion> {
  if (cachedVersion && Date.now() - cachedVersion.fetchedAt < WA_VERSION_TTL_MS) {
    return cachedVersion.value;
  }
  for (const source of [fetchLatestWaWebVersion, fetchLatestBaileysVersion]) {
    try {
      // A failed lookup reports itself in `error` and hands back the bundled
      // build rather than throwing. Caching that would pin us to the stale
      // version for hours, so it counts as a miss and the next source is tried.
      const { version, error } = await source({});
      if (!error && Array.isArray(version) && version.length === 3) {
        cachedVersion = { value: version, fetchedAt: Date.now() };
        return version;
      }
    } catch {
      // Try the next source.
    }
  }
  return DEFAULT_CONNECTION_CONFIG.version as WAVersion;
}


export async function connectChannel(channelId: string): Promise<void> {
  const current = runtimes.get(channelId);
  if (current && !current.stopRequested) return;
  const config = await backend<ChannelConfig>(`/channels/${channelId}`);
  if (!config.enabled) throw new Error("The channel is disabled");
  await setStatus(channelId, config.auth_state ? "reconnecting" : "connecting");

  const { state, persist } = createDatabaseAuth(channelId, config.auth_state || undefined);
  const version = await resolveWaVersion();
  console.log(`[WhatsApp ${channelId}] Connecting as WhatsApp Web ${version.join(".")}`);
  const socket = makeWASocket({
    version,
    auth: state,
    logger,
    browser: Browsers.macOS("OpenLivery"),
    syncFullHistory: false,
    shouldSyncHistoryMessage: () => false,
    markOnlineOnConnect: false,
    generateHighQualityLinkPreview: false,
  });
  const runtime: ChannelRuntime = { socket, stopRequested: false };
  runtimes.set(channelId, runtime);

  socket.ev.on("creds.update", async (update) => {
    Object.assign(state.creds, update);
    try { await persist(); } catch (error) { console.error(`[WhatsApp ${channelId}] Could not save the session:`, (error as Error).message); }
  });

  socket.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;
    for (const message of messages) {
      try {
        await processIncoming(channelId, socket, message);
      } catch (error) {
        const detail = `Could not process an incoming message: ${(error as Error).message}`;
        console.error(`[WhatsApp ${channelId}] ${detail}`);
        await setStatus(channelId, "error", { error: detail.slice(0, 500) }).catch(() => undefined);
      }
    }
  });

  socket.ev.on("connection.update", async ({ connection, lastDisconnect, qr }) => {
    try {
      if (qr) {
        const qrCode = await QRCode.toDataURL(qr, { width: 360, margin: 2, errorCorrectionLevel: "M" });
        await setStatus(channelId, "qr", { qr_code: qrCode });
      }
      if (connection === "open") {
        await persist();
        await setStatus(channelId, "connected", {
          phone_number: cleanNumber(socket.user?.id),
          display_name: socket.user?.name || null,
        });
      }
      if (connection === "close") {
        const latest = runtimes.get(channelId);
        if (latest !== runtime) return;
        const code = errorCode(lastDisconnect?.error);
        const loggedOut = code === DisconnectReason.loggedOut || code === DisconnectReason.badSession;
        if (runtime.stopRequested || loggedOut) {
          runtimes.delete(channelId);
          await backend(`/channels/${channelId}/auth`, { method: "DELETE" });
          return;
        }
        await setStatus(channelId, "reconnecting", {
          error: code ? `WhatsApp closed the connection (${code}). Retrying…` : "Connection interrupted. Retrying…",
        });
        runtime.reconnectTimer = setTimeout(() => {
          runtimes.delete(channelId);
          void connectChannel(channelId).catch(async (error) => {
            await setStatus(channelId, "error", { error: (error as Error).message.slice(0, 500) }).catch(() => undefined);
          });
        }, 3000);
      }
    } catch (error) {
      await setStatus(channelId, "error", { error: (error as Error).message.slice(0, 500) }).catch(() => undefined);
    }
  });
}

export async function disconnectChannel(channelId: string): Promise<void> {
  const runtime = runtimes.get(channelId);
  if (runtime) {
    runtime.stopRequested = true;
    if (runtime.reconnectTimer) clearTimeout(runtime.reconnectTimer);
    try { await runtime.socket.logout(); } catch {}
    runtimes.delete(channelId);
  }
  await backend(`/channels/${channelId}/auth`, { method: "DELETE" });
}

export async function sendMessage(channelId: string, remoteJid: string, text: string): Promise<string> {
  const runtime = runtimes.get(channelId);
  if (!runtime || runtime.stopRequested) throw new Error("WhatsApp is not connected")
  const sent = await sendTyped(runtime.socket, remoteJid, text);
  if (!sent?.key.id) throw new Error("WhatsApp did not confirm the send")
  return sent.key.id;
}

export async function restoreChannels(): Promise<void> {
  const channels = await backend<Array<{ id: string }>>("/channels");
  const results = await Promise.allSettled(channels.map((item) => connectChannel(item.id)));
  results.forEach((result, index) => {
    if (result.status === "rejected") console.error(`[WhatsApp ${channels[index]?.id}] Could not restore:`, result.reason?.message || result.reason);
  });
}

export async function shutdown(): Promise<void> {
  for (const runtime of runtimes.values()) {
    runtime.stopRequested = true;
    if (runtime.reconnectTimer) clearTimeout(runtime.reconnectTimer);
    runtime.socket.end(new Error("OpenLivery is shutting down"));
  }
  runtimes.clear();
}
