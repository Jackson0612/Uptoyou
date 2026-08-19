# Evaluation round — knn-vote

- **candidate**: `knn-vote`
- **model**: `none — majority vote of the k nearest labelled names`
- **prompt version**: `knn-vote_arctic_k1`
- **retrieval (D88)**: `snowflake-arctic-embed2`, k=1
- **started / finished**: 2026-08-19T12:50:26+00:00 → 2026-08-19T12:51:03+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |      15 |    45.5% |
| brand 品牌      |  40 |      25 |    62.5% |
| registered 登記 | 127 |      71 |    55.9% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     111 |    55.5% |
| of which 無效 | 200 |       0 |     0.0% |

## Accuracy by gold label

| gold     |  n | correct | accuracy |
|:---------|---:|--------:|---------:|
| 麵食     |  9 |       2 |    22.2% |
| 飯食     |  7 |       0 |     0.0% |
| 小吃     | 27 |      23 |    85.2% |
| 火鍋     |  3 |       0 |     0.0% |
| 燒烤     |  5 |       2 |    40.0% |
| 日式     |  4 |       1 |    25.0% |
| 西式     | 12 |       5 |    41.7% |
| 早餐     |  9 |       4 |    44.4% |
| 咖啡飲料 | 21 |       8 |    38.1% |
| 其他     | 57 |      36 |    63.2% |
| 法人     | 46 |      30 |    65.2% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |    2 |      |    2 |      |      |      |      |      |        2 |    1 |    2 |      |
| 飯食             |      |      |    3 |      |      |      |      |      |          |    2 |    2 |      |
| 小吃             |      |      |   23 |      |      |    1 |      |      |          |    3 |      |      |
| 火鍋             |    1 |      |    1 |      |      |      |      |      |          |    1 |      |      |
| 燒烤             |      |      |    1 |      |    2 |    1 |      |      |        1 |      |      |      |
| 日式             |      |      |    1 |      |      |    1 |      |    1 |          |      |    1 |      |
| 西式             |    1 |      |    1 |      |      |      |    5 |      |        1 |    2 |    2 |      |
| 早餐             |    1 |    1 |    1 |      |      |      |    1 |    4 |          |      |    1 |      |
| 咖啡飲料         |    2 |      |    1 |      |      |    2 |      |    2 |        8 |    3 |    3 |      |
| 其他             |    1 |    1 |    7 |      |      |      |    2 |    1 |        2 |   36 |    7 |      |
| 法人             |    4 |      |    1 |      |    1 |      |    2 |    1 |        2 |    5 |   30 |      |

