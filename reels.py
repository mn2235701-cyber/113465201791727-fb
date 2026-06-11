# =========================
# 🔧 CONFIG
# =========================

MIN_DURATION = 5
MAX_DURATION = 60

# =========================
# IMPORTS
# =========================
import requests, random, os, json, time, hashlib, subprocess

# =========================
# ENV
# =========================
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PAGE_ID = os.getenv("PAGE_ID")
ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")

# =========================
# FILES
# =========================
USED_FILE = "used_videos.json"
MUSIC_FILE = "music_state.json"
HASH_FILE = "reel_hash.json"
CAPTION_FILE = "caption_state.json"
RUN_LOG = "run_log.json"
KEYWORD_FILE = "keyword_state.json"

# =========================
# LOAD KEYWORDS FROM TXT
# =========================
def load_keywords():
    if not os.path.exists("keywords.txt"):
        raise Exception("❌ keywords.txt file not found")

    with open("keywords.txt", "r", encoding="utf-8") as f:
        keywords = [k.strip() for k in f.readlines() if k.strip()]

    if not keywords:
        raise Exception("❌ keywords.txt is empty")

    return keywords

SEARCH_KEYWORDS = load_keywords()

# =========================
# JSON HELPERS
# =========================
def load_json(file, default):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump(default, f)
        return default

    try:
        return json.load(open(file))
    except:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

# =========================
# RANDOM TEXT
# =========================
def get_random_line(file):
    if not os.path.exists(file):
        return ""

    with open(file, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]

    return random.choice(lines) if lines else ""

# =========================
# MUSIC (NO REPEAT)
# =========================
def get_music():
    if not os.path.exists("music"):
        return None, None

    files = [f for f in os.listdir("music") if f.endswith(".mp3")]

    if not files:
        return None, None

    state = load_json(MUSIC_FILE, {"used": []})

    available = [f for f in files if f not in state["used"]]

    if not available:
        state["used"] = []
        available = files

    music = random.choice(available)

    state["used"].append(music)
    save_json(MUSIC_FILE, state)

    return os.path.join("music", music), music

# =========================
# CAPTION
# =========================
def get_caption():
    title = get_random_line("hashtags.txt")
    desc = get_random_line("captions.txt")

    return title, desc

# =========================
# HASH
# =========================
def get_hash(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

# =========================
# FETCH VIDEO
# =========================
def fetch_video():
    used = load_json(USED_FILE, [])
    state = load_json(KEYWORD_FILE, {"index": 0})

    keyword = SEARCH_KEYWORDS[state["index"] % len(SEARCH_KEYWORDS)]

    state["index"] += 1
    save_json(KEYWORD_FILE, state)

    print("🔍 Keyword:", keyword)

    url = "https://api.pexels.com/videos/search"

    headers = {
        "Authorization": PEXELS_API_KEY
    }

    for page in range(1, 6):

        params = {
            "query": keyword,
            "per_page": 30,
            "page": page
        }

        data = requests.get(
            url,
            headers=headers,
            params=params
        ).json()

        videos = data.get("videos", [])

        for v in videos:

            vid = str(v["id"])

            if vid in used:
                continue

            # duration filter
            if v["duration"] < MIN_DURATION:
                continue

            if v["duration"] > MAX_DURATION:
                continue

            used.append(vid)

            save_json(USED_FILE, used[-200:])

            file = max(
                v["video_files"],
                key=lambda x: x.get("width", 0)
            )

            return {
                "url": file["link"],
                "id": vid,
                "query": keyword
            }

    raise Exception(f"❌ No valid video found for keyword: {keyword}")

# =========================
# DOWNLOAD
# =========================
def download(video):

    r = requests.get(video["url"])

    with open("video.mp4", "wb") as f:
        f.write(r.content)

# =========================
# ADD MUSIC + UPSCALE
# =========================
def add_music():

    music_path, music_name = get_music()

    if not music_path:
        return False, None

    cmd = [
        "ffmpeg",
        "-y",

        "-i", "video.mp4",

        "-stream_loop",
        "-1",

        "-i", music_path,

        "-vf",
        "scale='if(gt(iw,ih),1920,1080)':'if(gt(iw,ih),1080,1920)',setsar=1",

        "-map", "0:v:0",
        "-map", "1:a:0",

        "-shortest",

        "-r", "30",

        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",

        "-c:a", "aac",
        "-b:a", "192k",

        "final.mp4"
    ]

    subprocess.run(cmd, check=True)

    return True, music_name

# =========================
# FACEBOOK UPLOAD
# =========================
def upload(video, title, desc):

    url = f"https://graph-video.facebook.com/v19.0/{PAGE_ID}/videos"

    for i in range(5):

        try:

            with open(video, "rb") as f:

                r = requests.post(
                    url,
                    files={"source": f},
                    data={
                        "access_token": ACCESS_TOKEN,
                        "title": title,
                        "description": desc
                    }
                )

            response = r.json()

            print(response)

            if "id" in response:
                print("✅ Uploaded")
                return True

        except Exception as e:
            print("❌ Upload Error:", e)

        time.sleep(2 ** i)

    return False

# =========================
# LOG
# =========================
def log_run(data):

    logs = load_json(RUN_LOG, [])

    logs.append(data)

    save_json(RUN_LOG, logs[-200:])

# =========================
# CLEANUP
# =========================
def cleanup():

    for f in ["video.mp4", "final.mp4"]:

        if os.path.exists(f):
            os.remove(f)

# =========================
# MAIN
# =========================
def main():

    print("🚀 START")

    video = fetch_video()

    download(video)

    ok, music = add_music()

    if not ok:
        raise Exception("❌ No music files found")

    # Duplicate check without reels folder
    hashes = load_json(HASH_FILE, [])

    h = get_hash("final.mp4")

    if h in hashes:
        raise Exception("❌ Duplicate reel detected")

    hashes.append(h)

    save_json(HASH_FILE, hashes[-200:])

    title, desc = get_caption()

    uploaded = upload("final.mp4", title, desc)

    if not uploaded:
        raise Exception("❌ Upload failed")

    log_run({
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "video": video["id"],
        "keyword": video["query"],
        "music": music,
        "file": "final.mp4"
    })

    cleanup()

    print("🎬 DONE")
# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
