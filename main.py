import os
import asyncio
import feedparser
import edge_tts
from openai import OpenAI
from datetime import datetime
import xml.etree.ElementTree as ET
from email.utils import formatdate

# --- 配置区域 ---
RSS_URLS = [
    "https://www.36kr.com/feed",
    "https://sspai.com/feed",
]
PODCAST_NAME = "我的车载早报"
# 记得修改下面的用户名！
BASE_URL = "https://secret2030.github.io/my-daily-podcast"

# 使用 SiliconFlow (兼容 OpenAI SDK)
client = OpenAI(
    api_key=os.environ.get("SILICON_KEY"),
    base_url="https://api.siliconflow.cn/v1"
)

def get_news_summary():
    """1. 抓取 RSS 并提取新闻"""
    print("正在抓取新闻...")
    articles = []
    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]: # 每个源取前2条
                clean_summary = entry.summary.replace('<p>', '').replace('</p>', '')[:150]
                articles.append(f"标题：{entry.title}\n内容：{clean_summary}")
        except Exception as e:
            print(f"抓取失败: {e}")
            continue
    
    news_text = "\n\n".join(articles)
    
    """2. 让 DeepSeek/Qwen 写稿"""
    print("正在思考文案...")
    prompt = f"""
    你是一位专业的早间新闻播客主持人。请根据以下资讯写一段口语化的播报稿。
    要求：
    1. 语气自然、流畅，不要有'下面是第一条新闻'这种机械的词。
    2. 对新闻进行简单的串联和点评。
    3. 总长度控制在 600 字左右。
    4. 不要输出任何标题或Markdown格式，直接输出要读的纯文本。
    
    资讯内容：
    {news_text}
    """
    
    # 这里使用的是 DeepSeek-V3 模型，如果以后不可用了，可以换成 Qwen/Qwen2.5-7B-Instruct
    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-V3", 
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

async def run_tts(text, filename):
    """3. 使用 Edge-TTS (免费) 转语音"""
    print("正在生成语音...")
    # zh-CN-YunxiNeural 是非常自然的男声
    # zh-CN-XiaoxiaoNeural 是非常自然的女声
    communicate = edge_tts.Communicate(text, "zh-CN-YunxiNeural")
    await communicate.save(filename)

def update_rss_feed(audio_filename, title, pub_date):
    """4. 更新 RSS XML"""
    rss_file = "feed.xml"
    
    if not os.path.exists(rss_file):
        root = ET.Element("rss", version="2.0")
        channel = ET.SubElement(root, "channel")
        ET.SubElement(channel, "title").text = PODCAST_NAME
        ET.SubElement(channel, "description").text = "AI Generated Podcast"
        ET.SubElement(channel, "link").text = BASE_URL
        tree = ET.ElementTree(root)
    else:
        tree = ET.parse(rss_file)
        root = tree.getroot()
        channel = root.find("channel")

    item = ET.Element("item")
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "pubDate").text = formatdate(pub_date.timestamp())
    enclosure = ET.SubElement(item, "enclosure")
    enclosure.set("url", f"{BASE_URL}/{audio_filename}")
    enclosure.set("type", "audio/mpeg")
    enclosure.set("length", "1000000") # 占位符

    channel.insert(3, item)
    
    # 只保留最近 5 集
    items = channel.findall("item")
    if len(items) > 5:
        channel.remove(items[-1])

    tree.write(rss_file, encoding="UTF-8", xml_declaration=True)

if __name__ == "__main__":
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    filename = f"episode_{date_str}.mp3"
    
    # 执行流程
    script = get_news_summary()
    print("文案生成成功，字数：", len(script))
    
    # 异步运行 TTS
    asyncio.run(run_tts(script, filename))
    
    update_rss_feed(filename, f"{date_str} 早间新闻", today)
    print("全部完成！")
