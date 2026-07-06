# Telegram → 即時觸發

讓你在 Telegram 傳 `/run`(或 `/check`、`/爬`)給機器人,就立刻觸發 GitHub Actions 跑一次抓取,不用等每天的排程。

架構:Telegram 收到訊息 → 呼叫這個 Cloudflare Worker(webhook)→ Worker 呼叫 GitHub API 觸發 workflow → workflow 照平常流程跑完發 Telegram 通知。

## 設定步驟(一次性)

### 1. 安裝 wrangler 並登入 Cloudflare(免費帳號)

```bash
cd webhook
npx wrangler login
```

會開瀏覽器讓你登入/註冊 Cloudflare,授權後回到終端機即可。

### 2. 建立 GitHub Personal Access Token

去 https://github.com/settings/personal-access-tokens/new 建立一個 **fine-grained token**:

- Repository access:只選這個 repo(`coldpizzayum/jobjager`)
- Permissions → Actions:設為 **Read and write**
- 建立後複製 token(只會顯示一次)

### 3. 部署 Worker

```bash
npx wrangler deploy
```

部署完成後終端機會印出網址,長得像:
`https://job-alert-bot-webhook.<你的subdomain>.workers.dev`

先記下這個網址,下一步會用到。

### 4. 設定 Secrets

```bash
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put GITHUB_TOKEN
npx wrangler secret put ALLOWED_CHAT_ID
npx wrangler secret put TELEGRAM_SECRET_TOKEN
```

依序貼上對應的值:

| Secret | 值 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | 跟 GitHub Actions 用的同一組(BotFather 給的) |
| `GITHUB_TOKEN` | 步驟 2 建立的 PAT |
| `ALLOWED_CHAT_ID` | 你的 Telegram chat_id(同 GitHub Secrets 裡的 `TELEGRAM_CHAT_ID`) |
| `TELEGRAM_SECRET_TOKEN` | 自己隨便設一組隨機字串(例如用 `openssl rand -hex 20` 產生),用來驗證請求真的來自 Telegram,不是別人亂打你的 webhook |

### 5. 把 Webhook 註冊給 Telegram

用步驟 3 拿到的網址、步驟 4 設的 `TELEGRAM_SECRET_TOKEN`,執行(把 `<BOT_TOKEN>`、`<WORKER_URL>`、`<SECRET>` 換成實際值):

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -d "url=<WORKER_URL>" \
  -d "secret_token=<SECRET>"
```

回傳 `{"ok":true,...}` 就代表設定成功。

## 測試

跟你的 Telegram 機器人傳 `/run`,應該幾秒內收到「✅ 收到,已觸發抓取」,接著等 GitHub Actions 跑完(通常 1-2 分鐘)就會收到職缺結果。

## 之後要改動 Worker 程式碼

改完 `src/index.js` 後,在 `webhook/` 目錄下重新 `npx wrangler deploy` 即可,不需要重新設定 secrets 或 webhook。
