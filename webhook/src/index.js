/**
 * Cloudflare Worker: receives Telegram webhook updates and, when the
 * authorized chat sends a trigger command, dispatches the job-alert-bot
 * GitHub Actions workflow via the GitHub API.
 *
 * Required secrets (set with `wrangler secret put <NAME>`):
 *   TELEGRAM_BOT_TOKEN   - the bot's token from BotFather
 *   TELEGRAM_SECRET_TOKEN - random string, must match Telegram's setWebhook secret_token
 *   ALLOWED_CHAT_ID      - your Telegram chat id (only this chat can trigger runs)
 *   GITHUB_TOKEN         - fine-grained PAT scoped to this repo, Actions: read/write
 *
 * Required vars (set in wrangler.toml [vars]):
 *   GITHUB_REPO          - "owner/repo"
 *   WORKFLOW_FILE        - e.g. "check.yml"
 */

const TRIGGER_COMMANDS = new Set(["/run", "/check", "/爬"]);

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("OK");
    }

    // Reject anything that didn't come from Telegram itself.
    const secretHeader = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (secretHeader !== env.TELEGRAM_SECRET_TOKEN) {
      return new Response("Forbidden", { status: 403 });
    }

    let update;
    try {
      update = await request.json();
    } catch {
      return new Response("OK");
    }

    const message = update.message;
    const text = message?.text?.trim().toLowerCase();
    const chatId = message?.chat?.id ? String(message.chat.id) : null;

    if (!chatId || chatId !== env.ALLOWED_CHAT_ID || !text) {
      return new Response("OK");
    }

    if (!TRIGGER_COMMANDS.has(text)) {
      return new Response("OK");
    }

    const dispatchResp = await fetch(
      `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/${env.WORKFLOW_FILE}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json",
          "User-Agent": "job-alert-bot-webhook",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ref: "main" }),
      }
    );

    const replyText = dispatchResp.ok
      ? "✅ 收到,已觸發抓取,跑完會再通知你"
      : `⚠️ 觸發失敗 (HTTP ${dispatchResp.status})`;

    await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text: replyText }),
    });

    return new Response("OK");
  },
};
