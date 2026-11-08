# VideoFinderX Telegram Bot

Public photo/video upload and temporary sharing bot.

## What it does

- Any Telegram user can upload a photo or video.
- The bot copies the original media into your private Telegram storage channel.
- The bot creates a permanent deep link: `https://t.me/BOT_USERNAME?start=TOKEN`.
- Anyone who opens the link in Telegram receives a protected copy.
- The delivered copy is scheduled for deletion after 60 seconds.
- PostgreSQL stores the media-to-channel-message mapping and pending deletions, so links survive worker restarts.

**Important:** The original in the storage channel is not deleted. Only the copy sent to the recipient is deleted. A recipient can still screenshot, screen-record, or otherwise capture content; no bot can guarantee that media disappears from every device.

## Before deploying

1. In `@BotFather`, revoke the exposed old token and generate a new token.
2. Add your bot as an **Administrator** to the private `Video` channel.
3. Give it permission to post messages.
4. Find the channel's numeric chat ID. For a channel, it normally has this form: `-100...`. Do not guess it; verify it.
5. Create a PostgreSQL database. Use its **Internal Database URL** if the database and worker are on Render.
6. Do not put real tokens/passwords in GitHub.

## Deploy on Render

1. Push these files to a GitHub repository.
2. In Render, choose **New + → Blueprint** and select the repository, or create a Background Worker manually.
3. Create a PostgreSQL database in Render (or use a compatible PostgreSQL provider).
4. Set these Environment Variables on the worker:
   - `BOT_TOKEN`: your newly generated BotFather token
   - `CHANNEL_ID`: verified channel ID, usually starting with `-100`
   - `DATABASE_URL`: PostgreSQL connection URL
   - `DELETE_AFTER_SECONDS`: `60`
5. Deploy. Check the worker logs for `Starting @videofinderx_bot`.

This project uses long polling and a Render Background Worker; Flask/keep-alive is not needed. A continuously running Render Background Worker generally requires a paid instance. Render free web services sleep and are not suitable for reliable 24/7 polling.

## How users use it

- Send a photo or video to the bot.
- The bot returns a share link.
- Open the link in Telegram, or paste the link into the bot chat.
- The bot sends the same stored media; that delivered message is deleted after 60 seconds.

## Notes and limits

- This initial version supports Telegram photo and video messages (not documents, albums, audio, or arbitrary files).
- Users must start the bot before the bot can send them a private message.
- The private storage channel must remain accessible to the bot, and stored channel messages must not be manually deleted.
- Telegram's Bot API has platform limits on file size and message deletion. Deletion is best-effort if Telegram rejects a delete request.
- Links are bearer links: anyone who has the link can access the media. Do not share sensitive/private content.
- Add moderation, upload quotas, and abuse controls before making the bot widely public.
