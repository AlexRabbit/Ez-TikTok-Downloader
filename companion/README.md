# TikTok_Rabbit companion (v1.5.0)

This folder contains **TikTok_Rabbit.js v1.5.0** — the browser userscript that shares cache format with Ez-TikTok-Downloader.

Install from: [AlexRabbit/Userscripts](https://github.com/AlexRabbit/Userscripts)

If the main Userscripts repo is not yet updated, copy `TikTok_Rabbit.js` from this folder into your Userscripts fork or paste into Tampermonkey.

## v1.5.0 changes

- Export / Import cache buttons (schema v1, compatible with `python tt.py --import-cache`)
- Filename format: `YY-mm-dd - ProfileUniqueID - Username - VideoID`
- `content_type` in cache entries

See [CACHE_SPEC.md](../CACHE_SPEC.md) in the project root.
