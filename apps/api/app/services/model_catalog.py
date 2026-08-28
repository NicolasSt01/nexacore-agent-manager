"""AI model catalog with metadata (backend source of truth).

Each model declares its context window, capabilities (tools/vision) and price
per 1k tokens. This metadata powers:
- the model picker and token counter in the agent creation wizard,
- cost estimation and per-model markup (billing).

These are the seed values for the `model_prices` table and the fallback when a
model has no price row yet. The frontend reads this catalog through
`/api/catalog/models`; there is no second copy to keep in sync.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    id: str
    provider: str
    label: str
    family: str
    context_window: int
    max_output_tokens: int
    supports_tools: bool
    supports_vision: bool
    # Provider price per 1,000 tokens, in USD.
    input_price_per_1k: float
    output_price_per_1k: float
    badge: str = ""
    note: str = ""


# Standard approximation to estimate tokens without a tokenizer: ~4 chars/token.
CHARS_PER_TOKEN = 4


# Prices are USD per 1,000 tokens, as published by each provider. They are the
# seed for the `model_prices` table; once a price lives there, that row wins.
# The daily catalog sync (services/model_sync.py) reports drift against this
# list so the owner can react before it shows up in the margin.
_MODELS: tuple[ModelInfo, ...] = (
    # --- OpenAI ---------------------------------------------------------
    ModelInfo("gpt-5", "openai", "GPT-5", "gpt-5", 400_000, 128_000, True, True,
              0.00125, 0.010, "Top capability", "Complex reasoning and demanding conversations."),
    ModelInfo("gpt-5-mini", "openai", "GPT-5 mini", "gpt-5", 400_000, 128_000, True, True,
              0.00025, 0.002, "Balanced", "A good default for customer-facing agents."),
    ModelInfo("gpt-5-nano", "openai", "GPT-5 nano", "gpt-5", 400_000, 128_000, True, True,
              0.00005, 0.0004, "Most affordable", "High volume, short answers, cost-sensitive."),
    ModelInfo("gpt-4.1", "openai", "GPT-4.1", "gpt-4.1", 1_047_576, 32_768, True, True,
              0.002, 0.008, "Long context", "Very large documents and long histories."),
    ModelInfo("gpt-4.1-mini", "openai", "GPT-4.1 mini", "gpt-4.1", 1_047_576, 32_768, True, True,
              0.0004, 0.0016, "Economical", "Solid quality at a low price; a safe default."),
    ModelInfo("gpt-4.1-nano", "openai", "GPT-4.1 nano", "gpt-4.1", 1_047_576, 32_768, True, True,
              0.0001, 0.0004, "Cheapest OpenAI", "Simple FAQ-style agents at scale."),
    ModelInfo("gpt-4o", "openai", "GPT-4o", "gpt-4o", 128_000, 16_384, True, True,
              0.0025, 0.010, "Previous generation", "Kept for compatibility."),
    ModelInfo("gpt-4o-mini", "openai", "GPT-4o mini", "gpt-4o", 128_000, 16_384, True, True,
              0.00015, 0.0006, "Previous generation", "Kept for compatibility."),

    # --- Anthropic ------------------------------------------------------
    ModelInfo("claude-opus-5", "anthropic", "Claude Opus 5", "claude-5", 200_000, 64_000, True, True,
              0.005, 0.025, "Top capability", "The most capable Claude model."),
    ModelInfo("claude-sonnet-5", "anthropic", "Claude Sonnet 5", "claude-5", 200_000, 64_000, True, True,
              0.003, 0.015, "Balanced", "Strong quality for customer conversations."),
    ModelInfo("claude-fable-5", "anthropic", "Claude Fable 5", "claude-5", 200_000, 64_000, True, True,
              0.001, 0.005, "Fast", "Quick replies at a lower price."),
    ModelInfo("claude-haiku-4-5-20251001", "anthropic", "Claude Haiku 4.5", "claude-haiku-4", 200_000, 64_000, True, True,
              0.001, 0.005, "Economical", "Previous generation, kept for cost-sensitive agents."),

    # --- DeepSeek (direct) ----------------------------------------------
    ModelInfo("deepseek-chat", "deepseek", "DeepSeek Chat", "deepseek-v3", 128_000, 8_192, True, False,
              0.00027, 0.0011, "Very economical", "Excellent price for high-volume chat."),
    ModelInfo("deepseek-reasoner", "deepseek", "DeepSeek Reasoner", "deepseek-r1", 128_000, 65_536, True, False,
              0.00055, 0.00219, "Reasoning", "Step-by-step reasoning at a low price."),

    # --- Qwen / DashScope ------------------------------------------------
    ModelInfo("qwen-max", "qwen", "Qwen Max", "qwen", 32_768, 8_192, True, False,
              0.0016, 0.0064, "Top capability", "Alibaba's most capable Qwen model."),
    ModelInfo("qwen-plus", "qwen", "Qwen Plus", "qwen", 131_072, 8_192, True, False,
              0.0004, 0.0012, "Balanced", "Good quality at a moderate price."),
    ModelInfo("qwen-turbo", "qwen", "Qwen Turbo", "qwen", 1_000_000, 8_192, True, False,
              0.00005, 0.0002, "Cheapest", "Very high volume, simple conversations."),

    # --- OpenRouter (gateway; prices follow the upstream model) ----------
    ModelInfo("deepseek/deepseek-chat", "openrouter", "DeepSeek Chat (OpenRouter)", "deepseek-v3", 128_000, 8_192, True, False,
              0.00027, 0.0011, "Very economical", "DeepSeek through the OpenRouter gateway."),
    ModelInfo("deepseek/deepseek-r1", "openrouter", "DeepSeek R1 (OpenRouter)", "deepseek-r1", 128_000, 65_536, True, False,
              0.00055, 0.00219, "Reasoning", "DeepSeek R1 through OpenRouter."),
    ModelInfo("qwen/qwen-2.5-72b-instruct", "openrouter", "Qwen 2.5 72B (OpenRouter)", "qwen", 131_072, 8_192, True, False,
              0.0004, 0.0004, "Economical", "Open-weight Qwen through OpenRouter."),
    ModelInfo("meta-llama/llama-3.3-70b-instruct", "openrouter", "Llama 3.3 70B (OpenRouter)", "llama-3", 131_072, 8_192, True, False,
              0.00012, 0.0003, "Cheapest", "Open-weight Llama through OpenRouter."),
    # --- OpenCode Zen (gateway; live catalog, cheapest first) -------------
    # Verified against opencode.ai/zen/v1 on 2026-08-27.
    ModelInfo("deepseek-v4-flash-free", "opencode", "DeepSeek V4 Flash Free", "deepseek-flash", 200000, 65536, True, False,
              0.00000000, 0.00000000, "Free tier", "No metered cost; check the rate limits before selling it."),
    ModelInfo("hy3-free", "opencode", "Hy3 Free", "hy3-free", 190000, 64000, True, False,
              0.00000000, 0.00000000, "Free tier", "No metered cost; check the rate limits before selling it."),
    ModelInfo("nemotron-3.5-lightning-free", "opencode", "Nemotron 3.5 Lightning Free", "nemotron-free", 262144, 65536, True, False,
              0.00000000, 0.00000000, "Free tier", "No metered cost; check the rate limits before selling it."),
    ModelInfo("mimo-v2.5-free", "opencode", "MiMo V2.5 Free", "mimo-v2.5-free", 200000, 32000, True, True,
              0.00000000, 0.00000000, "Free tier", "No metered cost; check the rate limits before selling it."),
    ModelInfo("nemotron-3-ultra-free", "opencode", "Nemotron 3 Ultra Free", "nemotron-free", 1000000, 65536, True, False,
              0.00000000, 0.00000000, "Free tier", "No metered cost; check the rate limits before selling it."),
    ModelInfo("laguna-s-2.1-free", "opencode", "Laguna S 2.1 Free", "laguna", 256000, 32000, True, False,
              0.00000000, 0.00000000, "Free tier", "No metered cost; check the rate limits before selling it."),
    ModelInfo("muse-spark-1.2-contributor-free", "opencode", "Muse Spark 1.2 Free", "muse-free", 1048576, 65536, True, True,
              0.00000000, 0.00000000, "Free tier", "No metered cost; check the rate limits before selling it."),
    ModelInfo("big-pickle", "opencode", "Big Pickle", "big-pickle", 200000, 32000, True, False,
              0.00000000, 0.00000000, "Free tier", "No metered cost; check the rate limits before selling it."),
    ModelInfo("gpt-5-nano", "opencode", "GPT-5 Nano", "gpt-nano", 400000, 65536, True, True,
              0.00005000, 0.00040000, "Economical", "Good balance of price and quality."),
    ModelInfo("deepseek-v4-flash", "opencode", "DeepSeek V4 Flash", "deepseek-flash", 1000000, 65536, True, False,
              0.00014000, 0.00028000, "Economical", "Good balance of price and quality."),
    ModelInfo("qwen3.5-plus", "opencode", "Qwen3.5 Plus", "qwen3.5", 262144, 65536, True, True,
              0.00020000, 0.00120000, "Economical", "Good balance of price and quality."),
    ModelInfo("gpt-5.6-luna", "opencode", "GPT-5.6 Luna", "gpt-luna", 1050000, 65536, True, True,
              0.00020000, 0.00120000, "Economical", "Good balance of price and quality."),
    ModelInfo("gpt-5.4-nano", "opencode", "GPT-5.4 Nano", "gpt-nano", 400000, 65536, True, True,
              0.00020000, 0.00125000, "Economical", "Good balance of price and quality."),
    ModelInfo("gpt-5.1-codex-mini", "opencode", "GPT-5.1 Codex Mini", "gpt-codex", 400000, 65536, True, True,
              0.00025000, 0.00200000, "Economical", "Good balance of price and quality."),
    ModelInfo("minimax-m2.7", "opencode", "MiniMax-M2.7", "minimax", 204800, 65536, True, False,
              0.00030000, 0.00120000, "Economical", "Good balance of price and quality."),
    ModelInfo("minimax-m3", "opencode", "MiniMax-M3", "minimax", 512000, 65536, True, True,
              0.00030000, 0.00120000, "Economical", "Good balance of price and quality."),
    ModelInfo("minimax-m2.5", "opencode", "MiniMax-M2.5", "minimax", 204800, 65536, True, False,
              0.00030000, 0.00120000, "Economical", "Good balance of price and quality."),
    ModelInfo("gemini-3.5-flash-lite", "opencode", "Gemini 3.5 Flash Lite", "gemini-flash-lite", 1048576, 65536, True, True,
              0.00030000, 0.00250000, "Economical", "Good balance of price and quality."),
    ModelInfo("gemini-3-flash", "opencode", "Gemini 3 Flash", "gemini-flash", 1048576, 65536, True, True,
              0.00050000, 0.00300000, "Economical", "Good balance of price and quality."),
    ModelInfo("qwen3.6-plus", "opencode", "Qwen3.6 Plus", "qwen3.6", 262144, 65536, True, True,
              0.00050000, 0.00300000, "Economical", "Good balance of price and quality."),
    ModelInfo("kimi-k2.5", "opencode", "Kimi K2.5", "kimi-k2", 262144, 65536, True, True,
              0.00060000, 0.00300000, "Economical", "Good balance of price and quality."),
    ModelInfo("gpt-5.4-mini", "opencode", "GPT-5.4 Mini", "gpt-mini", 400000, 65536, True, True,
              0.00075000, 0.00450000, "Economical", "Good balance of price and quality."),
    ModelInfo("kimi-k2.7-code", "opencode", "Kimi K2.7 Code", "kimi-k2", 262144, 65536, True, True,
              0.00095000, 0.00400000, "Economical", "Good balance of price and quality."),
    ModelInfo("kimi-k2.6", "opencode", "Kimi K2.6", "kimi-k2", 262144, 65536, True, True,
              0.00095000, 0.00400000, "Economical", "Good balance of price and quality."),
    ModelInfo("grok-build-0.1", "opencode", "Grok Build 0.1", "grok-build", 256000, 65536, True, True,
              0.00100000, 0.00200000, "Economical", "Good balance of price and quality."),
    ModelInfo("glm-5", "opencode", "GLM-5", "glm", 204800, 65536, True, False,
              0.00100000, 0.00320000, "Economical", "Good balance of price and quality."),
    ModelInfo("claude-haiku-4-5", "opencode", "Claude Haiku 4.5", "claude-haiku", 200000, 64000, True, True,
              0.00100000, 0.00500000, "Economical", "Good balance of price and quality."),
    ModelInfo("gpt-5", "opencode", "GPT-5", "gpt", 400000, 65536, True, True,
              0.00107000, 0.00850000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gpt-5.1", "opencode", "GPT-5.1", "gpt", 400000, 65536, True, True,
              0.00107000, 0.00850000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gpt-5-codex", "opencode", "GPT-5 Codex", "gpt-codex", 400000, 65536, True, True,
              0.00107000, 0.00850000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gpt-5.1-codex", "opencode", "GPT-5.1 Codex", "gpt-codex", 400000, 65536, True, True,
              0.00107000, 0.00850000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("muse-spark-1.2", "opencode", "Muse Spark 1.2", "muse", 1048576, 65536, True, True,
              0.00125000, 0.00425000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gpt-5.1-codex-max", "opencode", "GPT-5.1 Codex Max", "gpt-codex", 400000, 65536, True, True,
              0.00125000, 0.01000000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("glm-5.1", "opencode", "GLM-5.1", "glm", 204800, 65536, True, False,
              0.00140000, 0.00440000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("glm-5.2", "opencode", "GLM-5.2", "glm", 1000000, 65536, True, False,
              0.00140000, 0.00440000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gemini-3.7-flash", "opencode", "Gemini 3.7 Flash", "gemini-flash", 1048576, 65536, True, True,
              0.00150000, 0.00750000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gemini-3.6-flash", "opencode", "Gemini 3.6 Flash", "gemini-flash", 1048576, 65536, True, True,
              0.00150000, 0.00750000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gemini-3.5-flash", "opencode", "Gemini 3.5 Flash", "gemini-flash", 1048576, 65536, True, True,
              0.00150000, 0.00900000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("deepseek-v4-pro", "opencode", "DeepSeek V4 Pro", "deepseek-thinking", 1000000, 65536, True, False,
              0.00174000, 0.00384000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gpt-5.3-codex", "opencode", "GPT-5.3 Codex", "gpt-codex", 400000, 65536, True, True,
              0.00175000, 0.01400000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gpt-5.2", "opencode", "GPT-5.2", "gpt", 400000, 65536, True, True,
              0.00175000, 0.01400000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gpt-5.2-codex", "opencode", "GPT-5.2 Codex", "gpt-codex", 400000, 65536, True, True,
              0.00175000, 0.01400000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gpt-5.3-codex-spark", "opencode", "GPT-5.3 Codex Spark", "gpt-codex-spark", 128000, 65536, True, False,
              0.00175000, 0.01400000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("grok-4.6", "opencode", "Grok 4.6", "grok", 500000, 65536, True, True,
              0.00200000, 0.00600000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("grok-4.5", "opencode", "Grok 4.5", "grok", 500000, 65536, True, True,
              0.00200000, 0.00600000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("claude-sonnet-5", "opencode", "Claude Sonnet 5", "claude-sonnet", 1000000, 65536, True, True,
              0.00200000, 0.01000000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gpt-5.6-sol", "opencode", "GPT-5.6 Sol (50% Off)", "gpt-sol", 1050000, 65536, True, True,
              0.00200000, 0.01000000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gemini-3.1-pro", "opencode", "Gemini 3.1 Pro Preview", "gemini-pro", 1048576, 65536, True, True,
              0.00200000, 0.01200000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gpt-5.4", "opencode", "GPT-5.4", "gpt", 1050000, 65536, True, True,
              0.00250000, 0.01500000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("gpt-5.6-terra", "opencode", "GPT-5.6 Terra", "gpt-terra", 1050000, 65536, True, True,
              0.00250000, 0.01500000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("claude-sonnet-4-6", "opencode", "Claude Sonnet 4.6", "claude-sonnet", 1000000, 64000, True, True,
              0.00300000, 0.01500000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("kimi-k3", "opencode", "Kimi K3", "kimi-k3", 1048576, 65536, True, True,
              0.00300000, 0.01500000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("claude-sonnet-4-5", "opencode", "Claude Sonnet 4.5", "claude-sonnet", 1000000, 64000, True, True,
              0.00300000, 0.01500000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("claude-sonnet-4", "opencode", "Claude Sonnet 4", "claude-sonnet", 1000000, 64000, True, True,
              0.00300000, 0.01500000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("claude-opus-4-5", "opencode", "Claude Opus 4.5", "claude-opus", 200000, 64000, True, True,
              0.00500000, 0.02500000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("claude-opus-4-6", "opencode", "Claude Opus 4.6", "claude-opus", 1000000, 65536, True, True,
              0.00500000, 0.02500000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("claude-opus-4-7", "opencode", "Claude Opus 4.7", "claude-opus", 1000000, 65536, True, True,
              0.00500000, 0.02500000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("claude-opus-4-8", "opencode", "Claude Opus 4.8", "claude-opus", 1000000, 65536, True, True,
              0.00500000, 0.02500000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("claude-opus-5", "opencode", "Claude Opus 5", "claude-opus", 1000000, 65536, True, True,
              0.00500000, 0.02500000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("gpt-5.5", "opencode", "GPT-5.5", "gpt", 1050000, 65536, True, True,
              0.00500000, 0.03000000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("claude-fable-5", "opencode", "Claude Fable 5", "claude-fable", 1000000, 65536, True, True,
              0.01000000, 0.05000000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("gpt-5.4-pro", "opencode", "GPT-5.4 Pro", "gpt-pro", 1050000, 65536, True, True,
              0.03000000, 0.18000000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("gpt-5.5-pro", "opencode", "GPT-5.5 Pro", "gpt-pro", 1050000, 65536, True, True,
              0.03000000, 0.18000000, "Top capability", "Only where quality justifies the cost."),

    # --- OpenCode GO (subscription gateway; live catalog, cheapest first) --
    # Verified against opencode.ai/zen/go/v1 on 2026-08-27.
    ModelInfo("ox-alpha-free", "opencode_go", "Ox Alpha Free (Unlimited)", "other", 1000000, 65536, True, True,
              0.00000000, 0.00000000, "Included in the plan", "No metered cost; check the plan's rate limits before selling it."),
    ModelInfo("hy3", "opencode_go", "Hy3 (8x usage)", "Hy", 256000, 64000, True, False,
              0.00001750, 0.00007250, "Cheapest", "Best price for high-volume customer chat."),
    ModelInfo("glm-5.3-flash", "opencode_go", "GLM-5.3-Flash (2x usage)", "glm", 1000000, 65536, True, True,
              0.00007500, 0.00025000, "Cheapest", "Best price for high-volume customer chat."),
    ModelInfo("muse-spark-1.2-contributor", "opencode_go", "Muse Spark 1.2 Contributor", "muse", 1048576, 65536, True, True,
              0.00010000, 0.00020000, "Cheapest", "Best price for high-volume customer chat."),
    ModelInfo("mimo-v2.5", "opencode_go", "MiMo V2.5", "mimo-v2.5", 1000000, 65536, True, True,
              0.00014000, 0.00028000, "Economical", "Good balance of price and quality."),
    ModelInfo("qwen3.5-plus", "opencode_go", "Qwen3.5 Plus", "qwen3.5", 262144, 65536, True, True,
              0.00020000, 0.00120000, "Economical", "Good balance of price and quality."),
    ModelInfo("gpt-5.6-luna", "opencode_go", "GPT-5.6 Luna", "gpt-luna", 1050000, 65536, True, True,
              0.00020000, 0.00120000, "Economical", "Good balance of price and quality."),
    ModelInfo("deepseek-v4-flash", "opencode_go", "DeepSeek V4 Flash", "deepseek-flash", 1000000, 65536, True, False,
              0.00022000, 0.00066000, "Economical", "Good balance of price and quality."),
    ModelInfo("deepseek-v4-flash-vision-exp", "opencode_go", "DeepSeek V4 Flash Vision Exp", "deepseek-flash", 1000000, 65536, True, True,
              0.00022000, 0.00066000, "Economical", "Good balance of price and quality."),
    ModelInfo("minimax-m3", "opencode_go", "MiniMax-M3", "minimax-m3", 1000000, 65536, True, True,
              0.00030000, 0.00120000, "Economical", "Good balance of price and quality."),
    ModelInfo("minimax-m2.7", "opencode_go", "MiniMax-M2.7", "minimax-m2.7", 204800, 65536, True, False,
              0.00030000, 0.00120000, "Economical", "Good balance of price and quality."),
    ModelInfo("minimax-m2.5", "opencode_go", "MiniMax-M2.5", "minimax-m2.5", 204800, 65536, True, False,
              0.00030000, 0.00120000, "Economical", "Good balance of price and quality."),
    ModelInfo("longcat-2.0", "opencode_go", "LongCat-2.0", "longcat", 1000000, 65536, True, False,
              0.00030000, 0.00120000, "Economical", "Good balance of price and quality."),
    ModelInfo("qwen3.7-plus", "opencode_go", "Qwen3.7 Plus", "qwen3.7-plus", 1000000, 65536, True, True,
              0.00040000, 0.00160000, "Economical", "Good balance of price and quality."),
    ModelInfo("mimo-v2-omni", "opencode_go", "MiMo V2 Omni", "mimo-v2-omni", 262144, 65536, True, True,
              0.00040000, 0.00200000, "Economical", "Good balance of price and quality."),
    ModelInfo("mimo-v2.5-pro", "opencode_go", "MiMo V2.5 Pro", "mimo-v2.5-pro", 1048576, 65536, True, False,
              0.00043500, 0.00087000, "Economical", "Good balance of price and quality."),
    ModelInfo("qwen3.6-plus", "opencode_go", "Qwen3.6 Plus", "qwen3.6", 1000000, 65536, True, True,
              0.00050000, 0.00300000, "Economical", "Good balance of price and quality."),
    ModelInfo("kimi-k2.5", "opencode_go", "Kimi K2.5", "kimi-k2", 262144, 65536, True, True,
              0.00060000, 0.00300000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("deepseek-v4-pro", "opencode_go", "DeepSeek V4 Pro (New)", "deepseek-thinking", 1000000, 65536, True, False,
              0.00066000, 0.00198000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("kimi-k2.7-code", "opencode_go", "Kimi K2.7 Code", "kimi-k2", 262144, 65536, True, True,
              0.00095000, 0.00400000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("kimi-k2.6", "opencode_go", "Kimi K2.6", "kimi-k2", 262144, 65536, True, True,
              0.00095000, 0.00400000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("mimo-v2-pro", "opencode_go", "MiMo V2 Pro", "mimo-v2-pro", 1048576, 65536, True, False,
              0.00100000, 0.00300000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("glm-5", "opencode_go", "GLM-5", "glm", 202752, 32768, True, False,
              0.00100000, 0.00320000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("glm-5.3", "opencode_go", "GLM-5.3", "glm", 1000000, 65536, True, False,
              0.00140000, 0.00440000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("glm-5.2", "opencode_go", "GLM-5.2", "glm", 1000000, 65536, True, False,
              0.00140000, 0.00440000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("glm-5.1", "opencode_go", "GLM-5.1", "glm", 202752, 32768, True, False,
              0.00140000, 0.00440000, "Balanced", "More capability when the cheap tier falls short."),
    ModelInfo("grok-4.6", "opencode_go", "Grok 4.6", "grok", 500000, 65536, True, True,
              0.00200000, 0.00600000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("grok-4.5", "opencode_go", "Grok 4.5", "grok", 500000, 65536, True, True,
              0.00200000, 0.00600000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("qwen3.8-max", "opencode_go", "Qwen3.8 Max", "qwen3.8-max", 1000000, 65536, True, True,
              0.00200000, 0.00600000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("qwen3.7-max", "opencode_go", "Qwen3.7 Max", "qwen3.7-max", 1000000, 65536, True, False,
              0.00250000, 0.00750000, "Top capability", "Only where quality justifies the cost."),
    ModelInfo("kimi-k3", "opencode_go", "Kimi K3", "kimi-k3", 1048576, 65536, True, True,
              0.00300000, 0.01500000, "Top capability", "Only where quality justifies the cost."),
)

_BY_ID: dict[str, ModelInfo] = {model.id: model for model in _MODELS}


def list_models() -> list[ModelInfo]:
    """All catalog models, in declaration order."""
    return list(_MODELS)


def get_model(model_id: str) -> ModelInfo | None:
    """Metadata for a model by its ID, or None if not in the catalog."""
    return _BY_ID.get(model_id)


def estimate_tokens(text: str) -> int:
    """Quick token estimate (~4 characters per token)."""
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN
