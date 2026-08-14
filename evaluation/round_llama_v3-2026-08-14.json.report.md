# Evaluation round — llama

- **candidate**: `llama`
- **model**: `llama3.2:3b`
- **prompt version**: `v3-2026-08-14`
- **started / finished**: 2026-08-14T13:18:25+00:00 → 2026-08-14T13:39:25+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |       4 |    12.1% |
| brand 品牌      |  40 |      10 |    25.0% |
| registered 登記 | 127 |      60 |    47.2% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |      74 |    37.0% |
| of which 無效 | 200 |       0 |     0.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       4 |    44.4% |
| 飯食     |  7 |       0 |     0.0% |
| 小吃     | 27 |       6 |    22.2% |
| 火鍋     |  3 |       1 |    33.3% |
| 燒烤     |  5 |       0 |     0.0% |
| 日式     |  4 |       0 |     0.0% |
| 西式     | 12 |       0 |     0.0% |
| 早餐     |  9 |       5 |    55.6% |
| 咖啡飲料 | 21 |       4 |    19.0% |
| 其他     | 57 |      12 |    21.1% |
| 法人     | 46 |      42 |    91.3% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    4 |      |    1 |      |      |      |      |    1 |          |    2 |    1 |      |
| 飯食             |    2 |      |    1 |      |      |    1 |      |      |          |    2 |    1 |      |
| 小吃             |   12 |      |    6 |      |      |      |      |      |          |    8 |    1 |      |
| 火鍋             |    1 |      |    1 |    1 |      |      |      |      |          |      |      |      |
| 燒烤             |    1 |      |      |    1 |      |      |      |      |          |    1 |    2 |      |
| 日式             |    1 |      |    2 |      |      |      |      |      |          |      |    1 |      |
| 西式             |    6 |      |    1 |      |      |      |      |    1 |          |      |    4 |      |
| 早餐             |    1 |      |    2 |      |      |      |      |    5 |          |    1 |      |      |
| 咖啡飲料         |      |      |    1 |      |      |      |      |    3 |        4 |   11 |    2 |      |
| 其他             |    7 |      |    6 |      |      |      |      |   12 |          |   12 |   20 |      |
| 法人             |    2 |      |      |      |      |      |      |      |          |    2 |   42 |      |

