import streamlit as st
import pandas as pd
import yt_dlp
import requests
from bs4 import BeautifulSoup
import re
import json
import streamlit.components.v1 as components


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
    color: black;
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
st.markdown("<div class='main-title'>🎬 YouTube Metadata Extractor & Prompt Generator</div>", unsafe_allow_html=True)
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
# CHATGPT PROMPT BUILDER
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
            f"- URL: {safe_text(r.get('URL'))}\n"
            f"- Title: {safe_text(r.get('Title'))}\n"
            f"- Description: {safe_text(r.get('Description'))}\n"
            f"- Tags: {safe_text(r.get('Tags'))}\n"
            f"  Views: {safe_text(r.get('Views'))}\n"
            f"  Duration (sec): {safe_text(r.get('Duration (sec)'))}\n"
        )

    competitor_block = "\n".join(rows)

    title_len_rule = "under 100 characters" if target_type == "Shorts" else "under 100 characters"

    return f"""
You are an expert YouTube {target_type} SEO strategist and brand copywriter for kids educational content.

Your job:
Generate a YouTube {target_type} optimized Title, Description, Hashtags, and Tags in the SAME style as the reference example below.

IMPORTANT RULES:
- Identify 5 winning patterns from the competitor titles (hooks, length, punctuation, emojis, numbers, curiosity).
- Create 5 title options optimized for {target_type}. Keep each natural and not misleading, {title_len_rule}.
- Output must be SEO optimized but NOT spammy.
- Use emojis naturally (2 to 5 emojis).
- The description must feel safe, parent-trusted, and educational.
- Always include the Subscribe link exactly:
https://www.youtube.com/@RVAppStudios?sub_confirmation=1
- Avoid these words: {avoid_words}
- Must include these keywords naturally: {must_include}
- Give 1 pinned comment idea that drives engagement.

VIDEO TOPIC:
{your_topic}

TARGET AUDIENCE:
Babies, toddlers, preschoolers (ages 2–7)

REFERENCE STYLE (must follow):
Title format example:
ABC Song for Baby 🚂 | Learn Alphabet Letters & Sounds with Lucas | Fun Toddler Learning #shorts

Description format example:
🎵 Hook line with emojis
Short paragraph explaining educational value
Perfect for: bullet list
Emotional trust paragraph
Brand trust paragraph
App promotion paragraph
Subscribe CTA line
Hashtags section

Now generate the following exactly in this format:

Title:
(Two SEO title with important keywords)

Description:
(full description following the exact structure)

Hashtags:
(5 hashtags, must include #lucasandfriends)

Tags:
(30-40 comma-separated tags, include #shorts and lucasandfriends)

Competitor video references:
{competitor_block}

Return ONLY in plain text with these exact headings:
Title:
Description:
Hashtags:
Tags:
"""


def render_copy_button(prompt_text: str):
    # JS button that copies the current prompt every rerun
    copy_html = f"""
    <div style="margin-top: 34px;">
      <button id="copyBtn"
        style="
          width: 100%;
          padding: 10px;
          background-color: #ff4b4b;
          color: white;
          border: none;
          border-radius: 8px;
          font-weight: bold;
          cursor: pointer;
        ">
        📋 Copy
      </button>
      <div id="copiedMsg" style="color:#0000FF; font-size:12px; margin-top:6px; display:none;">
        Copied!
      </div>
    </div>

    <script>
      const textToCopy = {json.dumps(prompt_text)};
      const btn = document.getElementById("copyBtn");
      const msg = document.getElementById("copiedMsg");

      btn.addEventListener("click", async () => {{
        try {{
          await navigator.clipboard.writeText(textToCopy);
          msg.style.display = "block";
          setTimeout(() => msg.style.display = "none", 1500);
        }} catch (e) {{
          alert("Copy failed. Please copy manually from the text box.");
        }}
      }});
    </script>
    """
    components.html(copy_html, height=95)


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
        "extractor_args": {"youtube": {"player_client": ["android"]}},
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
# INPUT UI (with default links)
# -----------------------------
text_input = st.text_area(
    "📌 Paste multiple YouTube URLs (one per line)",
    height=200,
    value="https://www.youtube.com/watch?v=9_WBQISVHnw\nhttps://www.youtube.com/shorts/ZzbDlLQwzFc",
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

        df_new = pd.DataFrame(results)
        df_new["Upload Date"] = df_new["Upload Date"].apply(format_date)
        st.session_state.df = df_new

        st.success("✅ Extraction complete!")


# -----------------------------
# RENDER RESULTS
# -----------------------------
df = st.session_state.df

if df is not None and not df.empty:
    st.markdown("## 📊 Extracted Data")
    st.dataframe(df, width="stretch")

    # CSV download
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download CSV",
        data=csv,
        file_name="youtube_metadata.csv",
        mime="text/csv"
    )

    st.markdown("## 🤖 ChatGPT Prompt Builder")

    # Inputs that affect prompt (these rerun and update prompt)
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        your_topic = st.text_input("Your next video topic (1 line)", value="baby first words learning video")
    with c2:
        target_type = st.selectbox("Target type", ["Shorts", "Videos"], index=0)
    with c3:
        tone = st.selectbox("Tone", ["fun", "educational", "emotional", "curious", "urgent"], index=1)

    c4, c5 = st.columns(2)
    with c4:
        must_include = st.text_input("Must include keywords (comma-separated)", value="baby, Montessori, toddler")
        branded_hashtags = st.text_input("Branded/campaign hashtags (comma or space)", value="#lucasandfriends")
    with c5:
        avoid_words = st.text_input("Avoid words (comma-separated)", value="any brand/company name")
        cta_type = st.selectbox("CTA type", ["Follow", "Shop", "Comment", "Save", "Share"], index=0)

    # Build prompt (always fresh)
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

    # Title + Copy button beside it
    title_col, copy_col = st.columns([6, 1])
    with title_col:
        st.info("Click Copy, then paste into ChatGPT. It will return titles, descriptions, tags, hashtags, and a pinned comment.")
        # st.markdown("## 🤖 ChatGPT Prompt Builder")
    with copy_col:
        render_copy_button(prompt_text)

    # st.info("Click Copy, then paste into ChatGPT. It will return JSON with patterns, titles, descriptions, tags, hashtags, and a pinned comment.")

    # IMPORTANT: no key here, so it updates whenever prompt_text changes
    st.text_area("ChatGPT Prompt", value=prompt_text, height=420)


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
