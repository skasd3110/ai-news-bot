import os
import requests
import feedparser
from datetime import datetime, timezone
from google import genai

# ============================================================
# 設定
# ============================================================

DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

RSS_FEEDS = [
    "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",
    "https://openai.com/news/rss.xml",
    "https://www.anthropic.com/news/rss.xml",
    "https://deepmind.google/blog/rss.xml",
    "https://huggingface.co/blog/feed.xml",
]

MAX_ARTICLES_PER_FEED = 10
DISCORD_LIMIT = 1800

# ============================================================
# RSS取得
# ============================================================

def collect_articles():
    articles = []

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:MAX_ARTICLES_PER_FEED]:

                title = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")

                articles.append(
                    {
                        "title": title,
                        "summary": summary,
                        "source": feed_url,
                    }
                )

        except Exception as e:
            print(f"RSS取得失敗: {feed_url}")
            print(e)

    return articles


# ============================================================
# Gemini
# ============================================================

def create_prompt(articles, weekly=False):

    news_text = ""

    for i, article in enumerate(articles, start=1):
        news_text += f"""
記事{i}
タイトル:
{article['title']}

概要:
{article['summary']}

ソース:
{article['source']}

----------------------------
"""

    if weekly:
        mode_text = """
以下の記事群から、
今週最も重要だったAIニュースTOP10を作成してください。
"""
    else:
        mode_text = """
以下の記事群から、
本日のAIニュースTOP5を作成してください。
"""

    prompt = f"""
{mode_text}

要件:

1. 重複ニュースは統合
2. 重要度順にランキング
3. 日本語で出力
4. 英語記事は翻訳
5. 各ニュースに重要度スコア(0〜100)
6. 関連企業を抽出
7. 背景を説明
8. 今後の影響を説明
9. Discordで読みやすいMarkdown形式

出力形式:

# 1位

タイトル

重要度: xx/100

関連企業:
- 企業名

要約:
...

背景:
...

今後の影響:
...

================================

対象記事:

{news_text}
"""

    return prompt


def generate_report(prompt):

    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text


# ============================================================
# Discord送信
# ============================================================

def send_discord(message):

    chunks = []

    for i in range(0, len(message), DISCORD_LIMIT):
        chunks.append(message[i:i + DISCORD_LIMIT])

    for chunk in chunks:

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json={
                "content": chunk
            },
            timeout=30
        )

        print("Discord:", response.status_code)

        if response.status_code >= 300:
            print(response.text)


# ============================================================
# メイン
# ============================================================

def main():

    print("RSS取得開始")

    articles = collect_articles()

    print(f"取得記事数: {len(articles)}")

    if not articles:
        raise Exception("記事取得失敗")

    # UTC基準
    now = datetime.now(timezone.utc)

    # 日曜判定
    weekly = (now.weekday() == 6)

    prompt = create_prompt(
        articles,
        weekly=weekly
    )

    print("Gemini生成開始")

    report = generate_report(prompt)

    if weekly:
        header = "📊 **今週のAIニュースTOP10**\n\n"
    else:
        header = "📢 **本日のAIニュースTOP5**\n\n"

    message = header + report

    print("Discord送信")

    send_discord(message)

    print("完了")


if __name__ == "__main__":
    main()
