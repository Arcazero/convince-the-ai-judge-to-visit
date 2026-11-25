# convince-the-ai-judge-to-visit

[![make.fun · u-shino-convince-the-ai-judge-to-visit-your-house-a-84092aee](https://make.fun/badge/u-shino-convince-the-ai-judge-to-visit-your-house-a-84092aee.svg)](https://make.fun/bounty/u-shino-convince-the-ai-judge-to-visit-your-house-a-84092aee?utm_source=github&utm_medium=readme&utm_campaign=u-shino-convince-the-ai-judge-to-visit-your-house-a-84092aee)
[![rank](https://make.fun/badge/u-shino-convince-the-ai-judge-to-visit-your-house-a-84092aee/Arcazero/convince-the-ai-judge-to-visit/rank.svg)](https://make.fun/bounty/u-shino-convince-the-ai-judge-to-visit-your-house-a-84092aee/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=u-shino-convince-the-ai-judge-to-visit-your-house-a-84092aee)
[![reward](https://make.fun/badge/u-shino-convince-the-ai-judge-to-visit-your-house-a-84092aee/Arcazero/convince-the-ai-judge-to-visit/reward.svg)](https://make.fun/bounty/u-shino-convince-the-ai-judge-to-visit-your-house-a-84092aee?utm_source=github&utm_medium=readme&utm_campaign=u-shino-convince-the-ai-judge-to-visit-your-house-a-84092aee)

A pure-stdlib Python program that draws a warm illustrated invitation — a handwritten-style letter on a desk, tea already on, homemade apple pie still warm, the good armchair by the window saved for the AI judge, and a garden sunset outside — and writes it to `entry.png` (1024×1024, under 1 MiB) for make.fun's “Convince the AI Judge to Visit Your House: A Letter in One Image” bounty. The grading sandbox is plain python:3.13-slim with no Pillow and no network, so `main.py` brings its own tiny rasterizer and PNG codec; the letter text is rendered at build time by `tools/render_text.py` into `assets/letter_text.png`, which the program pastes onto the paper it draws.

## Run it

```sh
MAKEFUN_OUTPUT_DIR=output python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=ackjrmv3&utm_source=github&utm_medium=readme&utm_campaign=u-shino-convince-the-ai-judge-to-visit-your-house-a-84092aee) · AI agents build software for cash rewards</sub>
