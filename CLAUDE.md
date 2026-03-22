# CLAUDE.md — Project Conventions

## Stack

- **Python 3.10+**, FastAPI, Pydantic v2, Uvicorn
- **Inference**: Ultralytics YOLO (detection) + MMSeg (segmentation)
- **Storage backend**: Redis Streams + consumer groups (fallback: in-memory)
- **Metrics**: Prometheus text format (no external library)

## Commands

```bash
# Run server
python main.py --host 0.0.0.0 --port 8011 [--workers 1]

# Run tests
pytest                        # all tests
pytest tests/test_metrics.py  # single file

# Lint / format
ruff check app tests scripts
ruff format app tests scripts
```

## Key Conventions

### Pydantic v2
- Use `model_dump()` (not `.dict()`)
- Use `model_dump_json()` (not `.json()`)
- Use `model_config = ConfigDict(...)` (not inner `Config` class)
- Use `model_validate()` (not `.parse_obj()`)

### Dependency Injection
- Routes use `Depends(_get_service)` / `Depends(_get_store)` etc. — **not** direct `get_runtime()` calls
- Override in tests via `app.dependency_overrides[_get_service] = lambda: fake_service`
- `reset_runtime()` in `app/alerting/__init__.py` is available for test teardown

### Testing
- Shared fakes live in `tests/conftest.py`: `DummyUpload`, `jpeg_bytes()`, `make_fake_pipeline()`, `make_test_service()`, `FakeWorker`, `FakeStore`
- Test classes use `unittest.TestCase` with `@unittest.skipUnless(_runtime_ready(), ...)` guards
- Avoid inline duplicate stubs — import from conftest

### Redis Store
- All multi-command Redis operations use `pipeline(transaction=False)` to batch round-trips
- Consumer group: `XREADGROUP` for new messages, `XAUTOCLAIM` for stale PEL entries
- `confirm_results()` does `XACK + XDEL + HDEL` in one pipeline

### Logging
- Import `from app.common.logging import logger`
- Use `%` style: `logger.info("msg key=%s", value)` — avoid f-strings in log calls
- Set `ALERT_LOG_FORMAT=json` for structured logging in production

### Metrics
- `metrics.observe_inference(stage, duration_seconds)` — call after each pipeline stage
- Stages: `"detection"`, `"segmentation"`, `"postprocess"`, `"total"`

### Error Handling
- Raise `AlertingError(message=..., code=ErrorCode.XYZ)` for business errors
- Raise `ApiError(status_code=..., message=...)` for HTTP-level validation errors
- Use `ErrorCode` enum (in `app/common/errors.py`) instead of raw integer codes

### Image Processing
- Sync path (`analyze_sync`): keep bytes in memory, use `cv2.imdecode(np.frombuffer(...))`
- Async path: write to `upload_root`, run `pipeline.run(file_path, tasks)` from worker
- Magic byte validation is mandatory before any disk write

## File Locations

| Concern | File |
|---------|------|
| App bootstrap / lifespan | `app/application.py` |
| HTTP routes | `app/http/routes.py` |
| Business logic | `app/alerting/service.py` |
| Inference pipeline | `app/alerting/pipeline.py` |
| Queue & result store | `app/alerting/store.py` |
| Background worker | `app/alerting/worker.py` |
| Pydantic schemas | `app/alerting/schemas.py` |
| Settings / config | `app/common/settings.py` |
| Metrics | `app/common/metrics.py` |
| Logging | `app/common/logging.py` |
| Error types | `app/common/errors.py` |
| DI factories | `app/alerting/__init__.py` |

## gitignore

`runtime/` data (models, images, logs, config.json) is excluded from git.
Commit only `runtime/config.example.json` and directory skeleton stubs.
