# 调用链说明

[中文](CALL_CHAIN.md) | [English](CALL_CHAIN.en.md)

## 1. 服务启动链
1. 根目录 `main.py` 执行 `uvicorn.run("app.main:app")`。
2. `app/main.py` 调用 `app.application.create_app()` 构建 FastAPI。
3. `create_app()` 注册 `app/http/routes.py` 路由。
4. `lifespan` 启动时调用 `alerting.get_runtime()` 并启动 `AlertWorker`。

## 2. 同步接口调用链（/analysis/danger）
1. `app/http/routes.py::analysis_danger`
2. `AlertService.analyze_sync`
3. `AlertPipeline.run`
4. `YoloDetector.predict_boxes` + `MmsegSegmentor.predict_mask`
5. 后处理按配置类别生成 `near_segment/enter_segment`
6. 返回任务结果

## 3. 异步接口调用链（/jobs/upload）
1. `app/http/routes.py::upload`
2. `AlertService.submit_async`
3. `AlertStore.enqueue` 写入队列与 pending
4. `AlertWorker._loop` 消费队列
5. `AlertService.process_async_task`
6. `AlertStore.save_result` 写入结果
7. `GET /jobs/alarm_result` 通过 `AlertService.get_alarm_result` 拉取 `items`
8. `POST /jobs/result_confirm` 通过 `AlertService.confirm_result` 删除已确认项
