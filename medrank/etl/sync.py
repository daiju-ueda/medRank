import subprocess

from medrank import config

S3_SRC = "s3://openalex/data/parquet/authors/"


def latest_partition_glob() -> str:
    return str(config.SNAPSHOT_DIR / "updated_date=*" / "*.parquet")


def sync_snapshot(dry_run: bool = False) -> str:
    config.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    # --delete: OpenAlex は再パーティション時に古い updated_date を消すため、
    # ローカルにも反映しないと翌月以降に重複著者が混入する
    cmd = ["aws", "s3", "sync", "--delete", "--no-sign-request", S3_SRC, str(config.SNAPSHOT_DIR)]
    cmd_str = " ".join(cmd)
    if dry_run:
        return cmd_str
    subprocess.run(cmd, check=True)
    return cmd_str
