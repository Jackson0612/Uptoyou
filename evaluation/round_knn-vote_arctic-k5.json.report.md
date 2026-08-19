# Evaluation round — knn-vote

- **candidate**: `knn-vote`
- **model**: `none — majority vote of the k nearest labelled names`
- **prompt version**: `knn-vote_arctic_k5`
- **retrieval (D88)**: `snowflake-arctic-embed2`, k=5
- **started / finished**: 2026-08-19T12:49:53+00:00 → 2026-08-19T12:50:30+00:00
- **test set**: `testset_v1.json`
- **test set sha256**: `fd711a7483fd5d8bb894d35c62654219156d1ba144a129649058084d0963b2a0`
- **scored**: 200 rows

Two reports compare only when the sha256 above matches. A refusal or an answer outside D38's list counts as wrong and lands in the `無效` column.

## Accuracy by name layer (D82: this one first)

| layer           |   n | correct | accuracy |
|:----------------|----:|--------:|---------:|
| sign 招牌       |  33 |      12 |    36.4% |
| brand 品牌      |  40 |      11 |    27.5% |
| registered 登記 | 127 |      81 |    63.8% |

## Pooled (second, and never on its own)

| set           |   n | correct | accuracy |
|:--------------|----:|--------:|---------:|
| all layers    | 200 |     104 |    52.0% |
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
| 西式     | 12 |       4 |    33.3% |
| 早餐     |  9 |       4 |    44.4% |
| 咖啡飲料 | 21 |      10 |    47.6% |
| 其他     | 57 |      19 |    33.3% |
| 法人     | 46 |      40 |    87.0% |

## Confusion — gold down, answered across

| gold ＼ answered | 麵食 | 飯食 | 小吃 | 火鍋 | 燒烤 | 日式 | 西式 | 早餐 | 咖啡飲料 | 其他 | 法人 | 無效 |
|:-----------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|---------:|-----:|-----:|-----:|
| 麵食             |      |      |    5 |      |      |      |      |      |        2 |    1 |    1 |      |
| 飯食             |      |      |    5 |      |      |      |      |      |          |    1 |    1 |      |
| 小吃             |      |      |   25 |      |      |    1 |      |      |          |    1 |      |      |
| 火鍋             |      |      |    2 |      |      |      |      |      |          |    1 |      |      |
| 燒烤             |      |      |    1 |      |    1 |      |      |      |        1 |      |    2 |      |
| 日式             |      |      |    2 |      |      |    1 |      |      |          |      |    1 |      |
| 西式             |    1 |      |    1 |      |      |      |    4 |    1 |          |    2 |    3 |      |
| 早餐             |    1 |      |      |      |      |      |    1 |    4 |          |    3 |      |      |
| 咖啡飲料         |      |      |      |      |      |      |    1 |    1 |       10 |    5 |    4 |      |
| 其他             |      |      |   11 |      |      |      |      |    1 |        5 |   19 |   21 |      |
| 法人             |      |      |    3 |      |      |      |      |      |        1 |    2 |   40 |      |

