# Evaluation round — gemma

- **candidate**: `gemma`
- **model**: `gemma2:2b`
- **prompt version**: `v5-rag-2026-08-15`
- **retrieval (D88)**: `bge-m3`, k=5
- **started / finished**: 2026-08-15T04:03:09+00:00 → 2026-08-15T05:40:13+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |      19 |    57.6% |
| brand 品牌      |  40 |      27 |    67.5% |
| registered 登記 | 127 |      76 |    59.8% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     122 |    61.0% |
| of which 無效 | 200 |       4 |     2.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       3 |    33.3% |
| 飯食     |  7 |       1 |    14.3% |
| 小吃     | 27 |      17 |    63.0% |
| 火鍋     |  3 |       2 |    66.7% |
| 燒烤     |  5 |       4 |    80.0% |
| 日式     |  4 |       1 |    25.0% |
| 西式     | 12 |       2 |    16.7% |
| 早餐     |  9 |       4 |    44.4% |
| 咖啡飲料 | 21 |       8 |    38.1% |
| 其他     | 57 |      49 |    86.0% |
| 法人     | 46 |      31 |    67.4% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    3 |      |    1 |      |      |    1 |      |      |          |    3 |    1 |      |
| 飯食             |      |    1 |    1 |      |      |    1 |      |      |          |    4 |      |      |
| 小吃             |      |      |   17 |      |    1 |      |      |      |          |    9 |      |      |
| 火鍋             |      |      |      |    2 |      |    1 |      |      |          |      |      |      |
| 燒烤             |      |      |      |      |    4 |      |      |      |          |    1 |      |      |
| 日式             |      |    1 |      |    1 |      |    1 |      |      |          |      |    1 |      |
| 西式             |      |      |      |      |      |      |    2 |      |          |    4 |    2 |    4 |
| 早餐             |      |      |    1 |      |      |      |    1 |    4 |          |    3 |      |      |
| 咖啡飲料         |      |      |      |      |      |      |      |      |        8 |   13 |      |      |
| 其他             |      |    1 |    2 |    1 |      |      |      |      |          |   49 |    4 |      |
| 法人             |    1 |      |      |      |    1 |      |      |      |          |   13 |   31 |      |

