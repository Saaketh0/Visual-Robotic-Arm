# Docker Build/Test Container

The Dockerfile is intentionally scoped to build/test/dev parity. It is not the
phase-1 live Jetson camera + serial runtime.

## Build

```bash
docker build -t xarm-ws-dev .
```

## Test

```bash
docker run --rm xarm-ws-dev
```

## Why not live hardware Docker yet?

Live Jetson runtime needs direct access to `/dev/video0` or `/dev/video1`, serial
ports such as `/dev/ttyTHS1`, optional display/GStreamer, and the Jetson GPU stack.
The supported phase-1 path is native runtime first, containerized build/test second.
