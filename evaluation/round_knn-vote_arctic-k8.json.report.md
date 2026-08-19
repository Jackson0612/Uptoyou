# Evaluation round — knn-vote

- **candidate**: `knn-vote`
- **model**: `none — majority vote of the k nearest labelled names`
- **prompt version**: `knn-vote_arctic_k8`
- **retrieval (D88)**: `snowflake-arctic-embed2`, k=8
- **started / finished**: 2026-08-19T12:50:30+00:00 → 2026-08-19T12:51:50+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |      11 |    33.3% |
| brand 品牌      |  40 |      12 |    30.0% |
| registered 登記 | 127 |      76 |    59.8% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |      99 |    49.5% |
| of which 無效 | 200 |       0 |     0.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       0 |     0.0% |
| 飯食     |  7 |       0 |     0.0% |
| 小吃     | 27 |      24 |    88.9% |
| 火鍋     |  3 |       0 |     0.0% |
| 燒烤     |  5 |       0 |     0.0% |
| 日式     |  4 |       0 |     0.0% |
| 西式     | 12 |       4 |    33.3% |
| 早餐     |  9 |       4 |    44.4% |
| 咖啡飲料 | 21 |       7 |    33.3% |
| 其他     | 57 |      19 |    33.3% |
| 法人     | 46 |      41 |    89.1% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |      |      |    4 |      |      |      |      |      |        1 |    3 |    1 |      |
| 飯食             |      |      |    5 |      |      |      |      |      |          |    1 |    1 |      |
| 小吃             |    1 |      |   24 |      |    1 |      |      |      |          |    1 |      |      |
| 火鍋             |      |      |    3 |      |      |      |      |      |          |      |      |      |
| 燒烤             |      |      |    1 |      |      |      |      |      |          |      |    4 |      |
| 日式             |      |      |    3 |      |      |      |      |      |          |      |    1 |      |
| 西式             |      |      |    1 |      |      |      |    4 |    1 |          |    2 |    4 |      |
| 早餐             |    2 |      |      |      |      |    1 |      |    4 |          |    2 |      |      |
| 咖啡飲料         |    1 |      |    3 |      |      |      |      |    1 |        7 |    6 |    3 |      |
| 其他             |    1 |      |   13 |      |      |      |      |      |        3 |   19 |   21 |      |
| 法人             |      |      |    2 |      |      |      |      |      |        1 |    2 |   41 |      |

