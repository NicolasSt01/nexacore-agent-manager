// UI strings for the "channels" area. Fill `en` and mirror it in `es`.
const en = {
  head: {
    eyebrow: "Channels",
    title: "Channels",
    description: "Connect each client's number to its own agent and Inbox.",
  },
  toolbar: {
    clientLabel: "Client",
    allClients: "All clients",
    openClient: "Open client",
  },
  whatsappCloud: {
    status: "Available",
    title: "WhatsApp API",
    description:
      "Official WhatsApp Business Cloud API, hosted by Meta. Connect a number with your own Meta app credentials.",
    ownerPlaceholder: "Choose a client to configure its number",
    configure: "Configure WhatsApp API",
    selectClient: "Select a client",
  },
  whatsapp: {
    status: "Available",
    title: "WhatsApp QR",
    description:
      "Scan a QR with the WhatsApp app on your phone, reply with an agent, and let the team take over from the Inbox.",
    ownerPlaceholder: "Choose a client to configure its number",
    configure: "Configure WhatsApp QR",
    selectClient: "Select a client",
  },
  messenger: {
    status: "Available",
    title: "Facebook Messenger",
    description:
      "Connect a Facebook Page with your own Meta app credentials and answer its inbox with an agent.",
    ownerPlaceholder: "Choose a client to configure its page",
    configure: "Configure Messenger",
    selectClient: "Select a client",
  },
  instagram: {
    status: "Available",
    title: "Instagram Direct",
    description:
      "Answer the direct messages of a professional Instagram account linked to your Facebook Page.",
    ownerPlaceholder: "Choose a client to configure its account",
    configure: "Configure Instagram",
    selectClient: "Select a client",
  },
  webchat: {
    status: "Available",
    title: "Webchat",
    description:
      "Embed an assistant on any website with a single line of code. Each agent has its own snippet.",
    ownerPlaceholder: "Configured on each agent",
    configure: "Open agents",
  },
  note: {
    strong: "Each connection belongs to a single client.",
    rest: "Its number, agent, session, and conversations stay separate from other spaces.",
  },
  meta: {
    loading: "Loading channel…",
    messengerTitle: "Facebook Messenger",
    messengerCopy: "Answer the Page inbox automatically with this client's agent.",
    instagramTitle: "Instagram Direct",
    instagramCopy: "Answer Instagram direct messages automatically with this client's agent.",
    statusDisconnected: "Not connected",
    statusConnected: "Connected",
    statusError: "Connection error",
    credentialsTitle: "Meta app credentials",
    credentialsCopy: "Taken from your Meta app. They are stored encrypted and never returned to the browser.",
    pageIdLabel: "Facebook Page ID",
    pageIdHint: "Found in the Page settings, under \u201CPage transparency\u201D.",
    igIdLabel: "Instagram account ID",
    igIdHint: "The professional account ID linked to the Page.",
    accessTokenLabel: "Access token",
    appSecretLabel: "App secret",
    connectedAccount: "Connected account",
    webhookCopy: "Register this URL in your Meta app and subscribe to the messages events.",
    webhookStep1: "In your Meta app, open Webhooks and add the callback URL with the verify token above.",
    webhookStep2: "Subscribe the account to the messages, messaging_postbacks and message_reactions fields.",
    webhookStep3: "Send a test message: it will show up in this client's inbox.",
    confirmDisconnect: "Disconnect this channel? The agent will stop replying.",
    needsAgent: "This client needs at least one agent before connecting this channel.",
  },
};

const es: typeof en = {
  head: {
    eyebrow: "Canales",
    title: "Canales",
    description: "Conecta el número de cada cliente con su propio agente e Inbox.",
  },
  toolbar: {
    clientLabel: "Cliente",
    allClients: "Todos los clientes",
    openClient: "Abrir cliente",
  },
  whatsappCloud: {
    status: "Disponible",
    title: "WhatsApp API",
    description:
      "API oficial de WhatsApp Business Cloud, alojada por Meta. Conecta un número con las credenciales de tu propia app de Meta.",
    ownerPlaceholder: "Elige un cliente para configurar su número",
    configure: "Configurar WhatsApp API",
    selectClient: "Selecciona un cliente",
  },
  whatsapp: {
    status: "Disponible",
    title: "WhatsApp QR",
    description:
      "Escanea un QR con la app de WhatsApp de tu teléfono, responde con un agente y permite que el equipo tome el control desde el Inbox.",
    ownerPlaceholder: "Elige un cliente para configurar su número",
    configure: "Configurar WhatsApp QR",
    selectClient: "Selecciona un cliente",
  },
  messenger: {
    status: "Disponible",
    title: "Facebook Messenger",
    description:
      "Conecta una página de Facebook con las credenciales de tu propia app de Meta y responde su bandeja con un agente.",
    ownerPlaceholder: "Elige un cliente para configurar su página",
    configure: "Configurar Messenger",
    selectClient: "Selecciona un cliente",
  },
  instagram: {
    status: "Disponible",
    title: "Instagram Direct",
    description:
      "Responde los mensajes directos de una cuenta profesional de Instagram vinculada a tu página de Facebook.",
    ownerPlaceholder: "Elige un cliente para configurar su cuenta",
    configure: "Configurar Instagram",
    selectClient: "Selecciona un cliente",
  },
  webchat: {
    status: "Disponible",
    title: "Webchat",
    description:
      "Inserta un asistente en cualquier sitio web con una línea de código. Cada agente tiene su propio fragmento.",
    ownerPlaceholder: "Se configura en cada agente",
    configure: "Abrir agentes",
  },
  note: {
    strong: "Cada conexión pertenece a un solo cliente.",
    rest: "Su número, agente, sesión y conversaciones permanecen separados de los demás espacios.",
  },
  meta: {
    loading: "Cargando canal…",
    messengerTitle: "Facebook Messenger",
    messengerCopy: "Responde automáticamente los mensajes de la página con el agente de este cliente.",
    instagramTitle: "Instagram Direct",
    instagramCopy: "Responde automáticamente los mensajes directos de Instagram con el agente de este cliente.",
    statusDisconnected: "Sin conectar",
    statusConnected: "Conectado",
    statusError: "Error de conexión",
    credentialsTitle: "Credenciales de la app de Meta",
    credentialsCopy: "Se toman de tu app de Meta. Se guardan cifradas y nunca vuelven al navegador.",
    pageIdLabel: "ID de la página de Facebook",
    pageIdHint: "Está en la configuración de la página, en \u201CTransparencia de la página\u201D.",
    igIdLabel: "ID de la cuenta de Instagram",
    igIdHint: "El ID de la cuenta profesional vinculada a la página.",
    accessTokenLabel: "Token de acceso",
    appSecretLabel: "App secret",
    connectedAccount: "Cuenta conectada",
    webhookCopy: "Registra esta URL en tu app de Meta y suscríbete a los eventos de mensajes.",
    webhookStep1: "En tu app de Meta, abre Webhooks y agrega la URL de callback con el token de verificación de arriba.",
    webhookStep2: "Suscribe la cuenta a los campos messages, messaging_postbacks y message_reactions.",
    webhookStep3: "Envía un mensaje de prueba: aparecerá en el inbox de este cliente.",
    confirmDisconnect: "¿Desconectar este canal? El agente dejará de responder.",
    needsAgent: "Este cliente necesita al menos un agente antes de conectar este canal.",
  },
};

export const channels = { en, es };
