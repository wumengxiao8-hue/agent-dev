# -*- coding: utf-8 -*-
"""Agent 开发 · 第 3 天：结构化输出（让模型吐出程序能用的数据）。

今天做三件事：
    A. 定义数据模型，让模型从气象文本里抽取观测记录
    B. 故意让它失败一次，看错误长什么样，再用重试救回来
    C. 把三次调用的 token 和成本记下来

运行：python day3.py
"""
import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError, field_validator, model_validator

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL = os.getenv("MODEL")
PRICE_IN = os.getenv("INPUT_PRICE_PER_M")
PRICE_OUT = os.getenv("OUTPUT_PRICE_PER_M")

if not all([API_KEY, BASE_URL, MODEL]):
    print("[X] .env 还没填全，先补齐 API_KEY / BASE_URL / MODEL。")
    sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

FENCE = chr(96) * 3          # 三个反引号，模型有时会用它把 JSON 包起来


# ------------------------------------------------------- 1. 定义数据结构 ----
class Observation(BaseModel):
    """一条地面气象观测记录。"""

    timestamp: str      # 观测时间，保留原文写法
    location: str       # 站点或地点
    element: str        # 气象要素：气温、相对湿度、风速、降水量、气压……
    value: float        # 数值，只保留数字
    unit: str           # 单位，统一成 °C / % / m/s / mm / hPa，原文没有就空字符串

    @field_validator("unit")
    @classmethod
    def normalize_unit(cls, v: str) -> str:
        """把各种中文写法统一的单位归一化，这是校验器最有用的地方。"""
        table = {
            "摄氏度": "°C", "℃": "°C", "度": "°C", "c": "°C", "°c": "°C",
            "百分比": "%", "百分号": "%",
            "米每秒": "m/s", "m s-1": "m/s", "m·s-1": "m/s",
            "毫米": "mm",
            "百帕": "hPa", "hpa": "hPa",
        }
        key = v.strip()
        return table.get(key, table.get(key.lower(), key))

    @model_validator(mode="after")
    def value_in_element_range(self):
        """跨字段校验：数值必须落在该要素的合理区间里。

        单个字段的范围检查（比如 0 到 100000）几乎没用，因为所有离谱的数
        都能通过。真正有用的是把 value 和 element 放在一起判断。
        """
        ranges = {
            "气温": (-90.0, 60.0),
            "温度": (-90.0, 60.0),
            "相对湿度": (0.0, 100.0),
            "湿度": (0.0, 100.0),
            "风速": (0.0, 120.0),
            "降水": (0.0, 2000.0),
            "雨量": (0.0, 2000.0),
            "气压": (300.0, 1100.0),
        }
        for key, (low, high) in ranges.items():
            if key in self.element and not (low <= self.value <= high):
                raise ValueError(
                    "%s 的数值 %g 不在合理区间 [%g, %g] 内，可能抽错了"
                    % (self.element, self.value, low, high))
        return self


SCHEMA_HINT = (
    "严格按这个 JSON 结构输出，不要解释、不要 markdown 代码块：\n"
    '{"timestamp": "观测时间（保留原文写法）", '
    '"location": "站点或地点", '
    '"element": "气象要素名称", '
    '"value": 数值（只写数字）, '
    '"unit": "单位（统一写成 °C / % / m/s / mm / hPa）"}\n'
    '如果原文没有给出某一项，对应字段填空字符串 ""，绝对不要编造。'
)

SYSTEM = "你是气象资料抽取助手，只输出 JSON。"


def strip_fences(raw: str) -> str:
    """模型有时会把 JSON 包在代码块标记里，先剥掉再解析。"""
    text = raw.strip()
    if text.startswith(FENCE):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith(FENCE):
            text = text.rstrip()[:-3]
    return text.strip()


def call_model(text: str, hint=None):
    """调一次模型，返回 (原始文本, usage)。"""
    user = (hint if hint else SCHEMA_HINT) + "\n\n文本：" + text
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0,
    )
    return (resp.choices[0].message.content or ""), resp.usage


