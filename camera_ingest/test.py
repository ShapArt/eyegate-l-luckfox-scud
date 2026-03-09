from __future__ import annotations

import argparse
import time

from camera_ingest.ingest import CameraIngest, CameraIngestConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Camera ingest probe")
    parser.add_argument("--url", required=True, help="RTSP URL")
    parser.add_argument("--width", type=int, default=960, help="Frame width")
    parser.add_argument("--height", type=int, default=720, help="Frame height")
    parser.add_argument("--transport", default="tcp", help="RTSP transport (tcp/udp)")
    parser.add_argument(
        "--timeout", type=float, default=3.0, help="Probe timeout seconds"
    )
    args = parser.parse_args()

    ingest = CameraIngest(
        CameraIngestConfig(
            url=args.url,
            transport=args.transport,
            width=args.width,
            height=args.height,
            read_timeout_sec=args.timeout,
        )
    )
    ingest.start()
    start = time.time()
    frame = ingest.get_frame(timeout=args.timeout)
    elapsed = time.time() - start
    status = ingest.status()
    ingest.stop()

    if frame is None:
        print(f"[camera_ingest.test] no frame after {elapsed:.2f}s")
        print(f"[camera_ingest.test] error={status.get('error')}")
        return 2
    print(f"[camera_ingest.test] got frame {frame.frame.shape} after {elapsed:.2f}s")
    print(
        f"[camera_ingest.test] fps={status.get('fps'):.1f} last_ts={status.get('last_frame_ts')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
