import streamlit as st
import pandas as pd
import yt_dlp
import requests
from bs4 import BeautifulSoup
import re
import json


# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="YouTube Metadata Extractor (No API)",
    page_icon="🎥",
    layout="wide"
)

# -----------------------------
# SESSION STATE INIT
# -----------------------------
if "df" not in st.session_state:
    st.session_state.df = None


# -----------------------------
# PREMIUM UI STYLING
# -----------------------------
st.markdown("""
<style>
body { background-color: #0d0d0d; }
.main-title {
    font-size: 44px;
    font-weight: 900;
    color: white;
    margin-bottom: 0px;
}
.sub-title {
    font-size: 16px;
    color: #bbbbbb;
    margin-top: -5px;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)


# -----------------------------
# HEADER
# -----------------------------
st.markdown("<div class='main-title'>🎬 YouTube Metadata Extractor</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sub-title'>Streamlit Cloud Ready · No API · Extract title, description, thumbnail + attempt tags</div>",
    unsafe_allow_html=True
)


# -----------------------------
# HELPERS
# -----------------------------
def safe_text(value):
    if value is None:
        return "Not Available"
    if str(value).strip() == "" or str(value).lower() == "nan":
        return "Not Available"
    return str(value)


def format_date(date_str):
    if date_str is None or str(date_str).lower() == "nan":
        return "Not Available"
    try:
        return pd.to_datetime(str(date_str), format="%Y%m%d").strftime("%d-%b-%Y")
    except:
        return str(date_str)


def clean_urls(text):
    urls = re.findall(r"(https?://[^\s]+)", text)
    return list(dict.fromkeys(urls))


# -----------------------------
# CHATGPT PROMPT BUILDER (from extracted data)
# -----------------------------
def build_chatgpt_prompt_from_df(
    df: pd.DataFrame,
    your_topic: str,
    target_type: str,
    tone: str,
    must_include: str,
    avoid_words: str,
    cta_type: str,
    branded_hashtags: str
) -> str:
    rows = []
    for _, r in df.iterrows():
        rows.append(
            f"- Title: {safe_text(r.get('Title'))}\n"
            f"  Channel: {safe_text(r.get('Channel'))}\n"
            f"  Views: {safe_text(r.get('Views'))}\n"
            f"  Upload Date: {safe_text(r.get('Upload Date'))}\n"
            f"  Duration (sec): {safe_text(r.get('Duration (sec)'))}\n"
            f"  Tags: {safe_text(r.get('Tags'))}\n"
            f"  URL: {safe_text(r.get('URL'))}\n"
        )

    competitor_block = "\n".join(rows)

    bh = (branded_hashtags or "").strip()
    if bh:
        bh = re.sub(r"[,\n]+", " ", bh)
        bh = " ".join([x for x in bh.split(" ") if x.strip()])

    title_len_rule = "under 60 characters" if target_type == "Shorts" else "under 80 characters"

    return f"""You are a YouTube {target_type} SEO strategist and copywriter.

My content topic (what my next video is about):
{your_topic}

Constraints:
- Tone: {tone}
- Must include keywords (comma list): {must_include}
- Avoid words/phrases (comma list): {avoid_words}
- CTA type: {cta_type}
- Branded/campaign hashtags to include (if relevant): {bh if bh else "None"}

Competitor reference data (extracted):
{competitor_block}

Tasks:
1) Identify 5 winning patterns from the competitor titles (hooks, length, punctuation, emojis, numbers, curiosity).
2) Create 8 title options optimized for {target_type}. Keep each natural and not misleading, {title_len_rule}.
3) Create 2 description options:
   - First line must be a hook.
   - Add 3 to 5 hashtags.
   - Include the CTA at the end.
4) Generate:
   - 20 to 30 tags as comma-separated.
   - 10 hashtags: 3 broad, 4 niche, 3 branded/campaign (include my branded ones if provided).
5) Give 1 pinned comment idea that drives engagement.

