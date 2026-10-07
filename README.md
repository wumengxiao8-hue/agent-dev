# agent-dev · Day 1

## 一次性准备（在 Anaconda Prompt 里执行）

```
conda create -n agent-dev python=3.11 -y
conda activate agent-dev
python --version
cd /d D:\agent-dev
pip install openai python-dotenv
```

## 每天开始前

```
conda activate agent-dev
cd /d D:\agent-dev
```

## 配置

```
copy .env.example .env
```

然后用记事本或 VS Code 打开 `.env`，填入 API_KEY、BASE_URL、MODEL 三项。

## 运行

```
python day1.py
```

## 常见问题

- 提示 `conda 不是内部或外部命令`：要用「Anaconda Prompt」，不是 PowerShell。
- 提示找不到 `day1.py`：先 `cd /d D:\agent-dev`，再 `dir` 看文件在不在。
- 提示 `.env 里这几项还没填`：文件名必须是 `.env`，不要变成 `.env.txt`。
- `401 / 403`：key 写错或没充值。`Connection error`：BASE_URL 写错或需要代理。
