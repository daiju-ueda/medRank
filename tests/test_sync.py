from medrank.etl import sync
from medrank import config


def test_glob_points_at_snapshot():
    g = sync.latest_partition_glob()
    assert str(config.SNAPSHOT_DIR) in g
    assert g.endswith(".parquet")


def test_dry_run_builds_aws_command():
    cmd = sync.sync_snapshot(dry_run=True)
    assert "aws s3 sync" in cmd
    assert "--no-sign-request" in cmd
    assert "s3://openalex/data/parquet/authors/" in cmd
