# Evaluation round — llama

- **candidate**: `llama`
- **model**: `llama3.2:3b`
- **prompt version**: `v5-rag-2026-08-15`
- **retrieval (D88)**: `qwen3-embedding:0.6b`, k=5
- **started / finished**: 2026-08-17T08:58:01+00:00 → 2026-08-17T10:03:08+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |      13 |    39.4% |
| brand 品牌      |  40 |      11 |    27.5% |
| registered 登記 | 127 |      79 |    62.2% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     103 |    51.5% |
| of which 無效 | 200 |       0 |     0.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       4 |    44.4% |
| 飯食     |  7 |       1 |    14.3% |
| 小吃     | 27 |      20 |    74.1% |
| 火鍋     |  3 |       1 |    33.3% |
| 燒烤     |  5 |       2 |    40.0% |
| 日式     |  4 |       0 |     0.0% |
| 西式     | 12 |       1 |     8.3% |
| 早餐     |  9 |       5 |    55.6% |
| 咖啡飲料 | 21 |       9 |    42.9% |
| 其他     | 57 |      21 |    36.8% |
| 法人     | 46 |      39 |    84.8% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    4 |      |    1 |      |      |      |      |      |        1 |    1 |    2 |      |
| 飯食             |    1 |    1 |    2 |      |      |      |      |      |          |    2 |    1 |      |
| 小吃             |      |    2 |   20 |      |      |      |      |      |          |    3 |    2 |      |
| 火鍋             |      |      |    2 |    1 |      |      |      |      |          |      |      |      |
| 燒烤             |      |      |    1 |    1 |    2 |      |      |      |          |      |    1 |      |
| 日式             |    2 |      |    1 |      |      |      |      |      |          |      |    1 |      |
| 西式             |    5 |      |    1 |      |      |      |    1 |      |          |    1 |    4 |      |
| 早餐             |      |      |    3 |      |      |      |      |    5 |          |    1 |      |      |
| 咖啡飲料         |    1 |      |      |      |      |      |      |      |        9 |    7 |    4 |      |
| 其他             |    9 |    2 |    5 |      |    1 |      |      |      |        1 |   21 |   18 |      |
| 法人             |    1 |      |    2 |      |    1 |      |    1 |      |          |    2 |   39 |      |

