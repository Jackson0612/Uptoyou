# Evaluation round — llama

- **candidate**: `llama`
- **model**: `llama3.2:3b`
- **prompt version**: `v5-rag-2026-08-15`
- **retrieval (D88)**: `bge-m3`, k=5
- **started / finished**: 2026-08-15T05:40:14+00:00 → 2026-08-15T09:45:37+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |      14 |    42.4% |
| brand 品牌      |  40 |      17 |    42.5% |
| registered 登記 | 127 |      85 |    66.9% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     116 |    58.0% |
| of which 無效 | 200 |       0 |     0.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       5 |    55.6% |
| 飯食     |  7 |       0 |     0.0% |
| 小吃     | 27 |      25 |    92.6% |
| 火鍋     |  3 |       0 |     0.0% |
| 燒烤     |  5 |       3 |    60.0% |
| 日式     |  4 |       1 |    25.0% |
| 西式     | 12 |       5 |    41.7% |
| 早餐     |  9 |       6 |    66.7% |
| 咖啡飲料 | 21 |       9 |    42.9% |
| 其他     | 57 |      23 |    40.4% |
| 法人     | 46 |      39 |    84.8% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    5 |    1 |    1 |      |      |      |      |      |        1 |      |    1 |      |
| 飯食             |    1 |      |    3 |      |      |    1 |      |      |          |    2 |      |      |
| 小吃             |    1 |      |   25 |      |      |      |      |      |          |    1 |      |      |
| 火鍋             |    1 |      |    2 |      |      |      |      |      |          |      |      |      |
| 燒烤             |      |      |    1 |      |    3 |      |      |      |          |    1 |      |      |
| 日式             |      |      |    2 |      |      |    1 |      |      |          |      |    1 |      |
| 西式             |      |      |    1 |      |      |      |    5 |      |          |    3 |    3 |      |
| 早餐             |      |    1 |    2 |      |      |      |      |    6 |          |      |      |      |
| 咖啡飲料         |    1 |      |    1 |      |      |      |      |    1 |        9 |    3 |    6 |      |
| 其他             |    4 |    4 |    7 |      |      |      |      |      |        1 |   23 |   18 |      |
| 法人             |    1 |    1 |    4 |      |      |      |      |      |          |    1 |   39 |      |

