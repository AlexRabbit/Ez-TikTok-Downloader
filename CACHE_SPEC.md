# Shared Cache Format — Ez-TikTok-Downloader + TikTok_Rabbit

Cross-tool cache spec by **AlexRabbit** for [Ez-TikTok-Downloader](https://github.com/AlexRabbit/Ez-TikTok-Downloader) and [TikTok_Rabbit userscript](https://github.com/AlexRabbit/Userscripts).

## Schema version 1

Desktop app writes `link_cache.json`:

```json
{
  "schema_version": 1,
  "updated_at": "2026-08-27T12:00:00Z",
  "app": "ez-tiktok-downloader",
  "entries": {
    "7668119571810766098": {
      "play_url": "https://...",
      "images": [],
      "username": "masanher",
      "video_id": "7668119571810766098",
      "create_time": 1720000000,
      "profile_uid": "265992760451776512",
      "content_type": "video"
    }
  }
}
```

## Entry fields

| Field | Required | Description |
|-------|----------|-------------|
| `play_url` | One of play_url/images | Direct CDN URL for video |
| `images` | One of play_url/images | List of image URLs (slideshows) |
| `username` | Recommended | TikTok @handle |
| `video_id` | Recommended | Post/media ID |
| `create_time` | Optional | Unix timestamp (UTC) |
| `profile_uid` | Optional | Numeric user ID |
| `content_type` | Optional | `video`, `photo`, `story`, `highlight` |

Cache hit rule: entry is usable if `play_url` is set OR `images` is a non-empty array.

## Browser storage (TikTok_Rabbit)

The userscript stores a **flat map** in `localStorage['tiktok_rabbit_cache']`:

```json
{
  "7668119571810766098": { "...same entry fields..." }
}
```

Export from the userscript produces schema v1 with an `entries` wrapper.

## Sync workflows

### Browser → Desktop

1. In TikTok (with TikTok_Rabbit): use **Export cache** from the menu
2. Save the downloaded JSON file
3. Run: `python tt.py --import-cache export.json --merge`

### Desktop → Browser

1. Run: `python tt.py --export-cache`
2. In TikTok: use **Import cache** and select the exported file

## Legacy format

Older desktop versions used a flat JSON map (no `schema_version`). The desktop app auto-migrates these on load and re-saves as schema v1.

## Filename convention (both tools)

```
YY-mm-dd - ProfileUniqueID - Username - VideoID.ext
```

Example: `26-07-30 - 265992760451776512 - masanher - 7668119571810766098.mp4`

Slideshows: same base + `_img_1.jpg`, `_img_2.jpg`, etc.
