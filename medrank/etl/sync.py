import subprocess

from medrank import config

S3_SRC = "s3://openalex/data/parquet/authors/"


def latest_partition_glob() -> str:
    return str(config.SNAPSHOT_DIR / "updated_date=*" / "*.parquet")


def sync_snapshot(dry_run: bool = False) -> str:
    config.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = ["aws", "s3", "sync", "--no-sign-request", S3_SRC, str(config.SNAPSHOT_DIR)]
    cmd_str = " ".join(cmd)
    if dry_run:
        return cmd_str
    subprocess.run(cmd, check=True)
    return cmd_str
