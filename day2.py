# -*- coding: utf-8 -*-
"""Agent 开发 · 第 2 天：流式输出、温度实验、诊断与成本。

四个实验，一个一个跑，别急：
    实验 1  流式输出：回复一个字一个字往外蹦
    实验 2  温度对比：同一批问题，用 0.0 / 0.7 / 1.3 各跑一遍
    实验 3  诊断：把 finish_reason 和 usage 的完整内容打出来
    实验 4  成本：算一算这几次调用花了多少钱

运行：python day2.py
"""
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL = os.getenv("MODEL")
PRICE_IN = os.getenv("INPUT_PRICE_PER_M")      # 元 / 百万 tokens，可选
PRICE_OUT = os.getenv("OUTPUT_PRICE_PER_M")    # 元 / 百万 tokens，可选

if not all([API_KEY, BASE_URL, MODEL]):
    print("[X] .env 还没填全，先回 Day 1 把 API_KEY / BASE_URL / MODEL 补齐。")
    sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

SYSTEM_PROMPT = "你是气象领域的技术助手，回答简洁准确，涉及专业概念时给出必要的限定条件。"

records = []          # 记录每次调用的结果，最后汇总


def line(title):
    print("\n" + "=" * 56)
    print(title)
    print("=" * 56)


def money(inp, out):
    """按 .env 里填的单价算钱；没填就返回 None。"""
    if not PRICE_IN or not PRICE_OUT:
        return None
    try:
        return inp / 1e6 * float(PRICE_IN) + out / 1e6 * float(PRICE_OUT)
    except ValueError:
        return None


# ---------------------------------------------------------------- 实验 1 ----
line("实验 1 · 流式输出")

question = "用三句话解释什么是资料同化，以及它在天气预报里的作用。"
print("提问：" + question)
print("-" * 56)

start = time.time()
char_count = 0
try:
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        stream=True,
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        piece = chunk.choices[0].delta.content
        if piece:
            print(piece, end="", flush=True)
            char_count += len(piece)
    print()
except Exception as exc:
    print("[X] 流式调用失败：" + type(exc).__name__ + " -> " + str(exc))
    sys.exit(1)

elapsed = time.time() - start
print("-" * 56)
print("共 %d 个字，用时 %.1f 秒，平均每秒 %.1f 字"
      % (char_count, elapsed, char_count / elapsed if elapsed else 0))
print("观察点：文字是不是一段一段出现的？第一个字出现得快不快？")
print("注意：流式输出默认不返回 token 用量，所以这里没有统计。")


# ---------------------------------------------------------------- 实验 2 ----
line("实验 2 · 温度对比（同一批问题，三档温度）")

questions = [
    ("事实题", "用两句话说明什么是资料同化。"),
    ("创意题", "给一个「气象数据可视化」小工具起三个名字，只要名字，用顿号隔开。"),
]
temperatures = [0.0, 0.7, 1.3]
index = 0

for q_type, q_text in questions:
    for temp in temperatures:
        index += 1
        print("\n--- 第 %d 次调用 ｜ %s ｜ temperature=%.1f ---" % (index, q_type, temp))
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": q_text},
                ],
                temperature=temp,
            )
        except Exception as exc:
            print("    调用失败：" + type(exc).__name__ + " -> " + str(exc))
            continue

        answer = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        in_p = getattr(usage, "prompt_tokens", 0) if usage else 0
        out_p = getattr(usage, "completion_tokens", 0) if usage else 0
        reason = resp.choices[0].finish_reason
        cost = money(in_p, out_p)

        print("    回复：" + answer.replace("\n", " ")[:160])
        print("    输入 %s tokens ｜ 输出 %s tokens ｜ finish_reason=%s"
              % (in_p, out_p, reason))
        if cost is not None:
            print("    本次成本约 %.6f 元" % cost)

        records.append((q_type, temp, in_p, out_p, reason, cost))


# ---------------------------------------------------------------- 实验 3 ----
line("实验 3 · 诊断：256 tokens 那个疑点")

resp = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "用一句话介绍你自己。"},
    ],
)

print("finish_reason =", resp.choices[0].finish_reason)
print("  -> stop = 模型正常说完了；length = 被 max_tokens 截断了")
print("\nusage 完整内容：")
print(resp.usage)
try:
    print("\n返回对象里有哪些字段：")
    print(sorted(resp.model_dump().keys()))
except Exception:
    pass
print("\n把上面这几行抄下来，我们第 3 天要用。")


# ---------------------------------------------------------------- 实验 4 ----
line("实验 4 · 成本汇总")

if not records:
    print("实验 2 没有成功记录，先解决报错。")
else:
    total_in = sum(r[2] for r in records)
    total_out = sum(r[3] for r in records)
    total_cost = sum(r[5] for r in records if r[5] is not None)
    print("%-8s %-6s %-10s %-10s %s"
          % ("题型", "温度", "输入token", "输出token", "finish_reason"))
    for q_type, temp, in_p, out_p, reason, _ in records:
        print("%-8s %-6.1f %-10d %-10d %s" % (q_type, temp, in_p, out_p, reason))
    print("-" * 56)
    print("合计：输入 %d，输出 %d tokens" % (total_in, total_out))
    if PRICE_IN and PRICE_OUT:
        print("本次实验总成本约 %.6f 元（单价：输入 %s / 输出 %s 元每百万）"
              % (total_cost, PRICE_IN, PRICE_OUT))
    else:
        print("想在 .env 里补两行就能自动算钱：")
        print("    INPUT_PRICE_PER_M=你的输入单价")
        print("    OUTPUT_PRICE_PER_M=你的输出单价")
