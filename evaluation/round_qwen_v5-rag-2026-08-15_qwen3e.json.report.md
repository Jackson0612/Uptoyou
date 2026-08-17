# Evaluation round — qwen

- **candidate**: `qwen`
- **model**: `qwen2.5:3b-instruct-q4_K_M`
- **prompt version**: `v5-rag-2026-08-15`
- **retrieval (D88)**: `qwen3-embedding:0.6b`, k=5
- **started / finished**: 2026-08-17T07:37:43+00:00 → 2026-08-17T08:57:57+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |       7 |    21.2% |
| brand 品牌      |  40 |      14 |    35.0% |
| registered 登記 | 127 |      88 |    69.3% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     109 |    54.5% |
| of which 無效 | 200 |       2 |     1.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       3 |    33.3% |
| 飯食     |  7 |       1 |    14.3% |
| 小吃     | 27 |      19 |    70.4% |
| 火鍋     |  3 |       2 |    66.7% |
| 燒烤     |  5 |       4 |    80.0% |
| 日式     |  4 |       2 |    50.0% |
| 西式     | 12 |       9 |    75.0% |
| 早餐     |  9 |       4 |    44.4% |
| 咖啡飲料 | 21 |      14 |    66.7% |
| 其他     | 57 |       8 |    14.0% |
| 法人     | 46 |      43 |    93.5% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    3 |      |    2 |      |      |      |      |    1 |        1 |    1 |    1 |      |
| 飯食             |      |    1 |    1 |    2 |      |    1 |      |      |          |    1 |      |    1 |
| 小吃             |      |      |   19 |      |    1 |    1 |      |      |          |    5 |    1 |      |
| 火鍋             |      |      |    1 |    2 |      |      |      |      |          |      |      |      |
| 燒烤             |      |      |      |    1 |    4 |      |      |      |          |      |      |      |
| 日式             |      |      |    1 |      |      |    2 |    1 |      |          |      |      |      |
| 西式             |      |      |      |      |      |      |    9 |    1 |          |      |    2 |      |
| 早餐             |      |      |    1 |      |      |      |    2 |    4 |          |    2 |      |      |
| 咖啡飲料         |      |      |      |    1 |      |      |      |      |       14 |    3 |    3 |      |
| 其他             |      |    2 |   12 |    2 |      |      |    1 |    2 |        1 |    8 |   28 |    1 |
| 法人             |      |      |    1 |      |    1 |      |      |      |          |    1 |   43 |      |

