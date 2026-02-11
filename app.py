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
# PREMIUM UI STYLING
# -----------------------------
st.markdown("""
<style>
body {
    background-color: #0d0d0d;
}
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
st.markdown("<div class='sub-title'>Streamlit Cloud Ready · No API · Extract title, description, thumbnail + attempt tags</div>", unsafe_allow_html=True)


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
# EXTRACT TAGS FROM HTML
# -----------------------------
def extract_tags_from_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

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
    # Streamlit Cloud friendly config (avoids JS runtime issues)
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "noplaylist": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android"]  # best bypass for cloud
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
    st.rerun()


# -----------------------------
# PROCESSING
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

        # Format date nicely
        df["Upload Date"] = df["Upload Date"].apply(format_date)

        st.success("✅ Extraction complete!")

        # -----------------------------
        # DATA TABLE
        # -----------------------------
        st.markdown("## 📊 Extracted Data")
        st.dataframe(df, width="stretch")

        # -----------------------------
        # CSV DOWNLOAD
        # -----------------------------
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download CSV",
            data=csv,
            file_name="youtube_metadata.csv",
            mime="text/csv"
        )

        # -----------------------------
        # PREVIEW CARDS (SAFE VERSION)
        # -----------------------------
        st.markdown("## 🎞️ Preview Cards")

        for _, row in df.iterrows():
            st.markdown("---")

            col1, col2 = st.columns([1, 3])

            with col1:
                thumb = safe_text(row["Thumbnail"])
                if thumb != "Not Available":
                    st.image(thumb, width="stretch")
                else:
                    st.write("No Thumbnail")

            with col2:
                st.subheader(safe_text(row["Title"]))
                st.write("**Channel:**", safe_text(row["Channel"]))
                st.write("**Views:**", safe_text(row["Views"]))
                st.write("**Upload Date:**", safe_text(row["Upload Date"]))
                st.write("**Duration (sec):**", safe_text(row["Duration (sec)"]))
                st.write("**Tags:**", safe_text(row["Tags"]))
                st.write("**URL:**", safe_text(row["URL"]))
