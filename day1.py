# -*- coding: utf-8 -*-
"""Agent 开发 · 第 1 天：跑通第一次大模型调用。

用法：
    1. 把 .env.example 复制成 .env，填好 API_KEY / BASE_URL / MODEL
    2. 命令行执行：python day1.py

看不懂的地方不用怕，先让它跑起来；哪一步报错就把报错原样发给我。
"""
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()          # 从同目录的 .env 文件里读配置

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL = os.getenv("MODEL")

# ---------- 1. 先检查配置有没有填全 ----------
missing = [name for name, value in
           (("API_KEY", API_KEY), ("BASE_URL", BASE_URL), ("MODEL", MODEL))
           if not value]
if missing:
    print("[X] .env 里这几项还没填：" + ", ".join(missing))
    print("    打开 .env 文件，把厂商控制台里的内容填进去，再运行一次。")
    sys.exit(1)

print("配置检查通过：")
print("    BASE_URL =", BASE_URL)
print("    MODEL    =", MODEL)
masked = API_KEY[:6] + "..." + API_KEY[-4:] if len(API_KEY) > 12 else "已设置"
print("    API_KEY  =", masked)

# ---------- 2. 创建客户端 ----------
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

question = "用一句话介绍你自己，并说明你是什么模型。"
print("\n提问：" + question)
print("-" * 52)

# ---------- 3. 发起调用 ----------
try:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "你是一个简洁的助手，回答不超过 50 字。"},
            {"role": "user", "content": question},
        ],
    )
except Exception as exc:                     # noqa: BLE001 - 新手要看到原始报错
    print("[X] 调用失败：" + type(exc).__name__)
    print("    原始报错：" + str(exc))
    print("\n对照着看常见原因：")
    print("    401 / 403            -> key 写错，或者没充值（有的厂商要先实名）")
    print("    Connection / Timeout -> BASE_URL 写错，或者需要代理")
    print("    model not found      -> MODEL 名字抄错了，回文档里重新复制")
    sys.exit(1)

print("模型回复：")
print(resp.choices[0].message.content)

# ---------- 4. 顺手看一眼这次花了多少 token ----------
usage = getattr(resp, "usage", None)
if usage:
    print("\n本次用量：输入 %s tokens，输出 %s tokens"
          % (usage.prompt_tokens, usage.completion_tokens))
