"""
songs.json 에 이미 있는 오리지널송 116곡은 한국어 제목만 있음 (title이 문자열).
이 스크립트는 오디오/자막은 그대로 두고, 영어·중국어 제목만 따로 받아와서
title을 {ko, en, cn} 형태로 채워 넣음.

사용법:
    python3 backfill_titles.py
    (songs.json 이 같은 폴더에 있어야 함, 인터넷 연결 필요)

songs.json 은 실행 전 songs.json.bak 으로 자동 백업됨.
"""

import json
import shutil
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_API_MEDIA = "https://b.jw-cdn.org/apis/mediator/v1/media-items"
LANG_MAP = {'en': 'E', 'cn': 'CHS'}
SONGS_FILE = "songs.json"
BACKUP_FILE = "songs.json.bak"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*'
}

http = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
http.mount("https://", HTTPAdapter(max_retries=retry))
http.headers.update(HEADERS)


def fetch_title(lang_code, natural_key):
    url = f"{BASE_API_MEDIA}/{lang_code}/{natural_key}?clientType=www"
    try:
        res = http.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            media = data.get('media', [{}])[0]
            return media.get('title', '')
    except Exception:
        pass
    return ''


def run():
    shutil.copy(SONGS_FILE, BACKUP_FILE)
    print(f"백업 완료: {BACKUP_FILE}")

    with open(SONGS_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    songs = raw['songs'] if isinstance(raw, dict) and 'songs' in raw else raw

    targets = [s for s in songs if s.get('category') == 'VODOriginalSongs' and isinstance(s.get('title'), str)]
    print(f"대상: {len(targets)}곡 (영어/중국어 제목 없는 오리지널송)")

    changed = 0
    for i, s in enumerate(targets, 1):
        nk = s['natural_key']
        title_dict = {'ko': s['title']}
        for lang, code in LANG_MAP.items():
            t = fetch_title(code, nk)
            if t:
                title_dict[lang] = t
        s['title'] = title_dict
        changed += 1
        print(f"[{i}/{len(targets)}] {nk} -> {title_dict}")

    with open(SONGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)

    print(f"\n완료: {changed}곡 제목 갱신함. {SONGS_FILE} 저장됨.")


if __name__ == '__main__':
    run()
