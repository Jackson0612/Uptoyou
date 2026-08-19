# Evaluation round — knn-vote

- **candidate**: `knn-vote`
- **model**: `none — majority vote of the k nearest labelled names`
- **prompt version**: `knn-vote_arctic_k3`
- **retrieval (D88)**: `snowflake-arctic-embed2`, k=3
- **started / finished**: 2026-08-19T12:51:03+00:00 → 2026-08-19T12:52:24+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |      12 |    36.4% |
| brand 品牌      |  40 |      24 |    60.0% |
| registered 登記 | 127 |      74 |    58.3% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     110 |    55.0% |
| of which 無效 | 200 |       0 |     0.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       0 |     0.0% |
| 飯食     |  7 |       0 |     0.0% |
| 小吃     | 27 |      25 |    92.6% |
| 火鍋     |  3 |       0 |     0.0% |
| 燒烤     |  5 |       1 |    20.0% |
| 日式     |  4 |       1 |    25.0% |
| 西式     | 12 |       5 |    41.7% |
| 早餐     |  9 |       4 |    44.4% |
| 咖啡飲料 | 21 |       6 |    28.6% |
| 其他     | 57 |      33 |    57.9% |
| 法人     | 46 |      35 |    76.1% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |      |      |    4 |      |      |      |      |      |        2 |    1 |    2 |      |
| 飯食             |      |      |    5 |      |      |      |      |      |          |    1 |    1 |      |
| 小吃             |      |      |   25 |      |      |    1 |      |      |          |    1 |      |      |
| 火鍋             |    1 |      |    1 |      |      |      |      |      |          |    1 |      |      |
| 燒烤             |      |      |    1 |      |    1 |    1 |      |      |        1 |      |    1 |      |
| 日式             |      |      |    1 |      |      |    1 |      |    1 |          |      |    1 |      |
| 西式             |    1 |      |    1 |      |      |      |    5 |      |          |    2 |    3 |      |
| 早餐             |    1 |    1 |      |      |      |      |    1 |    4 |          |    1 |    1 |      |
| 咖啡飲料         |    2 |      |      |      |      |    2 |      |    3 |        6 |    5 |    3 |      |
| 其他             |      |    1 |   10 |      |      |      |    1 |    1 |        4 |   33 |    7 |      |
| 法人             |    2 |      |    1 |      |    1 |      |    1 |    1 |        1 |    4 |   35 |      |

