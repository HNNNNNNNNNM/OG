import requests
import json
import re
import time
import os
import subprocess
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- 설정 구역 ---
MAIN_LANGUAGE = 'KO'
LANG_MAP = {'ko': 'KO', 'en': 'E', 'cn': 'CHS'}

BASE_API_CATEGORY = "https://b.jw-cdn.org/apis/mediator/v1/categories"
BASE_API_MEDIA = "https://b.jw-cdn.org/apis/mediator/v1/media-items"

TARGET_CATEGORIES = [
    'VODOriginalSongs',
    'VODCjOriginalSongs',
    'VODSJJMeetings',
    'SJJChorus'
]

EXCLUDE_KEYWORDS = ['Instrumental', '기악', 'Chorus', '합창', 'Orchestral', '관현악']
LOCAL_SAVE_FILE = "songs.json"          # GitHub Actions 워크플로가 이 파일명을 그대로 커밋합니다
EXTRACTED_AUDIO_DIR = "extracted_audio"  # mp3가 없어서 영상에서 뽑아낸 오디오를 저장하는 폴더

visited_keys = set()
existing_keys = set()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*'
}

http = requests.Session()
retry = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
http.mount("https://", HTTPAdapter(max_retries=retry))
http.headers.update(HEADERS)


def time_to_seconds(time_str):
    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            h, m, s = parts
            s, ms = s.split('.')
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
        elif len(parts) == 2:
            m, s = parts
            s, ms = s.split('.')
            return int(m) * 60 + int(s) + int(ms) / 1000
        return 0
    except:
        return 0


def parse_vtt(vtt_url):
    if not vtt_url:
        return []
    try:
        res = http.get(vtt_url, timeout=10)
        res.encoding = 'utf-8-sig'
        if res.status_code != 200:
            return []
        lines = res.text.splitlines()
        script_data = []
        current_start = 0
        current_end = 0
        current_text = []
        time_pattern = re.compile(r'((?:\d{2}:)?\d{2}:\d{2}\.\d{3})\s*-->\s*((?:\d{2}:)?\d{2}:\d{2}\.\d{3})')

        for line in lines:
            line = line.strip()
            time_match = time_pattern.search(line)
            if time_match:
                if current_text:
                    full_text = " ".join(current_text).strip()
                    if full_text:
                        script_data.append({"start": current_start, "end": current_end, "text": full_text})
                current_start = time_to_seconds(time_match.group(1))
                current_end = time_to_seconds(time_match.group(2))
                current_text = []
                continue
            if not line or line.isdigit() or line.startswith('WEBVTT') or line.startswith('NOTE') or '-->' in line:
                continue
            clean_line = re.sub(r'<[^>]+>', '', line)
            current_text.append(clean_line)

        if current_text:
            script_data.append({"start": current_start, "end": current_end, "text": " ".join(current_text).strip()})
        return script_data
    except:
        return []


def pick_best_video_file(files):
    """mp3가 없을 때, 화질이 가장 좋은 video 파일을 골라 반환"""
    video_files = [f for f in files if f.get('mimetype', '').startswith('video/') and f.get('progressiveDownloadURL')]
    if not video_files:
        return None
    video_files.sort(key=lambda f: (f.get('frameHeight', 0) or 0, f.get('bitRate', 0) or 0), reverse=True)
    return video_files[0]


