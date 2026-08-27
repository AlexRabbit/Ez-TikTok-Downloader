// ==UserScript==
// @name         TikTok_Rabbit
// @namespace    https://github.com/AlexRabbit/Userscripts
// @version      1.5.0
// @description  No-watermark TikTok download via TikWM; FYP vertical button + 4th button on video pages (Like/Comment/Save/DL).
// @author       AlexRabbit (https://github.com/AlexRabbit)
// @match        https://www.tiktok.com/*
// @match        https://m.tiktok.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_download
// @connect      tikwm.com
// @connect      www.tikwm.com
// @connect      tiktok.com
// @connect      *
// @run-at       document-idle
// @license      MIT
// @downloadURL  https://raw.githubusercontent.com/AlexRabbit/Userscripts/main/TikTok_Rabbit.js
// @updateURL    https://raw.githubusercontent.com/AlexRabbit/Userscripts/main/TikTok_Rabbit.js
// @supportURL   https://github.com/AlexRabbit/Userscripts/issues
// ==/UserScript==

(function () {
    'use strict';

    const SUBMIT_URL = 'https://tikwm.com/api/video/task/submit';
    const RESULT_BASE = 'https://tikwm.com/api/video/task/result?task_id=';
    const QUICK_API = 'https://www.tikwm.com/api/';
    const CACHE_KEY = 'tiktok_rabbit_cache';
    const SESSION_KEY = 'tiktok_rabbit_sessionid';
    const POLL_MS = 1000;
    const POLL_MAX = 60;
    const MARK = 'tiktok-rabbit-dl';

    const API_HEADERS = {
        'User-Agent': navigator.userAgent,
        Accept: 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        Origin: 'https://tikwm.com',
        Referer: 'https://tikwm.com/',
        'x-requested-with': 'XMLHttpRequest',
    };

    const COLLECT_SELECTORS = [
        '[data-e2e="browse-collect"]',
        '[data-e2e="video-collect"]',
        '[data-e2e="browse-collect-icon"]',
        '[data-e2e="video-collect-icon"]',
        '[data-e2e="browse-collection"]',
        '[data-e2e="video-collection"]',
        '[data-e2e="browse-favorite"]',
        '[data-e2e="video-favorite"]',
        '[data-e2e="undefined-icon"]',
    ];

    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

    const gmRequest = (opts) =>
        new Promise((resolve, reject) => {
            const gm =
                typeof GM_xmlhttpRequest === 'function'
                    ? GM_xmlhttpRequest
                    : typeof GM !== 'undefined' && typeof GM.xmlHttpRequest === 'function'
                      ? GM.xmlHttpRequest
                      : null;
            if (gm) {
                gm({
                    method: opts.method || 'GET',
                    url: opts.url,
                    headers: opts.headers || {},
                    data: opts.data,
                    responseType: opts.responseType,
                    onload: (r) => resolve(r),
                    onerror: (e) => reject(e),
                    ontimeout: () => reject(new Error('timeout')),
                });
                return;
            }
            const init = { method: opts.method || 'GET', headers: opts.headers || {} };
            if (opts.data) init.body = opts.data;
            fetch(opts.url, init)
                .then(async (res) => {
                    const buf =
                        opts.responseType === 'arraybuffer' ? await res.arrayBuffer() : await res.text();
                    resolve({
                        status: res.status,
                        responseText: typeof buf === 'string' ? buf : undefined,
                        response: buf,
                    });
                })
                .catch(reject);
        });

    const sanitize = (s) =>
        String(s || 'unknown')
            .replace(/[<>:"/\\|?*]/g, '_')
            .trim()
            .slice(0, 120) || 'unknown';

    const loadCache = () => {
        try {
            return JSON.parse(localStorage.getItem(CACHE_KEY) || '{}');
        } catch {
            return {};
        }
    };

    const saveCache = (cache) => {
        try {
            localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
        } catch {}
    };

    const exportCacheV1 = () => {
        const cache = loadCache();
        const wrapper = {
            schema_version: 1,
            updated_at: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
            app: 'tiktok-rabbit-userscript',
            entries: cache,
        };
        const blob = new Blob([JSON.stringify(wrapper, null, 2)], { type: 'application/json' });
        saveBlob(blob, 'link_cache.json');
        toast('Cache exported (schema v1 — Ez-TikTok compatible)');
    };

    const importCacheV1 = () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json,application/json';
        input.onchange = async () => {
            const file = input.files?.[0];
            if (!file) return;
            try {
                const text = await file.text();
                const data = JSON.parse(text);
                const incoming = data.schema_version && data.entries ? data.entries : data;
                const cache = loadCache();
                let count = 0;
                for (const [k, v] of Object.entries(incoming)) {
                    if (v && typeof v === 'object' && (v.play_url || (v.images && v.images.length))) {
                        cache[k] = v;
                        count++;
                    }
                }
                saveCache(cache);
                toast(`Imported ${count} cache entries`);
            } catch {
                toast('Cache import failed', true);
            }
        };
        input.click();
    };

    const contentTypeFromUrl = (url) => {
        if (/\/photo\//.test(url)) return 'photo';
        if (/\/story/.test(url)) return 'story';
        if (/highlight/.test(url)) return 'highlight';
        return 'video';
    };

    const getSessionId = () => {
        try {
            let v = (localStorage.getItem(SESSION_KEY) || '').trim();
            if (!v) return null;
            if (v.toLowerCase().startsWith('sessionid=')) v = v.slice(10).trim();
            return v || null;
        } catch {
            return null;
        }
    };

    const apiHeaders = () => {
        const h = { ...API_HEADERS };
        const sid = getSessionId();
        if (sid) {
            h.Referer = `https://www.tikwm.com/originalDownloader.html?cookie=sessionid=${sid}`;
            h['x-proxy-cookie'] = `sessionid=${sid}`;
        }
        return h;
    };

    const normalizeUrl = (url) => {
        let u = (url || location.href).trim();
        if (u.includes('#')) u = u.split('#')[0];
        if (u.includes('?')) u = u.split('?')[0];
        u = u.replace(/\/+$/, '');
        if (u.startsWith('http://')) u = 'https://' + u.slice(7);
        if (u.startsWith('/')) u = 'https://www.tiktok.com' + u;
        return u;
    };

    const extractMediaId = (url) => {
        const m = url.match(/\/(?:video|photo)\/(\d+)/);
        return m ? m[1] : null;
    };

    const extractUsername = (url) => {
        const m = url.match(/tiktok\.com\/@([\w.-]+)/i);
        return m ? m[1] : null;
    };

    const urlCandidates = (tiktokUrl) => {
        const normalized = normalizeUrl(tiktokUrl);
        const id = extractMediaId(normalized);
        const list = [normalized];
        if (id) {
            for (const u of [
                id,
                `https://www.tiktok.com/video/${id}`,
                `https://www.tiktok.com/@tiktok/video/${id}`,
                `https://m.tiktok.com/v/${id}.html`,
            ]) {
                if (!list.includes(u)) list.push(u);
            }
        }
        return list;
    };

    const buildDateStr = (createTime) => {
        if (createTime != null) {
            try {
                const d = new Date(Number(createTime) * 1000);
                return `${String(d.getUTCFullYear()).slice(-2)}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
            } catch {}
        }
        const n = new Date();
        return `${String(n.getUTCFullYear()).slice(-2)}-${String(n.getUTCMonth() + 1).padStart(2, '0')}-${String(n.getUTCDate()).padStart(2, '0')}`;
    };

    const buildFilename = (entry, ext) => {
        const username = sanitize(entry.username);
        const dateStr = buildDateStr(entry.create_time);
        const profileUid = sanitize(entry.profile_uid || 'unknown');
        const videoId = sanitize(entry.video_id || 'unknown');
        return `${dateStr} - ${profileUid} - ${username} - ${videoId}${ext}`;
    };

    const parseUniversalInText = (text) => {
        try {
            const data = JSON.parse(text);
            const scope = data?.__DEFAULT_SCOPE__ || {};
            for (const key of Object.keys(scope)) {
                const item =
                    scope[key]?.itemInfo?.itemStruct ||
                    scope[key]?.itemStruct ||
                    scope[key]?.videoDetail?.itemInfo?.itemStruct;
                if (!item?.id) continue;
                const user = item.author?.uniqueId || item.author?.unique_id || 'user';
                const kind = item.imagePost || /photo/.test(location.pathname) ? 'photo' : 'video';
                return normalizeUrl(`https://www.tiktok.com/@${user}/${kind}/${item.id}`);
            }
        } catch {}
        return null;
    };

    const parseUniversalData = () => {
        const el = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
        if (!el?.textContent) return null;
        try {
            const data = JSON.parse(el.textContent);
            const detail = data?.__DEFAULT_SCOPE__?.['webapp.video-detail']?.itemInfo?.itemStruct;
            if (detail?.id) {
                const user = detail.author?.uniqueId || detail.author?.unique_id || 'user';
                const kind = detail.imagePost ? 'photo' : 'video';
                return normalizeUrl(`https://www.tiktok.com/@${user}/${kind}/${detail.id}`);
            }
        } catch {}
        return parseUniversalInText(el.textContent);
    };

    const urlFromLocation = () => {
        if (/\/(video|photo)\/\d+/.test(location.pathname)) {
            return normalizeUrl(location.href);
        }
        const canonical = document.querySelector('link[rel="canonical"]')?.href;
        if (canonical && /\/(video|photo)\/\d+/.test(canonical)) {
            return normalizeUrl(canonical);
        }
        return null;
    };

    const resolveVideoUrl = (root) => {
        const onVideoPage = urlFromLocation();
        if (onVideoPage) return onVideoPage;

        const containerSelectors = [
            '[data-e2e="recommend-list-item-container"]',
            '[data-e2e="one-column-item"]',
            '[data-e2e="search-card-video-container"]',
            '[data-e2e="user-post-item"]',
            '[data-e2e="browse-video"]',
            '[data-e2e="video-detail"]',
        ];

        let scope = null;
        if (root && root.nodeType === 1) {
            for (const sel of containerSelectors) {
                const hit = root.closest?.(sel);
                if (hit) {
                    scope = hit;
                    break;
                }
            }
            if (!scope) {
                scope =
                    root.closest?.('[data-e2e="video-player"]') ||
                    root.closest?.('section') ||
                    root.closest?.('article') ||
                    root;
            }
        }

        if (scope && scope !== document) {
            const link = scope.querySelector?.('a[href*="/video/"], a[href*="/photo/"]');
            if (link) {
                const href = link.href || link.getAttribute('href') || '';
                if (href) return normalizeUrl(href);
            }
            const vid = scope.querySelector?.('video');
            if (vid) {
                let walk = vid.parentElement;
                for (let i = 0; i < 12 && walk; i++) {
                    const a = walk.querySelector?.(':scope a[href*="/video/"], :scope a[href*="/photo/"]');
                    if (a?.href) return normalizeUrl(a.href);
                    walk = walk.parentElement;
                }
            }
        }

        return parseUniversalData() || urlFromLocation();
    };

    const parseTikwmEntry = (j, usernameFromUrl, videoIdFromUrl) => {
        const data = j?.data;
        if (!data) return null;
        if (data.play || data.hdplay || data.wmplay) {
            return {
                play_url: data.hdplay || data.play || data.wmplay,
                images: data.images || [],
                username: sanitize(data.author?.unique_id || data.author?.uniqueId || usernameFromUrl),
                video_id: String(data.id || videoIdFromUrl || 'unknown'),
                create_time: data.create_time,
                profile_uid: data.author?.id != null ? String(data.author.id) : 'unknown',
            };
        }
        const detail = data.detail || data;
        const playUrl = detail.play_url || detail.url || detail.play || detail.hdplay;
        const images = detail.images || data.images || [];
        const author = detail.author || data.author || {};
        if (!playUrl && !(images && images.length)) return null;
        let vid = detail.video_id || data.video_id || videoIdFromUrl || 'unknown';
        if (typeof vid === 'number') vid = String(vid);
        return {
            play_url: playUrl,
            images: Array.isArray(images) ? images : [],
            username: sanitize(author.unique_id || author.nickname || usernameFromUrl),
            video_id: vid,
            create_time: detail.create_time ?? detail.createTime ?? data.create_time,
            profile_uid:
                author.id != null ? String(author.id) : author.uid != null ? String(author.uid) : 'unknown',
        };
    };

    const submitTikwmQuick = async (tiktokUrl) => {
        const headers = apiHeaders();
        for (const candidate of urlCandidates(tiktokUrl)) {
            try {
                const url = `${QUICK_API}?url=${encodeURIComponent(candidate)}&hd=1`;
                const r = await gmRequest({ method: 'GET', url, headers });
                if (r.status !== 200) continue;
                const j = JSON.parse(r.responseText);
                if (j?.code !== 0) continue;
                const entry = parseTikwmEntry(j, extractUsername(tiktokUrl), extractMediaId(tiktokUrl));
                if (entry) return entry;
            } catch (e) {
                console.debug('[TikTok_Rabbit] quick api', e);
            }
        }
        return null;
    };

    const submitTikwmTask = async (tiktokUrl) => {
        const usernameFromUrl = extractUsername(tiktokUrl) || 'unknown';
        const videoIdFromUrl = extractMediaId(tiktokUrl);
        const headers = apiHeaders();

        for (const candidate of urlCandidates(tiktokUrl)) {
            try {
                const body = `web=1&url=${encodeURIComponent(candidate)}`;
                const r = await gmRequest({ method: 'POST', url: SUBMIT_URL, headers, data: body });
                if (r.status !== 200) continue;
                const j = JSON.parse(r.responseText);
                const taskId = j?.data?.task_id;
                if (j?.code !== 0 || !taskId) continue;

                for (let i = 0; i < POLL_MAX; i++) {
                    await sleep(POLL_MS);
                    const poll = await gmRequest({
                        method: 'GET',
                        url: RESULT_BASE + taskId,
                        headers,
                    });
                    if (poll.status !== 200) continue;
                    const j2 = JSON.parse(poll.responseText);
                    if (j2?.code !== 0 || !j2?.data) continue;
                    const data = j2.data;
                    if (data.status === 3) break;
                    if (data.status !== 2) continue;
                    const entry = parseTikwmEntry(
                        { data: { ...data, detail: data.detail || data } },
                        usernameFromUrl,
                        videoIdFromUrl
                    );
                    if (entry) return entry;
                }
            } catch (e) {
                console.debug('[TikTok_Rabbit] task api', e);
            }
        }
        return null;
    };

    const fetchEntry = async (url) => {
        const cache = loadCache();
        const videoId = extractMediaId(url) || 'unknown';
        const cached = cache[videoId];
        if (cached && (cached.play_url || (cached.images && cached.images.length))) {
            return { ...cached, video_id: cached.video_id || videoId };
        }
        let result = await submitTikwmQuick(url);
        if (!result) result = await submitTikwmTask(url);
        if (!result) return null;
        result.content_type = contentTypeFromUrl(url);
        cache[videoId] = result;
        saveCache(cache);
        return result;
    };

    const saveBlob = (blob, filename) => {
        const blobUrl = URL.createObjectURL(blob);
        if (typeof GM_download === 'function') {
            GM_download({
                url: blobUrl,
                name: filename,
                onload: () => URL.revokeObjectURL(blobUrl),
                onerror: () => URL.revokeObjectURL(blobUrl),
            });
            return;
        }
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(blobUrl), 8000);
    };

    const triggerDownload = async (url, filename) => {
        const r = await gmRequest({
            method: 'GET',
            url: url.startsWith('//') ? 'https:' + url : url,
            headers: { Referer: 'https://www.tiktok.com/', Origin: 'https://www.tiktok.com' },
            responseType: 'arraybuffer',
        });
        if (r.status !== 200) throw new Error('HTTP ' + r.status);
        const blob = new Blob([r.response], { type: 'video/mp4' });
        saveBlob(blob, filename);
    };

    const downloadEntry = async (entry, pageUrl) => {
        const images = entry.images || [];
        const playUrl = entry.play_url;
        const isPhoto = /\/photo\//.test(pageUrl);

        if (images.length && (!playUrl || isPhoto)) {
            const base = buildFilename(entry, '');
            let ok = 0;
            for (let i = 0; i < images.length; i++) {
                const item = images[i];
                const imgUrl =
                    typeof item === 'string' ? item : item?.url || item?.image_url || '';
                if (!imgUrl) continue;
                let ext = '.jpg';
                const pathPart = imgUrl.split('?')[0];
                if (pathPart.includes('.')) {
                    const e = '.' + pathPart.split('.').pop().toLowerCase();
                    if (['.jpg', '.jpeg', '.png', '.webp'].includes(e)) ext = e;
                }
                await triggerDownload(imgUrl, `${base}_img_${i + 1}${ext}`);
                ok++;
            }
            return ok > 0;
        }

        if (!playUrl) return false;
        await triggerDownload(playUrl, buildFilename(entry, '.mp4'));
        return true;
    };

    let busy = false;

    const toast = (msg, err) => {
        const box = document.createElement('div');
        box.textContent = msg;
        Object.assign(box.style, {
            position: 'fixed',
            top: '72px',
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: '2147483647',
            background: err ? '#b00020' : '#fe2c55',
            color: '#fff',
            padding: '12px 20px',
            borderRadius: '8px',
            fontWeight: '600',
            fontSize: '14px',
            fontFamily: 'system-ui,sans-serif',
            boxShadow: '0 4px 16px rgba(0,0,0,.35)',
            pointerEvents: 'none',
        });
        document.body.appendChild(box);
        setTimeout(() => box.remove(), 2800);
    };

    const runDownload = async (triggerEl) => {
        if (busy) return;
        busy = true;
        toast('Preparing download…');
        try {
            const wrap =
                triggerEl?.closest?.('[data-tiktok-rabbit-dl]') ||
                (triggerEl?.hasAttribute?.('data-tiktok-rabbit-dl') ? triggerEl : null);
            let pageUrl =
                wrap?.getAttribute('data-video-url') ||
                triggerEl?.getAttribute?.('data-video-url') ||
                resolveVideoUrl(triggerEl) ||
                urlFromLocation() ||
                parseUniversalData();
            if (pageUrl && !extractMediaId(pageUrl) && /^\d{10,}$/.test(pageUrl)) {
                pageUrl = `https://www.tiktok.com/video/${pageUrl}`;
            }
            if (!pageUrl || !extractMediaId(pageUrl)) {
                toast('Video URL not found for this item', true);
                return;
            }
            const entry = await fetchEntry(pageUrl);
            if (!entry) {
                toast('TikWM failed — check console or set session ID', true);
                return;
            }
            await downloadEntry(entry, pageUrl);
            toast('Download started');
        } catch (e) {
            console.error('[TikTok_Rabbit]', e);
            toast('Download failed — see console', true);
        } finally {
            busy = false;
        }
    };

    const downloadSvg = (px) => {
        const ns = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(ns, 'svg');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('width', String(px));
        svg.setAttribute('height', String(px));
        svg.setAttribute('fill', 'currentColor');
        const p = document.createElementNS(ns, 'path');
        p.setAttribute('d', 'M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z');
        svg.appendChild(p);
        return svg;
    };

    const getCollectControl = (el) => {
        if (!el) return null;
        if (el.tagName === 'BUTTON' || el.getAttribute('role') === 'button') return el;
        return el.querySelector('button, [role="button"]') || el;
    };

    const isBookmarkNode = (el) => {
        if (!el) return false;
        const e2e = el.getAttribute('data-e2e') || el.closest('[data-e2e]')?.getAttribute('data-e2e') || '';
        if (/collect|bookmark|favorite/i.test(e2e)) return true;
        const control = getCollectControl(el);
        const label = (control?.getAttribute('aria-label') || '').toLowerCase();
        return (
            label.includes('favorite') ||
            label.includes('favourite') ||
            label.includes('bookmark') ||
            label.includes('add to favorites')
        );
    };

    const getActionItem = (control) => {
        let item = control;
        for (let i = 0; i < 14 && item; i++) {
            const parent = item.parentElement;
            if (!parent) break;
            const peers = [...parent.children].filter(
                (c) =>
                    c.querySelector?.('button, [role="button"]') ||
                    c.tagName === 'BUTTON' ||
                    c.getAttribute?.('role') === 'button'
            );
            if (peers.length >= 2 && peers.includes(item)) return item;
            const pe2e = parent.getAttribute?.('data-e2e') || '';
            if (/actions|action-bar/i.test(pe2e)) return item;
            item = parent;
        }
        return control.parentElement || control;
    };

    const measureBtnSize = (refControl) => {
        const refBtn =
            refControl?.tagName === 'BUTTON' || refControl?.getAttribute?.('role') === 'button'
                ? refControl
                : refControl?.querySelector?.('button, [role="button"]') || refControl;
        let size = 48;
        try {
            const r = refBtn?.getBoundingClientRect?.();
            if (r?.width >= 28) size = Math.round(r.width);
        } catch {}
        return Math.max(48, Math.min(size, 56));
    };

    const isVideoDetailPage = () => /\/@[\w.-]+\/(video|photo)\/\d+/.test(location.pathname);

    const isHorizontalActionRow = (row) => {
        if (!row?.children?.length) return false;
        if (isVideoDetailPage()) return true;
        const kids = [...row.children].filter((c) => !c.hasAttribute('data-tiktok-rabbit-dl'));
        if (kids.length < 2) return false;
        const a = kids[0].getBoundingClientRect();
        const b = kids[1].getBoundingClientRect();
        return Math.abs(a.top - b.top) < 24 && b.left > a.left + 8;
    };

    const wireDownloadClick = (block) => {
        const click = (e) => {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            runDownload(block);
        };
        block.querySelectorAll('button, [role="button"]').forEach((el) => {
            el.addEventListener('click', click, true);
        });
    };

    const buildDownloadBlockVertical = (refControl, videoUrl) => {
        const size = measureBtnSize(refControl);
        const block = document.createElement('motion-button');
        block.setAttribute('data-tiktok-rabbit-dl', '1');
        block.setAttribute('data-video-url', videoUrl || urlFromLocation() || '');
        block.className = 'tiktok-rabbit-dl-wrap tiktok-rabbit-dl-vertical';

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.setAttribute('aria-label', 'Download video');
        btn.setAttribute('title', 'Download without watermark');
        btn.appendChild(downloadSvg(Math.round(size * 0.5)));

        const label = document.createElement('strong');
        label.textContent = 'Save';
        label.setAttribute('data-e2e', 'rabbit-download-count');
        block.append(btn, label);
        wireDownloadClick(block);
        return block;
    };

    const buildDownloadBlockHorizontal = (templateItem, videoUrl) => {
        const block = templateItem.cloneNode(true);
        block.setAttribute('data-tiktok-rabbit-dl', '1');
        block.setAttribute('data-video-url', videoUrl || urlFromLocation() || '');
        block.classList.add('tiktok-rabbit-dl-wrap', 'tiktok-rabbit-dl-inline');

        const btn = block.querySelector('button, [role="button"]');
        if (btn) {
            const fresh = btn.cloneNode(false);
            fresh.type = 'button';
            fresh.setAttribute('aria-label', 'Download video');
            fresh.setAttribute('title', 'Download without watermark');
            fresh.appendChild(downloadSvg(22));
            btn.replaceWith(fresh);
        }

        block.querySelectorAll('strong, span, p').forEach((el) => {
            const t = (el.textContent || '').trim();
            if (/^[\d,.]+[KMB]?$/i.test(t) || /^\d+$/.test(t)) {
                el.textContent = 'DL';
            }
        });

        wireDownloadClick(block);
        return block;
    };

    const findBookmarkNodes = () => {
        const found = new Set();
        for (const sel of COLLECT_SELECTORS) {
            document.querySelectorAll(sel).forEach((el) => found.add(el));
        }
        document.querySelectorAll('[data-e2e]').forEach((el) => {
            const e2e = el.getAttribute('data-e2e') || '';
            if (/collect|bookmark/i.test(e2e)) found.add(el);
        });
        document.querySelectorAll('button, [role="button"]').forEach((el) => {
            if (isBookmarkNode(el)) found.add(el);
        });
        return [...found];
    };

    const findBookmarkActionItem = () => {
        for (const node of findBookmarkNodes()) {
            const control = getCollectControl(node);
            if (!control) continue;
            return getActionItem(control);
        }
        const likeItem = document.querySelector(
            '[data-e2e="browse-like-icon"], [data-e2e="video-like-icon"], [data-e2e="like-icon"]'
        );
        if (likeItem) {
            const item = getActionItem(getCollectControl(likeItem) || likeItem);
            const row = item?.parentElement;
            if (row) {
                const kids = [...row.children];
                const collect = kids.find((c) => isBookmarkNode(c));
                if (collect) return getActionItem(getCollectControl(collect));
            }
        }
        return null;
    };

    const findVideoDetailActionRow = () => {
        let bookmarkItem = findBookmarkActionItem();
        if (bookmarkItem) return bookmarkItem;

        const collect = document.querySelector(
            '[data-e2e="video-collect-icon"], [data-e2e="browse-collect-icon"], [data-e2e="video-collect"], [data-e2e="browse-collect"]'
        );
        if (collect) return getActionItem(getCollectControl(collect) || collect);

        const candidates = document.querySelectorAll(
            '[class*="ActionBar"], [data-e2e*="comment-avatar"], section div'
        );
        for (const row of candidates) {
            const hasLike = row.querySelector('[data-e2e*="like"]');
            const hasComment = row.querySelector('[data-e2e*="comment"]');
            const hasCollect = row.querySelector('[data-e2e*="collect"], [aria-label*="Favorite" i]');
            if (!hasLike || !hasComment || !hasCollect) continue;
            const item = getActionItem(getCollectControl(hasCollect) || hasCollect);
            if (item) return item;
        }
        return null;
    };

    const injectVideoDetailRow = () => {
        if (!isVideoDetailPage()) return;
        if (document.querySelector('.tiktok-rabbit-dl-inline')) return;

        const bookmarkItem = findVideoDetailActionRow();
        if (!bookmarkItem?.parentElement) return;

        const videoUrl = urlFromLocation() || parseUniversalData() || '';
        const dl = buildDownloadBlockHorizontal(bookmarkItem, videoUrl);
        bookmarkItem.insertAdjacentElement('afterend', dl);
    };

    const injectBesideBookmark = (bookmarkNode) => {
        if (isVideoDetailPage()) return;

        const control = getCollectControl(bookmarkNode);
        if (!control) return;
        const actionItem = getActionItem(control);
        if (!actionItem?.parentElement) return;
        if (actionItem.nextElementSibling?.hasAttribute('data-tiktok-rabbit-dl')) return;
        if (document.querySelector(`[data-tiktok-rabbit-dl][data-video-url]`)) return;

        const row = actionItem.parentElement;
        const videoUrl = resolveVideoUrl(control) || urlFromLocation() || '';

        if (isHorizontalActionRow(row)) {
            const dl = buildDownloadBlockHorizontal(actionItem, videoUrl);
            actionItem.insertAdjacentElement('afterend', dl);
            return;
        }

        const dl = buildDownloadBlockVertical(control, videoUrl);
        actionItem.insertAdjacentElement('afterend', dl);
    };

    const injectAll = () => {
        if (isVideoDetailPage()) {
            injectVideoDetailRow();
            return;
        }
        findBookmarkNodes().forEach(injectBesideBookmark);
    };

    const style = document.createElement('style');
    style.textContent = `
        .tiktok-rabbit-dl-wrap {
            pointer-events: auto !important;
            z-index: 10 !important;
            flex-shrink: 0 !important;
        }
        .tiktok-rabbit-dl-vertical {
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 10px 0 !important;
            padding: 0 !important;
            min-width: 52px !important;
        }
        .tiktok-rabbit-dl-inline {
            display: inline-flex !important;
            flex-direction: row !important;
            align-items: center !important;
            justify-content: flex-start !important;
            gap: 6px !important;
            margin: 0 0 0 20px !important;
            padding: 0 !important;
            min-width: 0 !important;
            vertical-align: middle !important;
        }
        .tiktok-rabbit-dl-wrap button {
            border-radius: 50% !important;
            border: none !important;
            background: rgba(255, 255, 255, 0.12) !important;
            color: #fff !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            cursor: pointer !important;
            padding: 0 !important;
            flex-shrink: 0 !important;
        }
        .tiktok-rabbit-dl-vertical button {
            width: 48px !important;
            height: 48px !important;
            min-width: 48px !important;
            min-height: 48px !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.35) !important;
        }
        .tiktok-rabbit-dl-inline button {
            width: 40px !important;
            height: 40px !important;
            min-width: 40px !important;
            min-height: 40px !important;
        }
        .tiktok-rabbit-dl-wrap button:hover {
            background: rgba(254, 44, 85, 0.85) !important;
            transform: scale(1.05);
        }
        .tiktok-rabbit-dl-vertical strong {
            display: block !important;
            margin-top: 6px !important;
            color: #fff !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            text-align: center !important;
            text-shadow: 0 1px 2px rgba(0,0,0,0.8);
        }
        .tiktok-rabbit-dl-inline strong,
        .tiktok-rabbit-dl-inline span,
        .tiktok-rabbit-dl-inline p {
            margin: 0 !important;
            padding: 0 !important;
            color: #fff !important;
            font-size: 15px !important;
            font-weight: 600 !important;
            line-height: 1.2 !important;
            text-shadow: 0 1px 2px rgba(0,0,0,0.8);
        }
    `;
    document.head.appendChild(style);

    const cachePanel = document.createElement('div');
    cachePanel.id = 'tiktok-rabbit-cache-panel';
    Object.assign(cachePanel.style, {
        position: 'fixed',
        bottom: '16px',
        left: '16px',
        zIndex: '2147483646',
        background: 'rgba(0,0,0,0.75)',
        color: '#fff',
        padding: '8px 12px',
        borderRadius: '8px',
        fontSize: '12px',
        fontFamily: 'system-ui,sans-serif',
        display: 'flex',
        gap: '10px',
        alignItems: 'center',
    });
    const mkLink = (label, fn) => {
        const a = document.createElement('button');
        a.type = 'button';
        a.textContent = label;
        Object.assign(a.style, {
            background: '#fe2c55',
            border: 'none',
            color: '#fff',
            padding: '4px 10px',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '12px',
        });
        a.onclick = fn;
        return a;
    };
    cachePanel.appendChild(mkLink('Export cache', exportCacheV1));
    cachePanel.appendChild(mkLink('Import cache', importCacheV1));
    document.body.appendChild(cachePanel);

    injectAll();
    const obs = new MutationObserver(() => injectAll());
    obs.observe(document.documentElement, { childList: true, subtree: true });
    setInterval(injectAll, 1200);
})();

/*
Credits — modified by AlexRabbit (https://github.com/AlexRabbit)
  - AlexRabbit — Ez-TikTok-Downloader (TikWM flow, filenames, cache)
  - Greasy Fork 577695 — collect-button placement & video URL detection
  - TikWM — https://www.tikwm.com API
*/
