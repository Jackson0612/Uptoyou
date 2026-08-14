# Evaluation round — gemma

- **candidate**: `gemma`
- **model**: `gemma2:2b`
- **prompt version**: `v4-2026-08-14`
- **started / finished**: 2026-08-14T14:23:36+00:00 → 2026-08-14T14:33:52+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |       8 |    24.2% |
| brand 品牌      |  40 |      14 |    35.0% |
| registered 登記 | 127 |      77 |    60.6% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |      99 |    49.5% |
| of which 無效 | 200 |       6 |     3.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       3 |    33.3% |
| 飯食     |  7 |       3 |    42.9% |
| 小吃     | 27 |      20 |    74.1% |
| 火鍋     |  3 |       2 |    66.7% |
| 燒烤     |  5 |       4 |    80.0% |
| 日式     |  4 |       1 |    25.0% |
| 西式     | 12 |       0 |     0.0% |
| 早餐     |  9 |       4 |    44.4% |
| 咖啡飲料 | 21 |      11 |    52.4% |
| 其他     | 57 |      19 |    33.3% |
| 法人     | 46 |      32 |    69.6% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    3 |      |    2 |      |      |    1 |      |      |          |    2 |    1 |      |
| 飯食             |      |    3 |    2 |      |      |      |      |      |          |    1 |      |    1 |
| 小吃             |    2 |      |   20 |      |    1 |      |      |      |          |    4 |      |      |
| 火鍋             |      |      |      |    2 |      |    1 |      |      |          |      |      |      |
| 燒烤             |      |      |      |    1 |    4 |      |      |      |          |      |      |      |
| 日式             |      |      |      |    1 |    1 |    1 |      |      |          |    1 |      |      |
| 西式             |      |      |    6 |    1 |      |      |      |      |          |    4 |    1 |      |
| 早餐             |    1 |      |    2 |      |      |      |      |    4 |          |    2 |      |      |
| 咖啡飲料         |      |      |    1 |      |      |      |      |      |       11 |    9 |      |      |
| 其他             |    1 |      |   12 |    1 |      |      |      |    1 |        2 |   19 |   16 |    5 |
| 法人             |    1 |      |    2 |    1 |      |      |      |      |          |   10 |   32 |      |