def extract_audio_from_video(video_url, out_name):
    """고화질 영상을 받아 오디오만 mp3로 뽑아내고 원본 영상은 삭제. 성공 시 로컬 mp3 경로 반환"""
    os.makedirs(EXTRACTED_AUDIO_DIR, exist_ok=True)
    out_mp3 = os.path.join(EXTRACTED_AUDIO_DIR, out_name + '.mp3')
    if os.path.exists(out_mp3):
        return out_mp3
    tmp_video = out_mp3 + '.tmp.mp4'
    try:
        r = http.get(video_url, stream=True, timeout=60)
        r.raise_for_status()
        with open(tmp_video, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
        subprocess.run(
            ['ffmpeg', '-y', '-i', tmp_video, '-vn', '-acodec', 'libmp3lame', '-q:a', '2', out_mp3],
            check=True, capture_output=True
        )
        return out_mp3
    except Exception as e:
        print(f"   ! 오디오 추출 실패: {e}")
        return None
    finally:
        if os.path.exists(tmp_video):
            os.remove(tmp_video)


def get_media_assets(media_item, natural_key_for_extraction=None):
    audio_url = ""
    sub_url = ""
    cover_url = ""

    if 'images' in media_item:
        images = media_item['images']
        if 'sqr' in images and 'lg' in images['sqr']:
            cover_url = images['sqr']['lg']
        elif 'wss' in images and 'lg' in images['wss']:
            cover_url = images['wss']['lg']

    if 'files' in media_item:
        for file in media_item['files']:
            if file.get('mimetype') == 'audio/mpeg' or file.get('progressiveDownloadURL', '').endswith('.mp3'):
                audio_url = file.get('progressiveDownloadURL')
            if 'subtitles' in file and not sub_url:
                sub_url = file['subtitles']['url']

        # mp3가 없으면: 가장 화질 좋은 영상을 받아 오디오만 추출 (ffmpeg 필요)
        if not audio_url and media_item['files']:
            best_video = pick_best_video_file(media_item['files'])
            if best_video and natural_key_for_extraction:
                extracted = extract_audio_from_video(best_video['progressiveDownloadURL'], natural_key_for_extraction)
                if extracted:
                    audio_url = extracted   # 로컬 파일 경로 — 레포에 같이 커밋해야 재생됨
            if not audio_url:
                audio_url = media_item['files'][0].get('progressiveDownloadURL')

    return audio_url, sub_url, cover_url


def fetch_variant_data(lang_code, natural_key):
    target_url = f"{BASE_API_MEDIA}/{lang_code}/{natural_key}?clientType=www"
    try:
        res = http.get(target_url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            media = data.get('media', [{}])[0]
            audio_url, sub_url, _ = get_media_assets(media, natural_key_for_extraction=f"{natural_key}_{lang_code}")
            script = parse_vtt(sub_url) if sub_url else []
            return audio_url, script
    except:
        pass
    return None, []


def crawl_category(category_key, collected_list, is_target=False):
    if category_key in visited_keys:
        return
    visited_keys.add(category_key)
    if not is_target and any(ex in category_key for ex in EXCLUDE_KEYWORDS):
        return

    target_url = f"{BASE_API_CATEGORY}/{MAIN_LANGUAGE}/{category_key}?detailed=1"
    try:
        res = http.get(target_url, timeout=20)
        if res.status_code != 200:
            print(f"[진단] {category_key}: HTTP {res.status_code} — 카테고리 키가 존재하지 않거나 접근 불가")
            return
        data = res.json()
        cat_info = data.get('category', {})
        current_title = cat_info.get('title', category_key)
        media_count = len(cat_info.get('media', []))
        sub_count = len(cat_info.get('subcategories', []))
        print(f"[진단] {category_key}: 로드 성공 — 제목='{current_title}', 미디어 {media_count}개, 하위카테고리 {sub_count}개")

        if 'media' in cat_info:
            for media in cat_info['media']:
                natural_key = media.get('languageAgnosticNaturalKey')
                if not natural_key:
                    continue
                if natural_key in existing_keys:
                    continue
                if any(ex in media.get('title', '') for ex in EXCLUDE_KEYWORDS):
                    continue

                audio_url_ko, sub_url_ko, cover_url = get_media_assets(media, natural_key_for_extraction=f"{natural_key}_ko")
                if not audio_url_ko:
                    continue

                print(f"   + Extracting: {media['title'][:30]}...")

                scripts = {}
                audio_urls = {}

                scripts['ko'] = parse_vtt(sub_url_ko)
                audio_urls['ko'] = audio_url_ko

                for key, code in LANG_MAP.items():
                    if key == 'ko':
                        continue
                    a_url, script = fetch_variant_data(code, natural_key)
                    if a_url:
                        audio_urls[key] = a_url
                    if script:
                        scripts[key] = script

                collected_list.append({
                    'category': current_title,
                    'title': media['title'],
                    'natural_key': natural_key,
                    'cover_url': cover_url,
                    'audio_urls': audio_urls,
                    'date': media.get('firstPublished', '0000-00-00'),
                    'scripts': scripts
                })
                existing_keys.add(natural_key)
                time.sleep(0.1)

        for sub in cat_info.get('subcategories', []):
            if sub.get('key'):
                crawl_category(sub.get('key'), collected_list)
    except Exception as e:
        print(f"Error ({category_key}): {e}")


def load_existing_data():
    total_data = []
    if os.path.exists(LOCAL_SAVE_FILE):
        try:
            with open(LOCAL_SAVE_FILE, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            total_data = raw['songs'] if isinstance(raw, dict) and 'songs' in raw else raw
            print(f"Loaded {len(total_data)} items.")
        except:
            pass

    for item in total_data:
        if 'natural_key' in item:
            existing_keys.add(item['natural_key'])
    return total_data


def save_data(data):
    data.sort(key=lambda x: x.get('date', '0000-00-00'), reverse=True)
    with open(LOCAL_SAVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(data)} total songs.")


def run():
    print("--- Start JW Music Sync Crawler ---")
    collected_list = load_existing_data()
    initial_count = len(collected_list)

    for category in TARGET_CATEGORIES:
        crawl_category(category, collected_list, is_target=True)

    added_count = len(collected_list) - initial_count
    print(f"Finished. New songs added: {added_count}")

    if added_count > 0:
        save_data(collected_list)


if __name__ == "__main__":
    run()
