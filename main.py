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
    # 1. Hacker News 中文精选 (硬核科技前沿)
    "https://feeds.feedburner.com/hackernews-zh",
    
    # 2. 阮一峰的网络日志 (高质量科技/人文/工具)
    "http://www.ruanyifeng.com/blog/atom.xml",
    
    # 3. 少数派 - 派读 (高效工作/新玩意)
    "https://sspai.com/feed",
    
    # 4. 【关键】Product Hunt (每日全球最新发布的新产品)
    "https://rsshub.app/producthunt/today",
    
    # 5. 如果你非要 X 的内容，可以用 RSSHub 的镜像 (可能不稳定)
    # 比如抓取 Elon Musk 的推文：
    "https://rsshub.app/twitter/user/elonmusk", 
    # 建议替换为 "即刻" 的科技圈热榜 (国内平替版 X，资讯很快)
    "https://rsshub.app/jike/topic/553870e8e4b0cafb0a1cba80", 
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
            for entry in feed.entries[:6]: # 每个源取前6条
                clean_summary = entry.summary.replace('<p>', '').replace('</p>', '')[:150]
                articles.append(f"标题：{entry.title}\n内容：{clean_summary}")
        except Exception as e:
            print(f"抓取失败: {e}")
            continue
    
    news_text = "\n\n".join(articles)
    
    """2. 让 DeepSeek/Qwen 写稿"""
    print("正在思考文案...")
    prompt = f"""
    你是一位深度科技评论员，正在录制一期名为《前沿观察》的播客节目。
    
    要求：
    1. 【时长控制】请生成一篇长约 3000 字的逐字稿（朗读时长约 10-12 分钟）。
    2. 【结构安排】
       - 开场（1分钟）：寒暄，快速预告今日重点。
       - 深度解读（6分钟）：从素材中挑选 2-3 个最重磅的新闻，进行深度剖析。不要只读新闻，要分析它背后的商业逻辑、对行业的影响、以及网友的争议点。你可以适度发散，引用一些科技史的案例。
       - 甚至可以设计两个角色（你自己扮演）：比如“有人可能会问...”，然后你来反驳，增加互动感。
       - 资讯快讯（3分钟）：快速过一遍其他 5-6 条次要新闻，一句话点评即可。
       - 结尾（1分钟）：总结升华，推荐一个提升效率的小技巧或工具。
    3. 【语气风格】专业但不枯燥，像老罗（罗永浩）或者罗振宇那种风格，金句频出。
    
    资讯素材如下：
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
    communicate = edge_tts.Communicate(text, "zh-CN-YunjianNeural")
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
