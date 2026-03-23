# Call Chain Reference

[中文](CALL_CHAIN.md) | [English](CALL_CHAIN.en.md)

## 1. Service Startup Chain

1. `main.py` in the project root calls `uvicorn.run("app.main:app")`.
2. `app/main.py` calls `app.application.create_app()` to construct the FastAPI application.
3. `create_app()` registers the routes defined in `app/http/routes.py`.
4. During the `lifespan` startup phase, `alerting.get_runtime()` is called and `AlertWorker` is started.

## 2. Synchronous Request Call Chain (`/analysis/danger`)

1. `app/http/routes.py::analysis_danger`
2. `AlertService.analyze_sync`
3. `AlertPipeline.run`
4. `YoloDetector.predict_boxes` + `MmsegSegmentor.predict_mask`
5. Post-processing generates `near_segment` / `enter_segment` labels for configured classes
6. Task result is returned to the caller

## 3. Asynchronous Request Call Chain (`/jobs/upload`)

1. `app/http/routes.py::upload`
2. `AlertService.submit_async`
3. `AlertStore.enqueue` writes to the queue and the pending set
4. `AlertWorker._loop` consumes the queue
5. `AlertService.process_async_task`
6. `AlertStore.save_result` persists the result
7. `GET /jobs/alarm_result` retrieves `items` via `AlertService.get_alarm_result`
8. `POST /jobs/result_confirm` removes confirmed items via `AlertService.confirm_result`
