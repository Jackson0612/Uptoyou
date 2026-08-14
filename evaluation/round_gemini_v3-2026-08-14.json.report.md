# Evaluation round — gemini

- **candidate**: `gemini`
- **model**: `gemini-3.5-flash-lite`
- **prompt version**: `v3-2026-08-14`
- **started / finished**: 2026-08-14T13:39:44+00:00 → 2026-08-14T13:57:01+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |      21 |    63.6% |
| brand 品牌      |  40 |      16 |    40.0% |
| registered 登記 | 127 |      84 |    66.1% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     121 |    60.5% |
| of which 無效 | 200 |       2 |     1.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       3 |    33.3% |
| 飯食     |  7 |       6 |    85.7% |
| 小吃     | 27 |      18 |    66.7% |
| 火鍋     |  3 |       3 |   100.0% |
| 燒烤     |  5 |       3 |    60.0% |
| 日式     |  4 |       2 |    50.0% |
| 西式     | 12 |       9 |    75.0% |
| 早餐     |  9 |       9 |   100.0% |
| 咖啡飲料 | 21 |      18 |    85.7% |
| 其他     | 57 |      14 |    24.6% |
| 法人     | 46 |      36 |    78.3% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    3 |      |    1 |      |      |    2 |      |      |          |    1 |    1 |    1 |
| 飯食             |      |    6 |      |      |      |      |    1 |      |          |      |      |      |
| 小吃             |      |    1 |   18 |      |    1 |    1 |    2 |      |          |    4 |      |      |
| 火鍋             |      |      |      |    3 |      |      |      |      |          |      |      |      |
| 燒烤             |      |      |    1 |      |    3 |      |      |      |          |      |    1 |      |
| 日式             |      |      |      |      |      |    2 |      |      |          |    1 |    1 |      |
| 西式             |      |      |      |      |      |      |    9 |      |          |      |    3 |      |
| 早餐             |      |      |      |      |      |      |      |    9 |          |      |      |      |
| 咖啡飲料         |      |      |      |      |      |      |      |      |       18 |      |    3 |      |
| 其他             |      |    1 |    4 |    2 |      |      |   10 |    2 |        2 |   14 |   21 |    1 |
| 法人             |    1 |      |    2 |      |    1 |      |      |      |        1 |    5 |   36 |      |