Output ONLY valid JSON in exactly this format:
{{
  "patterns": [...],
  "titles": [...],
  "descriptions": [...],
  "tags": "...",
  "hashtags": [...],
  "pinned_comment": "..."
}}
"""


# -----------------------------
# EXTRACT TAGS FROM HTML
# -----------------------------
def extract_tags_from_html(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return []

        html = r.text
        soup = BeautifulSoup(html, "html.parser")

        # Method 1: meta keywords
        meta_keywords = soup.find("meta", {"name": "keywords"})
        if meta_keywords and meta_keywords.get("content"):
            keywords = meta_keywords["content"].split(",")
            keywords = [k.strip() for k in keywords if k.strip()]
            if keywords:
                return keywords

        # Method 2: ytInitialPlayerResponse JSON
        match = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.*?\});", html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                tags = data.get("videoDetails", {}).get("keywords", [])
                if tags:
                    return tags
            except:
                pass

        # Method 3: regex fallback for "keywords":[...]
        match2 = re.search(r'"keywords":\s*\[(.*?)\]', html, re.DOTALL)
        if match2:
            raw = match2.group(1)
            tags = re.findall(r'"(.*?)"', raw)
            tags = [t.strip() for t in tags if t.strip()]
            if tags:
                return tags

        return []
    except:
        return []


# -----------------------------
# EXTRACT VIDEO INFO USING YT-DLP
# -----------------------------
def extract_video_info(url):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "noplaylist": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android"]
            }
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    thumbnails = info.get("thumbnails", [])
    best_thumb = thumbnails[-1]["url"] if thumbnails else info.get("thumbnail")

    tags = info.get("tags", [])
    if not tags:
        tags = extract_tags_from_html(url)

    return {
        "URL": url,
        "Title": info.get("title") or "Not Available",
        "Description": info.get("description") or "Not Available",
        "Tags": ", ".join(tags) if tags else "Not Found",
        "Channel": info.get("uploader") or info.get("channel") or "Not Available",
        "Upload Date": info.get("upload_date") or "Not Available",
        "Views": info.get("view_count") or "Not Available",
        "Duration (sec)": info.get("duration") or "Not Available",
        "Thumbnail": best_thumb or ""
    }


# -----------------------------
# INPUT UI
# -----------------------------
text_input = st.text_area(
    "📌 Paste multiple YouTube URLs (one per line)",
    height=200,
    placeholder="https://www.youtube.com/watch?v=xxxx\nhttps://youtu.be/yyyy"
)

col1, col2 = st.columns([2, 2])

with col1:
    extract_btn = st.button("🚀 Extract Metadata", use_container_width=True)

with col2:
    clear_btn = st.button("🧹 Clear", use_container_width=True)

if clear_btn:
    st.session_state.df = None
    st.rerun()


# -----------------------------
# PROCESSING (only when button clicked)
# -----------------------------
if extract_btn:
    urls = clean_urls(text_input)

    if not urls:
        st.error("❌ Please paste at least one valid YouTube URL.")
    else:
        st.info(f"🔍 Found {len(urls)} URLs. Extracting metadata...")

        results = []
        progress = st.progress(0)

        for i, url in enumerate(urls):
            try:
                data = extract_video_info(url)
                results.append(data)
            except Exception as e:
                results.append({
                    "URL": url,
                    "Title": "ERROR",
                    "Description": str(e),
                    "Tags": "N/A",
                    "Channel": "N/A",
                    "Upload Date": "N/A",
                    "Views": "N/A",
                    "Duration (sec)": "N/A",
                    "Thumbnail": ""
                })

            progress.progress((i + 1) / len(urls))

        df = pd.DataFrame(results)
        df["Upload Date"] = df["Upload Date"].apply(format_date)
        st.session_state.df = df

        st.success("✅ Extraction complete!")


# -----------------------------
# RENDER RESULTS (persist across reruns)
# -----------------------------
df = st.session_state.df

if df is not None and not df.empty:
    # Data table
    st.markdown("## 📊 Extracted Data")
    st.dataframe(df, width="stretch")

    # Prompt builder
    st.markdown("## 🤖 ChatGPT Prompt Builder")

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        your_topic = st.text_input("Your next video topic (1 line)", value="Write your next video idea here")
    with c2:
        target_type = st.selectbox("Target type", ["Shorts", "Videos"], index=0)
    with c3:
        tone = st.selectbox("Tone", ["fun", "educational", "emotional", "curious", "urgent"], index=1)

    c4, c5 = st.columns(2)
    with c4:
        must_include = st.text_input("Must include keywords (comma-separated)", value="wooden toy, Montessori, toddler")
        branded_hashtags = st.text_input("Branded/campaign hashtags (comma or space)", value="#lucasandfriends")
    with c5:
        avoid_words = st.text_input("Avoid words (comma-separated)", value="cheap, discount")
        cta_type = st.selectbox("CTA type", ["Follow", "Shop", "Comment", "Save", "Share"], index=2)

    prompt_text = build_chatgpt_prompt_from_df(
        df=df,
        your_topic=your_topic,
        target_type=target_type,
        tone=tone,
        must_include=must_include,
        avoid_words=avoid_words,
        cta_type=cta_type,
        branded_hashtags=branded_hashtags
    )

    st.info("Copy the prompt below and paste into ChatGPT. It will return JSON with patterns, titles, descriptions, tags, hashtags, and a pinned comment.")
    st.text_area("ChatGPT Prompt", prompt_text, height=420)

    # CSV download
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download CSV",
        data=csv,
        file_name="youtube_metadata.csv",
        mime="text/csv"
    )

    # Preview cards
    st.markdown("## 🎞️ Preview Cards")

    for _, row in df.iterrows():
        st.markdown("---")
        colA, colB = st.columns([1, 3])

        with colA:
            thumb = safe_text(row.get("Thumbnail"))
            if thumb != "Not Available":
                st.image(thumb, width="stretch")
            else:
                st.write("No Thumbnail")

        with colB:
            st.subheader(safe_text(row.get("Title")))
            st.write("**Channel:**", safe_text(row.get("Channel")))
            st.write("**Views:**", safe_text(row.get("Views")))
            st.write("**Upload Date:**", safe_text(row.get("Upload Date")))
            st.write("**Duration (sec):**", safe_text(row.get("Duration (sec)")))
            st.write("**Tags:**", safe_text(row.get("Tags")))
            st.write("**Description:**", safe_text(row.get("Description")))
            st.write("**URL:**", safe_text(row.get("URL")))


# ------------------------------------------------------------
# Footer
# ------------------------------------------------------------
st.text("")
st.text("")
st.text("")
st.markdown("---")
st.markdown("**✶ Built like a weapon, use like a tool. ✶**")
st.text("- by Ex-Code Warrior Ⓜ")
st.markdown("---")
