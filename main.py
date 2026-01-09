import os
import asyncio
import feedparser
import edge_tts
import re
from openai import OpenAI
from datetime import datetime
import xml.etree.ElementTree as ET
from email.utils import formatdate

# --- 配置区域 ---
RSS_URLS = [
    "https://feeds.feedburner.com/hackernews-zh", # Hacker News 中文
    "https://sspai.com/feed",      # 少数派
    "http://www.ruanyifeng.com/blog/atom.xml", # 阮一峰
    "https://rsshub.app/jike/topic/553870e8e4b0cafb0a1cba80", # 即刻科技圈（备用）
]

PODCAST_NAME = "我的车载早报"

# ⚠️⚠️⚠️ 请在这里填入你的 GitHub Pages 地址 ⚠️⚠️⚠️
# 格式：https://<用户名>.github.io/<仓库名>
BASE_URL = "https://secret2030.github.io/my-daily-podcast"

# 使用 SiliconFlow (兼容 OpenAI SDK)
client = OpenAI(
    api_key=os.environ.get("SILICON_KEY"),
    base_url="https://api.siliconflow.cn/v1"
)

def clean_text_for_tts(text):
    """清洗文案，去掉 Markdown 符号"""
    # 去掉加粗
    text = text.replace("**", "").replace("__", "")
    # 去掉标题符号
    text = text.replace("##", "").replace("###", "")
    # 去掉链接
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # 去掉列表符
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
    # 去掉多余空行
    text = re.sub(r'\n\s*\n', '\n', text)
    return text

def get_news_summary():
    """1. 抓取 RSS 并提取新闻"""
    print("正在抓取新闻...")
    articles = []
    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            # 每个源多取几条
            for entry in feed.entries[:3]: 
                # 清理 HTML 标签
                summary = entry.summary if hasattr(entry, 'summary') else ""
                clean_summary = re.sub(r'<[^>]+>', '', summary)[:200]
                articles.append(f"标题：{entry.title}\n内容：{clean_summary}")
        except Exception as e:
            print(f"源 {url} 抓取失败: {e}")
            continue
    
    if not articles:
        return "各位听众早安。今天网络似乎有点问题，没抓到新闻。建议听听音乐，祝您一天好心情！"

    news_text = "\n\n".join(articles)
    
    """2. 让 DeepSeek 写深度长文"""
    print("正在生成长文案...")
    prompt = f"""
    你是一位深度科技评论员，正在录制一期名为《前沿观察》的播客节目。
    
    要求：
    1. 【时长控制】请生成一篇约 2500 字的逐字稿（朗读时长约 10 分钟）。
    2. 【内容结构】
       - 开场：热情寒暄，快速预告今日重点。
       - 深度解读：从素材中挑选 2-3 个最重磅的新闻，进行深度剖析。不要只读新闻，要分析商业逻辑、行业影响。
       - 资讯快讯：快速过一遍其他次要新闻。
       - 结尾：总结升华，推荐一个提升效率的小技巧。
    3. 【语气风格】像罗永浩或罗振宇的风格，金句频出，口语化。
    4. 【绝对禁止】不要输出任何 Markdown 符号（如 **、##），不要输出“标题：”标签，直接输出纯文本。
    
    资讯素材：
    {news_text}
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3", 
            messages=[{"role": "user", "content": prompt}]
        )
        raw_content = response.choices[0].message.content
        return clean_text_for_tts(raw_content)
    except Exception as e:
        print(f"AI 生成失败: {e}")
        return "AI 大脑正在休息，暂时无法生成今日内容。"

async def run_tts(text, filename):
    """3. 使用 Edge-TTS 转语音"""
    print("正在生成语音...")
    # 使用更有磁性的男声
    communicate = edge_tts.Communicate(text, "zh-CN-YunjianNeural")
    await communicate.save(filename)

def update_rss_feed(audio_filename, title, pub_date):
    """4. 更新 RSS XML"""
    rss_file = "feed.xml"
    
    if not os.path.exists(rss_file):
        root = ET.Element("rss", version="2.0")
        channel = ET.SubElement(root, "channel")
        ET.SubElement(channel, "title").text = PODCAST_NAME
        ET.SubElement(channel, "description").text = "AI Generated Tech News"
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
    enclosure.set("length", "10000000") 

    channel.insert(3, item)
    
    # 保留最近 5 期
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
    print(f"文案准备就绪，长度：{len(script)} 字")
    
    asyncio.run(run_tts(script, filename))
    
    update_rss_feed(filename, f"{date_str} 科技早报", today)
    print("全部完成！")
