# Evaluation round — llama

- **candidate**: `llama`
- **model**: `llama3.2:3b`
- **prompt version**: `v4-2026-08-14`
- **started / finished**: 2026-08-14T14:33:52+00:00 → 2026-08-14T14:56:35+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |       9 |    27.3% |
| brand 品牌      |  40 |       7 |    17.5% |
| registered 登記 | 127 |      65 |    51.2% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |      81 |    40.5% |
| of which 無效 | 200 |       0 |     0.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       4 |    44.4% |
| 飯食     |  7 |       1 |    14.3% |
| 小吃     | 27 |       2 |     7.4% |
| 火鍋     |  3 |       2 |    66.7% |
| 燒烤     |  5 |       0 |     0.0% |
| 日式     |  4 |       3 |    75.0% |
| 西式     | 12 |       0 |     0.0% |
| 早餐     |  9 |       4 |    44.4% |
| 咖啡飲料 | 21 |      11 |    52.4% |
| 其他     | 57 |      15 |    26.3% |
| 法人     | 46 |      39 |    84.8% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    4 |      |    1 |      |      |      |      |      |          |    3 |    1 |      |
| 飯食             |    1 |    1 |      |      |      |    1 |      |      |        1 |    3 |      |      |
| 小吃             |    8 |      |    2 |    1 |      |      |      |      |        2 |   14 |      |      |
| 火鍋             |      |      |    1 |    2 |      |      |      |      |          |      |      |      |
| 燒烤             |    1 |      |      |    1 |      |      |      |      |          |    2 |    1 |      |
| 日式             |      |      |      |      |      |    3 |      |      |          |    1 |      |      |
| 西式             |    6 |      |      |      |      |      |      |    1 |          |    3 |    2 |      |
| 早餐             |      |      |    1 |      |      |      |      |    4 |          |    4 |      |      |
| 咖啡飲料         |    1 |      |      |      |      |      |      |      |       11 |    9 |      |      |
| 其他             |    3 |      |    1 |      |      |    1 |      |    7 |        8 |   15 |   22 |      |
| 法人             |      |      |      |      |      |      |      |    1 |        1 |    5 |   39 |      |

