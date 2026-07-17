"""Publish a single test gesture to AWS IoT Core.

This script is meant for local integration testing after Terraform creates the
IoT Core certificate files and the gesture_recognition/.env file is configured.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
GESTURE_DIR = REPO_ROOT / "gesture_recognition"

sys.path.insert(0, str(GESTURE_DIR))

import run_hands  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish a test gesture to AWS IoT Core.")
    parser.add_argument("--gesture", default="Right_Open_Palm")
    parser.add_argument("--ctname", default="gesture")
    return parser.parse_args()


def normalize_env_path(name: str) -> None:
    value = os.getenv(name)
    if not value:
        return

    path = Path(value)
    if not path.is_absolute():
        path = GESTURE_DIR / path
    os.environ[name] = str(path.resolve())


def main() -> None:
    args = parse_args()
    load_dotenv(GESTURE_DIR / ".env", override=True)
    for name in ("AWS_IOT_CA_PATH", "AWS_IOT_CERT_PATH", "AWS_IOT_KEY_PATH"):
        normalize_env_path(name)

    publisher_args = argparse.Namespace(
        outputMode="aws_iot",
        tasHost=run_hands.DEFAULT_TAS_HOST,
        tasPort=run_hands.DEFAULT_TAS_PORT,
        awsIotEndpoint=run_hands.os.getenv("AWS_IOT_ENDPOINT", ""),
        awsIotPort=int(run_hands.os.getenv("AWS_IOT_PORT", "8883")),
        awsIotTopic=run_hands.os.getenv("AWS_IOT_TOPIC", "evacuation/gesture"),
        awsIotClientId=run_hands.os.getenv("AWS_IOT_CLIENT_ID", "gesture-recognition-client"),
    )

    publisher = run_hands.create_publisher(publisher_args)
    try:
        publisher.publish(args.ctname, args.gesture)
        time.sleep(2)
        print(f"Published gesture: {args.gesture}")
    finally:
        publisher.close()


if __name__ == "__main__":
    main()
