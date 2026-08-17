# Evaluation round — qwen

- **candidate**: `qwen`
- **model**: `qwen2.5:3b-instruct-q4_K_M`
- **prompt version**: `v5-rag-2026-08-15`
- **retrieval (D88)**: `snowflake-arctic-embed2`, k=5
- **started / finished**: 2026-08-17T10:48:04+00:00 → 2026-08-17T11:46:36+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |       6 |    18.2% |
| brand 品牌      |  40 |      13 |    32.5% |
| registered 登記 | 127 |      82 |    64.6% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     101 |    50.5% |
| of which 無效 | 200 |       3 |     1.5% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       3 |    33.3% |
| 飯食     |  7 |       1 |    14.3% |
| 小吃     | 27 |      15 |    55.6% |
| 火鍋     |  3 |       2 |    66.7% |
| 燒烤     |  5 |       5 |   100.0% |
| 日式     |  4 |       2 |    50.0% |
| 西式     | 12 |       8 |    66.7% |
| 早餐     |  9 |       5 |    55.6% |
| 咖啡飲料 | 21 |      14 |    66.7% |
| 其他     | 57 |       4 |     7.0% |
| 法人     | 46 |      42 |    91.3% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    3 |      |      |      |      |      |    1 |    1 |        1 |      |    3 |      |
| 飯食             |      |    1 |      |    1 |    1 |    1 |    1 |      |          |      |    2 |      |
| 小吃             |      |      |   15 |      |      |    1 |    3 |      |        1 |    4 |    2 |    1 |
| 火鍋             |      |      |    1 |    2 |      |      |      |      |          |      |      |      |
| 燒烤             |      |      |      |      |    5 |      |      |      |          |      |      |      |
| 日式             |      |      |      |      |      |    2 |    1 |      |          |    1 |      |      |
| 西式             |      |      |      |      |      |      |    8 |      |        1 |      |    2 |    1 |
| 早餐             |      |      |    1 |      |      |      |    3 |    5 |          |      |      |      |
| 咖啡飲料         |      |      |      |      |      |      |    1 |      |       14 |    2 |    4 |      |
| 其他             |      |    1 |   15 |    1 |      |      |    2 |    1 |        5 |    4 |   27 |    1 |
| 法人             |    1 |      |    1 |      |    1 |      |      |      |          |    1 |   42 |      |

