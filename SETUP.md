# One-time setup (≈20 minutes)

Until these steps are done, scheduled runs skip quietly — nothing breaks.
**Never paste tokens into chat, issues or code.** They go only into GitHub secrets (step 3).

## 1. Facebook Page token

1. Go to <https://developers.facebook.com> → **My Apps** → **Create App**.
   - Name: `History Unsealed Publisher`
   - Use case: **Manage everything on your Page** (if not listed: **Other** → app type **Business**).
   - Connect it to the business portfolio that owns the Page (if asked).
   - The app can stay in **Development** mode — you're only posting to your own Page, so no App Review is needed.
2. Open the **Graph API Explorer**: <https://developers.facebook.com/tools/explorer>
   - Meta App: `History Unsealed Publisher`
   - User or Page: **Get Page Access Token**
   - Add permissions: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `pages_read_user_content`, `pages_manage_engagement`
   - Click **Generate Access Token**, approve, and select **History Unsealed**.
3. Make it long-lived:
   - Copy the **user** token → open the **Access Token Debugger**
     (<https://developers.facebook.com/tools/debug/accesstoken>) → **Debug** → **Extend Access Token**.
   - Back in Graph API Explorer, paste the extended user token, then run `GET me/accounts`.
   - In the result, find **History Unsealed**: copy its `id` (→ `FB_PAGE_ID`) and its `access_token` (→ `FB_PAGE_TOKEN`).
   - A Page token taken from a long-lived user token does not expire (it is revoked if you change your Facebook password or remove the app — then repeat this step).

> Alternative that survives password changes: create a **System User** in Business Settings → Users → System users, assign it the Page and the app, generate a token with the same permissions, and use `GET me/accounts` with it to get the Page token.

## 2. Cloudflare (free AI images)

1. Sign up at <https://dash.cloudflare.com/sign-up> (free plan).
2. **Account ID**: open **Workers & Pages** (or the account home) — it's in the right sidebar. → `CF_ACCOUNT_ID`
3. **API token**: profile icon → **My Profile** → **API Tokens** → **Create Token** → template **Workers AI** → Create. → `CF_API_TOKEN`

The free allowance covers this Page's ~8–10 images a day. If Cloudflare ever fails, the bot falls back to Pollinations automatically.

## 3. GitHub secrets

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Name | Value |
|---|---|
| `FB_PAGE_ID` | from step 1 |
| `FB_PAGE_TOKEN` | from step 1 |
| `CF_ACCOUNT_ID` | from step 2 |
| `CF_API_TOKEN` | from step 2 |

Optional **Variables** (same screen, Variables tab): `TTS_VOICE` (default `en-US-AndrewMultilingualNeural`), `GRAPH_VERSION` (default `v24.0`).

## 4. Test

1. **Actions** → **Check setup** → **Run workflow**. Both steps must be green; it prints which Page the token belongs to. If it warns that `FB_PAGE_ID` differs, update the secret to the id it shows.
2. **Actions** → **Publish** → **Run workflow** → slot `b`, date `2026-10-17`, **dry run ticked**. When it finishes, download the `media-…` artifact and watch the reel.
3. Happy with it? Run **Publish** once more with **dry run unticked** to post it for real. After that, everything runs on schedule.

## Notes

- **Public repo** = unlimited free Actions minutes. **Private repo** = 2,000 free minutes/month; this bot uses roughly 200–300.
- Optional background music: drop royalty-free `.mp3` files into `assets/music/` (e.g. from the YouTube Audio Library). The bot mixes one in at low volume.
- If a scheduled run fails, GitHub emails you. The rendered media of every run is kept for 7 days under the run's **Artifacts**.
