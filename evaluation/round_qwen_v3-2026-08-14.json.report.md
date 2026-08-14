# Evaluation round — qwen

- **candidate**: `qwen`
- **model**: `qwen2.5:3b-instruct-q4_K_M`
- **prompt version**: `v3-2026-08-14`
- **started / finished**: 2026-08-14T11:28:22+00:00 → 2026-08-14T11:46:48+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |       4 |    12.1% |
| brand 品牌      |  40 |      14 |    35.0% |
| registered 登記 | 127 |      84 |    66.1% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     102 |    51.0% |
| of which 無效 | 200 |       5 |     2.5% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       3 |    33.3% |
| 飯食     |  7 |       1 |    14.3% |
| 小吃     | 27 |      22 |    81.5% |
| 火鍋     |  3 |       2 |    66.7% |
| 燒烤     |  5 |       3 |    60.0% |
| 日式     |  4 |       1 |    25.0% |
| 西式     | 12 |       8 |    66.7% |
| 早餐     |  9 |       4 |    44.4% |
| 咖啡飲料 | 21 |      12 |    57.1% |
| 其他     | 57 |       5 |     8.8% |
| 法人     | 46 |      41 |    89.1% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    3 |      |    5 |      |      |      |      |      |          |      |    1 |      |
| 飯食             |      |    1 |    1 |    1 |      |    1 |    2 |      |          |      |    1 |      |
| 小吃             |      |      |   22 |      |      |      |      |      |        3 |    2 |      |      |
| 火鍋             |      |      |    1 |    2 |      |      |      |      |          |      |      |      |
| 燒烤             |      |      |      |    1 |    3 |      |      |      |          |      |    1 |      |
| 日式             |      |      |    2 |      |      |    1 |    1 |      |          |      |      |      |
| 西式             |      |      |      |      |      |      |    8 |      |        1 |      |    2 |    1 |
| 早餐             |      |      |    4 |      |      |      |    1 |    4 |          |      |      |      |
| 咖啡飲料         |      |      |    6 |      |      |      |      |      |       12 |    2 |    1 |      |
| 其他             |      |    1 |   16 |    2 |      |      |      |    1 |        3 |    5 |   25 |    4 |
| 法人             |    1 |      |    3 |      |      |      |      |      |          |    1 |   41 |      |

