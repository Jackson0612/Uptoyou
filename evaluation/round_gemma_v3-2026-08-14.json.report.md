# Evaluation round — gemma

- **candidate**: `gemma`
- **model**: `gemma2:2b`
- **prompt version**: `v3-2026-08-14`
- **started / finished**: 2026-08-14T13:08:02+00:00 → 2026-08-14T13:17:51+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |      10 |    30.3% |
| brand 品牌      |  40 |      10 |    25.0% |
| registered 登記 | 127 |      83 |    65.4% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     103 |    51.5% |
| of which 無效 | 200 |       0 |     0.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       3 |    33.3% |
| 飯食     |  7 |       1 |    14.3% |
| 小吃     | 27 |      18 |    66.7% |
| 火鍋     |  3 |       2 |    66.7% |
| 燒烤     |  5 |       3 |    60.0% |
| 日式     |  4 |       1 |    25.0% |
| 西式     | 12 |       0 |     0.0% |
| 早餐     |  9 |       4 |    44.4% |
| 咖啡飲料 | 21 |      10 |    47.6% |
| 其他     | 57 |      22 |    38.6% |
| 法人     | 46 |      39 |    84.8% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    3 |      |    1 |      |      |    1 |      |      |          |    3 |    1 |      |
| 飯食             |      |    1 |    1 |    1 |      |    1 |      |      |          |    3 |      |      |
| 小吃             |    1 |      |   18 |      |    1 |      |      |      |          |    7 |      |      |
| 火鍋             |      |      |      |    2 |      |    1 |      |      |          |      |      |      |
| 燒烤             |      |      |      |    1 |    3 |      |      |      |          |      |    1 |      |
| 日式             |      |      |      |    1 |    1 |    1 |      |      |          |    1 |      |      |
| 西式             |      |      |    4 |    2 |      |      |      |      |          |    4 |    2 |      |
| 早餐             |      |      |    2 |      |      |      |      |    4 |          |    3 |      |      |
| 咖啡飲料         |      |      |      |      |      |      |      |      |       10 |   10 |    1 |      |
| 其他             |      |      |    6 |    2 |    1 |      |      |    1 |        2 |   22 |   23 |      |
| 法人             |      |      |    1 |    1 |      |      |      |      |          |    5 |   39 |      |

