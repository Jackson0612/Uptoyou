# Evaluation round — llama

- **candidate**: `llama`
- **model**: `llama3.2:3b`
- **prompt version**: `v5-rag-2026-08-15`
- **retrieval (D88)**: `snowflake-arctic-embed2`, k=5
- **started / finished**: 2026-08-17T11:46:40+00:00 → 2026-08-17T12:54:25+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |      13 |    39.4% |
| brand 品牌      |  40 |      13 |    32.5% |
| registered 登記 | 127 |      86 |    67.7% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     112 |    56.0% |
| of which 無效 | 200 |       0 |     0.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       3 |    33.3% |
| 飯食     |  7 |       1 |    14.3% |
| 小吃     | 27 |      26 |    96.3% |
| 火鍋     |  3 |       1 |    33.3% |
| 燒烤     |  5 |       3 |    60.0% |
| 日式     |  4 |       0 |     0.0% |
| 西式     | 12 |       5 |    41.7% |
| 早餐     |  9 |       5 |    55.6% |
| 咖啡飲料 | 21 |      10 |    47.6% |
| 其他     | 57 |      18 |    31.6% |
| 法人     | 46 |      40 |    87.0% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    3 |      |    4 |      |      |      |      |      |        1 |      |    1 |      |
| 飯食             |    2 |    1 |    1 |      |      |      |      |      |          |    2 |    1 |      |
| 小吃             |      |      |   26 |      |      |      |      |      |          |    1 |      |      |
| 火鍋             |    1 |      |    1 |    1 |      |      |      |      |          |      |      |      |
| 燒烤             |      |      |    2 |      |    3 |      |      |      |          |      |      |      |
| 日式             |      |      |    2 |      |      |      |      |      |          |      |    2 |      |
| 西式             |    1 |      |    1 |      |      |      |    5 |      |          |    2 |    3 |      |
| 早餐             |    2 |      |      |      |      |      |    1 |    5 |          |    1 |      |      |
| 咖啡飲料         |    2 |      |      |      |      |      |      |      |       10 |    5 |    4 |      |
| 其他             |    8 |    1 |   10 |      |      |      |      |    1 |        1 |   18 |   18 |      |
| 法人             |    2 |      |    2 |      |      |      |    1 |      |        1 |      |   40 |      |

