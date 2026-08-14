# Evaluation round — qwen

- **candidate**: `qwen`
- **model**: `qwen2.5:3b-instruct-q4_K_M`
- **prompt version**: `v4-2026-08-14`
- **started / finished**: 2026-08-14T14:03:27+00:00 → 2026-08-14T14:23:36+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |       6 |    18.2% |
| brand 品牌      |  40 |      13 |    32.5% |
| registered 登記 | 127 |      81 |    63.8% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     100 |    50.0% |
| of which 無效 | 200 |       1 |     0.5% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       3 |    33.3% |
| 飯食     |  7 |       1 |    14.3% |
| 小吃     | 27 |      24 |    88.9% |
| 火鍋     |  3 |       2 |    66.7% |
| 燒烤     |  5 |       3 |    60.0% |
| 日式     |  4 |       1 |    25.0% |
| 西式     | 12 |       9 |    75.0% |
| 早餐     |  9 |       4 |    44.4% |
| 咖啡飲料 | 21 |      14 |    66.7% |
| 其他     | 57 |       3 |     5.3% |
| 法人     | 46 |      36 |    78.3% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    3 |      |    5 |      |      |      |      |      |          |      |    1 |      |
| 飯食             |      |    1 |    1 |    1 |      |    1 |    2 |      |          |    1 |      |      |
| 小吃             |      |      |   24 |      |      |      |      |      |        2 |    1 |      |      |
| 火鍋             |      |      |    1 |    2 |      |      |      |      |          |      |      |      |
| 燒烤             |      |      |    1 |    1 |    3 |      |      |      |          |      |      |      |
| 日式             |      |      |    2 |      |      |    1 |    1 |      |          |      |      |      |
| 西式             |      |      |    1 |      |      |      |    9 |      |          |    1 |    1 |      |
| 早餐             |      |      |    4 |      |      |      |    1 |    4 |          |      |      |      |
| 咖啡飲料         |      |      |    4 |      |      |      |      |      |       14 |    1 |    2 |      |
| 其他             |      |      |   20 |      |      |      |    4 |    1 |        3 |    3 |   25 |    1 |
| 法人             |    1 |      |    4 |      |    1 |      |    1 |      |        1 |    2 |   36 |      |