def cost_of(usage):
    if not usage or not PRICE_IN or not PRICE_OUT:
        return None
    try:
        return (usage.prompt_tokens / 1e6 * float(PRICE_IN)
                + usage.completion_tokens / 1e6 * float(PRICE_OUT))
    except ValueError:
        return None


def report(usage):
    c = cost_of(usage)
    reasoning = getattr(usage.completion_tokens_details, "reasoning_tokens", "?")
    print("    token：输入 %s ｜ 输出 %s（其中思考 %s）%s"
          % (usage.prompt_tokens, usage.completion_tokens, reasoning,
             ("｜成本 %.6f 元" % c) if c else ""))
    return c or 0.0


TEXTS = [
    "2026年7月15日08时，南京国家基准气候站观测到气温 35.2 摄氏度。",
    "2026-07-16 14:00，武汉站相对湿度达到 78%，十分钟平均风速 3.4 米每秒。",
    "昨天下午上海浦东出现短时强降水，6 小时累计雨量 62 毫米，同期气压 1002。",
]

total_cost = 0.0


# ------------------------------------------------------ A. 正常抽取流程 ----
print("=" * 60)
print("A · 从三段文本里抽取观测记录")
print("=" * 60)

for i, text in enumerate(TEXTS, start=1):
    print("\n--- 文本 %d ---" % i)
    print("原文：" + text)

    raw, usage = call_model(text)
    total_cost += report(usage)

    try:
        obj = Observation.model_validate_json(strip_fences(raw))
    except (ValidationError, json.JSONDecodeError) as exc:
        print("    [X] 校验失败：" + str(exc)[:150])
        continue

    print("    解析结果：" + obj.model_dump_json(ensure_ascii=False))
    if obj.unit == "":
        print("    注意：unit 是空的 —— 模型遵守了不要编造，这比瞎猜好")


# --------------------------------------------- B. 故意失败 + 重试修复 ----
print("\n" + "=" * 60)
print("B · 故意做一个失败的例子，再用重试救回来")
print("=" * 60)

text = "2026年8月2日20时，广州站测得气压 1002。"
print("原文：" + text)

print("\n第一次：故意用一句很随意的提问，不给结构要求")
raw, usage = call_model(text, hint="帮我看看这段话说了什么。")
total_cost += report(usage)
print("模型返回：" + raw.replace("\n", " ")[:120])

error_hint = None
try:
    Observation.model_validate_json(strip_fences(raw))
    print("    （这次它碰巧输出对了，把 hint 改得再随意一点可以复现失败）")
except (ValidationError, json.JSONDecodeError) as exc:
    print("    [X] 果然没通过校验：" + str(exc)[:120])
    error_hint = (
        "上一次你的输出无法解析成 JSON，报错是：" + str(exc)[:200] + "\n"
        "请重新输出，只输出 JSON 本身。\n" + SCHEMA_HINT
    )

if error_hint:
    print("\n第二次：把错误信息一起喂回去，要求它改正")
    raw2, usage2 = call_model(text, hint=error_hint)
    total_cost += report(usage2)
    try:
        obj = Observation.model_validate_json(strip_fences(raw2))
        print("    [OK] 救回来了：" + obj.model_dump_json(ensure_ascii=False))
    except (ValidationError, json.JSONDecodeError) as exc:
        print("    [X] 还是不行：" + str(exc)[:150])


# ---------------------------------------------------------------- C. 收尾 ----
print("\n" + "=" * 60)
print("C · 今日小结")
print("=" * 60)
if total_cost:
    print("本次实验总成本约 %.6f 元" % total_cost)
else:
    print("（.env 里没填单价，这次没算钱）")
print("\n做完回答我四个问题：")
print("  1. 三段文本各自抽出了什么？有没有抽错的字段？")
print("  2. 第三段缺单位，模型是怎么处理的 —— 填空、瞎猜，还是报错？")
print("  3. 你加的 validator 把哪些单位写法统一了？（可以自己加新写法试）")
print("  4. B 部分那次失败长什么样？把错误信息喂回去之后救回来了吗？")
