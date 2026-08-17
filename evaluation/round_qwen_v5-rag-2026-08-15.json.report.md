# Evaluation round — qwen

- **candidate**: `qwen`
- **model**: `qwen2.5:3b-instruct-q4_K_M`
- **prompt version**: `v5-rag-2026-08-15`
- **retrieval (D88)**: `bge-m3`, k=5
- **started / finished**: 2026-08-15T00:10:59+00:00 → 2026-08-15T04:03:08+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |       6 |    18.2% |
| brand 品牌      |  40 |      13 |    32.5% |
| registered 登記 | 127 |      78 |    61.4% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |      97 |    48.5% |
| of which 無效 | 200 |       2 |     1.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       2 |    22.2% |
| 飯食     |  7 |       1 |    14.3% |
| 小吃     | 27 |      16 |    59.3% |
| 火鍋     |  3 |       2 |    66.7% |
| 燒烤     |  5 |       4 |    80.0% |
| 日式     |  4 |       2 |    50.0% |
| 西式     | 12 |       9 |    75.0% |
| 早餐     |  9 |       4 |    44.4% |
| 咖啡飲料 | 21 |      13 |    61.9% |
| 其他     | 57 |       4 |     7.0% |
| 法人     | 46 |      40 |    87.0% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    2 |      |    2 |      |      |      |    1 |    1 |          |      |    3 |      |
| 飯食             |      |    1 |      |    2 |      |    1 |      |      |          |      |    2 |    1 |
| 小吃             |      |      |   16 |      |    1 |    1 |      |      |        2 |    6 |      |    1 |
| 火鍋             |      |      |    1 |    2 |      |      |      |      |          |      |      |      |
| 燒烤             |      |      |    1 |      |    4 |      |      |      |          |      |      |      |
| 日式             |      |      |    1 |      |      |    2 |      |      |          |    1 |      |      |
| 西式             |      |      |      |      |      |      |    9 |    1 |          |      |    2 |      |
| 早餐             |      |      |    2 |      |      |      |    2 |    4 |          |    1 |      |      |
| 咖啡飲料         |      |      |    1 |      |      |      |      |      |       13 |    4 |    3 |      |
| 其他             |      |    1 |   14 |    3 |      |      |    2 |    2 |        2 |    4 |   29 |      |
| 法人             |    1 |      |    2 |      |      |      |      |      |          |    3 |   40 |      |

