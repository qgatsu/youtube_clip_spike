## YouTube コメントスパイク解析

### ローカル環境 (AWS 構成を想定したコンテナ)

1. 事前に `.env` を用意し、必要な API キーなどを設定してください。
2. Docker と Docker Compose v2 がインストールされていることを確認します。
3. 下記のコマンドで Redis / Web / Worker の 3 サービスを起動します。

```bash
docker compose up --build
```

| サービス | 役割 | AWS での想定 |
| -------- | ---- | ------------ |
| `redis`  | RQ キュー/メタデータを保存。 | Amazon ElastiCache (Redis) |
| `web`    | Flask + Gunicorn で API/フロントを提供。 | AWS App Runner / ECS Fargate / Elastic Beanstalk |
| `worker` | RQ Worker として解析ジョブを非同期実行。 | ECS Fargate / EKS / Lambda (Container) |

ブラウザから `http://localhost:5000` にアクセスすると従来通り UI を利用できます。ジョブは Redis キューにエンキューされ、`worker` が処理します。

- Docker イメージ内では `sample/youtube.py` を `chat_downloader` の公式 `youtube.py` に上書きしているため、配信のチャット取得で発生していた解析失敗を回避できます。ローカル環境で直接 Python を実行する場合も、同様に `sample/youtube.py` を site-packages の `chat_downloader/sites/youtube.py` にコピーしてください。

### バックグラウンドジョブ構成

- Redis URL や Queue 名、タイムアウトは `config/settings.yaml` もしくは環境変数 (`REDIS_URL`, `REDIS_QUEUE_NAME`, `REDIS_JOB_TIMEOUT`, `REDIS_RESULT_TTL`) で調整できます。
- 解析ワーカーは `app.worker.run_analysis_job` に実装され、RQ から呼び出されます。処理途中の進捗や結果は Redis 上の Job Meta に保存されるため、スケールアウトした Web/Worker 間で共有が可能です。

### AWS への展開を想定したポイント

- Docker イメージは `Dockerfile` をそのまま Amazon ECR にプッシュし、ECS/App Runner 等から利用できます。
- Redis はマネージドサービス (Amazon ElastiCache) を利用し、`REDIS_URL` を該当エンドポイントに切り替えるだけで構成を移行できます。
- ワーカー数を増やしたい場合は worker サービスを水平スケールさせるだけでジョブ処理能力が向上します。
