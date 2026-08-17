# Evaluation round — gemma

- **candidate**: `gemma`
- **model**: `gemma2:2b`
- **prompt version**: `v5-rag-2026-08-15`
- **retrieval (D88)**: `snowflake-arctic-embed2`, k=5
- **started / finished**: 2026-08-17T10:03:12+00:00 → 2026-08-17T10:48:00+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |      20 |    60.6% |
| brand 品牌      |  40 |      32 |    80.0% |
| registered 登記 | 127 |      80 |    63.0% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     132 |    66.0% |
| of which 無效 | 200 |       1 |     0.5% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       3 |    33.3% |
| 飯食     |  7 |       2 |    28.6% |
| 小吃     | 27 |      16 |    59.3% |
| 火鍋     |  3 |       2 |    66.7% |
| 燒烤     |  5 |       3 |    60.0% |
| 日式     |  4 |       2 |    50.0% |
| 西式     | 12 |       6 |    50.0% |
| 早餐     |  9 |       6 |    66.7% |
| 咖啡飲料 | 21 |      11 |    52.4% |
| 其他     | 57 |      48 |    84.2% |
| 法人     | 46 |      33 |    71.7% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    3 |      |    1 |      |      |    1 |      |      |          |    3 |    1 |      |
| 飯食             |      |    2 |      |      |    1 |      |      |      |          |    4 |      |      |
| 小吃             |    2 |      |   16 |      |    1 |      |      |      |          |    8 |      |      |
| 火鍋             |      |      |      |    2 |      |      |      |      |          |    1 |      |      |
| 燒烤             |      |      |      |    1 |    3 |      |      |      |          |    1 |      |      |
| 日式             |      |      |      |    1 |      |    2 |      |      |          |    1 |      |      |
| 西式             |      |      |      |      |      |      |    6 |      |          |    4 |    2 |      |
| 早餐             |      |      |      |      |      |      |      |    6 |          |    2 |      |    1 |
| 咖啡飲料         |      |      |      |      |      |      |      |      |       11 |    9 |    1 |      |
| 其他             |      |    1 |    1 |    1 |      |      |      |      |        2 |   48 |    4 |      |
| 法人             |      |      |      |    1 |      |      |      |      |          |   12 |   33 |      |

