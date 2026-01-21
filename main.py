import os
import asyncio
import feedparser
import edge_tts
import re
from openai import OpenAI
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
from email.utils import formatdate

# --- 配置区域 ---
RSS_URLS = [
    "https://36kr.com/feed/newsflash",            # 36氪快讯
    "https://sspai.com/feed",                     # 少数派
    "https://feeds.feedburner.com/hackernews-zh", # Hacker News 中文
    "http://www.ruanyifeng.com/blog/atom.xml",    # 阮一峰
]

# 【修改】这里改成了你想要的新名字
PODCAST_NAME = "你好AI"

# ⚠️⚠️⚠️ 请务必修改这里为你的 GitHub Pages 地址 ⚠️⚠️⚠️
BASE_URL = "https://secret2030.github.io/my-daily-podcast"

# 设定节目时长目标 (分钟)
TARGET_DURATION_MINUTES = 12
# 设定中文语速 (字/分钟)
WORDS_PER_MINUTE = 250 

# 使用 SiliconFlow (兼容 OpenAI SDK)
client = OpenAI(
    api_key=os.environ.get("SILICON_KEY"),
    base_url="https://api.siliconflow.cn/v1"
)

def clean_text_for_tts(text):
    """双重清洗：防止 AI 哪怕输出了 Markdown 也能兜底"""
    text = text.replace("**", "").replace("__", "")
    text = text.replace("##", "").replace("###", "")
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n\s*\n', '\n', text)
    # 去掉可能存在的 Speaker 标签 (如 "老罗: ")
    text = re.sub(r'^[^：\n]+：', '', text, flags=re.MULTILINE) 
    return text

def get_news_summary():
    """1. 抓取 RSS 并提取新闻"""
    print("正在抓取新闻...")
    articles = []
    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]: 
                summary = entry.summary if hasattr(entry, 'summary') else ""
                clean_summary = re.sub(r'<[^>]+>', '', summary)[:250] 
                articles.append(f"《{entry.title}》\n内容：{clean_summary}")
        except Exception as e:
            print(f"源 {url} 抓取失败: {e}")
            continue
    
    if not articles:
        return "各位听众早安。今天网络似乎有点问题，没抓到新闻。建议听听音乐，祝您一天好心情！"

    news_text = "\n\n".join(articles)
    
    """2. 构建高级提示词 (Zenfeed Style)"""
    print("正在构建高级提示词并生成文案...")
    
    estimated_words = TARGET_DURATION_MINUTES * WORDS_PER_MINUTE
    
    prompt_segments = []
    
    # 角色定义
    prompt_segments.append("你是一位名为【老罗】的资深科技评论员，正在录制一期名为《你好AI》的单人脱口秀播客。")
    
    # 任务目标
    prompt_segments.append(f"请将以下资讯素材，改写成一份深度播客逐字稿。目标长度约为 {estimated_words} 字，以适应约 {TARGET_DURATION_MINUTES} 分钟的朗读时长。")
    
    # 详细内容指令
    prompt_segments.append("""
    内容结构要求：
    - 开场（约1分钟）：必须包含热情、自然的寒暄，预告今日看点。欢迎大家收听《你好AI》。
    - 核心深读（约8分钟）：从素材中挑选 2-3 个最具争议或深度的科技新闻，进行辛辣点评。要分析商业逻辑、吐槽行业乱象，不要只读新闻稿。多用“这就好比...”、“大家想一想...”这样的口语。
    - 资讯串烧（约2分钟）：快速过一遍其他次要新闻。
    - 结尾（约1分钟）：总结升华，并推荐一个提升效率的小技巧，最后礼貌道别。
    """)
    
    # 负面约束 (Zenfeed Style)
    prompt_segments.append("格式强制要求 (Format Constraints):")
    prompt_segments.append("- The output MUST be raw spoken text only. (只输出要读的纯文本)")
    prompt_segments.append("- Do NOT include speaker names (e.g., '主持人:', '老罗:'). (不要包含说话人标签)")
    prompt_segments.append("- Do NOT include formatting symbols like **, ##, or []. (严禁使用 Markdown)")
    prompt_segments.append("- Do NOT include stage directions (e.g., [Music plays]). (不要包含旁白动作)")
    prompt_segments.append("- Do NOT use title labels like '标题：'.")
    
    # 注入素材
    prompt_segments.append("现在，基于以下素材开始创作：")
    prompt_segments.append(news_text)
    
    final_prompt = "\n\n".join(prompt_segments)
    
    try:
        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3", 
            messages=[{"role": "user", "content": final_prompt}]
        )
        raw_content = response.choices[0].message.content
        return clean_text_for_tts(raw_content)
    except Exception as e:
        print(f"AI 生成失败: {e}")
        return "AI 大脑正在休息，暂时无法生成今日内容。"

async def run_tts(text, filename):
    """3. 使用 Edge-TTS 转语音"""
    print("正在生成语音...")
    # zh-CN-YunjianNeural: 稳重磁性男声
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
        
        # 【新增】强制更新频道名称（防止改了名字不生效）
        channel_title = channel.find("title")
        if channel_title is not None:
            channel_title.text = PODCAST_NAME

    item = ET.Element("item")
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "pubDate").text = formatdate(pub_date.timestamp())
    enclosure = ET.SubElement(item, "enclosure")
    enclosure.set("url", f"{BASE_URL}/{audio_filename}")
    enclosure.set("type", "audio/mpeg")
    enclosure.set("length", "12582912") 

    channel.insert(3, item)
    
    items = channel.findall("item")
    if len(items) > 5:
        channel.remove(items[-1])

    tree.write(rss_file, encoding="UTF-8", xml_declaration=True)

if __name__ == "__main__":
    # 强制北京时间
    beijing_time = datetime.now(timezone.utc) + timedelta(hours=8)
    date_str = beijing_time.strftime("%Y-%m-%d")
    
    filename = f"episode_{date_str}.mp3"
    print(f"开始执行任务，北京时间：{beijing_time}")
    
    script = get_news_summary()
    print(f"文案生成完毕，字数：{len(script)}")
    
    asyncio.run(run_tts(script, filename))
    
    update_rss_feed(filename, f"{date_str} 你好AI 早报", beijing_time)
    print("全部完成！")
