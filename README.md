# Job Alert Bot 🔔

每天自動檢查各公司 ATS 上的新職缺,過濾出設計相關 + 目標地點的職位,推播到你的 Telegram。跑在 GitHub Actions 上,不需要伺服器,完全免費。

## 運作原理

排程觸發(每天 09:00 柏林時間)→ 呼叫各家 ATS 公開 API → 職稱關鍵字 + 地點過濾 → 與 `seen.json` 比對找出新職缺 → Telegram 推播 → 更新狀態 commit 回 repo。

第一次執行會推送「初始快照」(目前所有符合條件的職缺),之後只在有新職缺時通知。某家公司抓取失敗或突然變成 0 筆時,你也會收到警告訊息,不會默默失敗。

## 設定步驟(一次性,約 10 分鐘)

### 1. 建立 Telegram Bot

1. 在 Telegram 搜尋 `@BotFather`,傳送 `/newbot`
2. 依指示取名(username 需以 `bot` 結尾)
3. 記下它給你的 **token**(格式像 `1234567890:ABCdef...`)

### 2. 取得你的 chat_id

1. 先跟你的新 bot 說一句話(任何內容)
2. 瀏覽器打開:`https://api.telegram.org/bot<你的TOKEN>/getUpdates`
3. 在回傳的 JSON 裡找 `"chat":{"id": 一串數字}`,那串數字就是你的 **chat_id**

### 3. 建立 GitHub Repo 並上傳

1. 在 GitHub 建一個新的 **private** repo
2. 把這個資料夾的所有檔案推上去(包含 `.github/workflows/check.yml`)

### 4. 設定 Secrets

Repo → Settings → Secrets and variables → Actions → New repository secret,新增兩個:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather 給的 token |
| `TELEGRAM_CHAT_ID` | 步驟 2 拿到的數字 |

### 5. 驗證各公司 API(重要!)

其中幾家的 board token 是推測值,第一次請先驗證。在本機執行:

```bash
pip install -r requirements.txt
python main.py --check
```

會列出每家公司抓到幾筆職缺、哪些符合條件。如果某家顯示「抓取失敗」:

- **Greenhouse 系**:到 `boards.greenhouse.io/<猜的token>` 試開,或去公司 careers 頁按 F12 → Network 看實際請求裡的 token,改進 `companies.json`
- **歐洲版 Greenhouse**(如 Bitpanda):token 正確但 US API 失敗時,加上 `"region": "eu"`

### 6. 啟動

Repo → Actions → 啟用 workflows → 選「Job alert」→ Run workflow 手動跑第一次。收到初始快照訊息就代表成功了,之後每天早上自動執行。

## 日常調整

**加公司**:在 `companies.json` 的 `companies` 加一行。支援的 `ats` 值:`greenhouse`、`ashby`、`workable`。

**調整過濾**:改 `filters` 裡的 `title_keywords`(職稱須包含其一)、`title_exclude`(包含就排除,目前排除 engineer/developer,注意這也會擋掉 Design Engineer 這類職位)、`locations`(地點須包含其一;沒寫地點的職缺一律保留,寧可多推不漏接)。

**改執行時間**:改 `check.yml` 裡的 cron(UTC 時間,`0 7 * * *` = 柏林夏令時間 09:00)。想一天跑兩次就加一行 `- cron: "0 15 * * *"`。

**本機測試不發訊息**:`DRY_RUN=1 python main.py`

## 已知限制

- **Bunq** 用的招募平台不是這三種 ATS,要加的話先去 careers.bunq.com 按 F12 → Network 找它的職缺 JSON 來源,再告訴 Claude 幫你加 adapter
- Bitpanda 和 SIXT 官網本身就有 job alert 功能,可以直接用官方的,不一定要進機器人
- ATS 的 location 欄位格式各家不一,若發現漏抓,把該職缺的 location 原文加進 `locations` 清單
