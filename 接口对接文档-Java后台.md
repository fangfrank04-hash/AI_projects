# AiProctor 智能监考服务 - 接口对接文档（Java 后台）

> 版本：v1.3.0　｜　更新日期：2026-08-31　｜　所有接口已实测通过
> v1.3.0 变更：新增**重复告警去重机制**（`exception_code=1002`），详见第 6 节，Java 侧需配合改造

***

## 1. 服务地址

| 环境          | 地址                   | 说明                  |
| ----------- | -------------------- | ------------------- |
| 联调（临时）      | `http://{内网IP}:8000` | 部署到测试服务器后提供，以实际通知为准 |
| Swagger 调试页 | `http://{服务地址}/docs` | 可在线查看并调试全部接口        |

**统一约定：**

* 所有响应为 JSON，统一格式 `{code, message, data}`

* **判断成功请以响应体里的** **`code == 200`** **为准**，不要只看 HTTP 状态码
  （业务错误时 HTTP 也可能是 200，但 `code` 为 400/404/413 等）

***

## 2. 核心接口：上传图片识别监考动作

```
POST /upload_face
Content-Type: multipart/form-data
```

### 2.1 请求参数（form-data 表单）

| 参数                | 类型     | 必填 | 说明                       |
| ----------------- | ------ | -- | ------------------------ |
| `file`            | File   | 是  | 考生截图，jpg/png，不超过 10MB    |
| `user_id`         | String | 是  | 考生用户 ID                  |
| `max_left_angle`  | Number | 否  | 左右角 > 该值 → 判定向左看，默认 6    |
| `max_right_angle` | Number | 否  | 左右角 < 该值 → 判定向右看，默认 -6   |
| `max_up_angle`    | Number | 否  | 上下角 > 该值 → 判定向上看，默认 6    |
| `max_down_angle`  | Number | 否  | 上下角 < 该值 → 判定向下看，默认 -0.5 |

> 4 个角度阈值均可选，不传则使用服务端默认值。初期对接只传 `file` + `user_id` 即可。

### 2.2 成功响应（正常行为）

```json
{
  "code": 200,
  "message": "识别成功",
  "data": {
    "warning": false,
    "action_type": "normal",
    "action_label": "正常考试中",
    "warning_count": 0,
    "person_count": 1,
    "user_id": "u_10086",
    "exception_code": null,
    "exception_message": null,
    "notify": false
  }
}
```

### 2.3 成功响应（检测到违规）

```json
{
  "code": 200,
  "message": "识别成功",
  "data": {
    "warning": true,
    "action_type": "phone_call",
    "action_label": "考生疑似打电话",
    "warning_count": 1,
    "person_count": 1,
    "user_id": "u_10086",
    "exception_code": null,
    "exception_message": null,
    "notify": true
  }
}
```

> 注意：违规响应的 `notify=true`（表示本次是新的告警，Java 应记录/提示）。同一违规连续出现超过 3 次后 `notify=false` 且 `exception_code=1002`，详见第 6 节。

### 2.4 data 字段说明

| 字段                  | 类型      | 说明                                           |
| ------------------- | ------- | -------------------------------------------- |
| `warning`           | Boolean | **是否命中违规**（主判断字段）                            |
| `action_type`       | String  | 动作类型（机器可读枚举，见 2.5）                           |
| `action_label`      | String  | 动作的中文描述                                      |
| `warning_count`     | Integer | 该考生累计告警次数                                    |
| `person_count`      | Integer | 检测到的人数                                       |
| `user_id`           | String  | 回显请求中的用户 ID                                  |
| `exception_code`    | Integer | 违规编码：`1001`=黑屏，`1002`=重复告警（见第 6 节），正常为 null  |
| `exception_message` | String  | 违规编码对应的中文描述，正常为 null                         |
| `notify`            | Boolean | **本次是否为新告警**：`true`=需记录/提示；`false`=重复告警，无需再记 |

### 2.5 action\_type 枚举值

| 值              | 含义     |
| -------------- | ------ |
| `normal`       | 正常考试   |
| `gaze_away`    | 视线偏移   |
| `leave_seat`   | 离开座位   |
| `turn_head`    | 转头     |
| `turn_body`    | 转身     |
| `seated_turn`  | 坐姿转身   |
| `phone_call`   | 疑似打电话  |
| `stretch_arm`  | 伸展胳膊   |
| `multi_person` | 多人出现   |
| `black_screen` | 截图几乎全黑 |

### 2.6 错误响应示例

缺少必填字段（HTTP 422）：

```json
{
  "code": 400,
  "message": "请求参数校验失败",
  "data": [{ "type": "missing", "loc": ["body", "user_id"], "msg": "Field required" }]
}
```

图片过大（HTTP 200，业务码 413）：

```json
{ "code": 413, "message": "图片过大（>10MB）", "data": null }
```

### 2.7 错误码一览

| code | 场景                               |
| ---- | -------------------------------- |
| 200  | 识别成功（含识别出违规，违规不是错误）              |
| 400  | 文件类型不支持 / 文件为空 / 图片无法解析 / 参数校验失败 |
| 404  | 内置测试图片缺失（仅 /test 接口）             |
| 413  | 上传文件超过 10MB                      |
| 500  | 服务内部错误                           |

***

## 3. 辅助接口

### 3.1 健康检查（可用于探活）

```
GET /ping
```

```json
{ "pong": true, "message": "server is alive", "pool_ready": true, "pool_size": 2 }
```

> `pool_ready = true` 才表示模型就绪、可正常识别，建议探活时校验该字段。

### 3.2 内置图片测试（联调验证用）

```
GET /test
```

不传参数即可调用，返回格式与 `/upload_face` 的 `data` 结构一致，用于验证服务连通性。

***

## 4. Java 调用示例（Spring RestTemplate）

```java
public String uploadFace(File imageFile, String userId) {
    MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
    body.add("file", new FileSystemResource(imageFile));  // multipart 文件部分
    body.add("user_id", userId);                          // multipart 表单字段

    HttpHeaders headers = new HttpHeaders();
    headers.setContentType(MediaType.MULTIPART_FORM_DATA);

    ResponseEntity<String> resp = restTemplate.postForEntity(
            "http://{HOST}:8000/upload_face",
            new HttpEntity<>(body, headers),
            String.class);

    // 建议：解析 body 后按 code == 200 判断成功，再取 data.warning / data.action_type
    return resp.getBody();
}
```

**Java 侧建议处理逻辑：**

1. `code == 200` → 本次识别成功
2. `data.warning == true` → 考生违规，读取 `action_type` 确定违规类型
3. `data.notify == true` → **新告警，记录/提示**；`notify == false` → 重复告警，**跳过不记**（也可按 `exception_code == 1002` 判断，两者等价）
4. `code != 200` → 请求本身失败，记录日志或重试

***

## 6. 重复告警去重机制（v1.3.0 新增，Java 需配合）

### 6.1 规则

同一考生（`user_id`）**同一种违规连续出现**时：

| 连续次数     | 响应表现                                                            | Java 应该做的         |
| -------- | --------------------------------------------------------------- | ----------------- |
| 第 1\~3 次 | `notify=true`，`exception_code` 为原编码（黑屏=1001，其他违规=null）          | 正常记录报错            |
| 第 4 次及以后 | `notify=false`，`exception_code=1002`，`exception_message="重复告警"` | **不记报错**（静默或仅记日志） |

**计数重置条件**（重新从第 1 次开始报）：

* 该考生出现了**正常画面**（某次截图无违规）

* 该考生切换到**另一种违规类型**（如转头 → 打电话）

> 计数在 Python 服务内存中维护，按 user\_id 隔离，并发请求下计数精确（已做线程安全）。
> 服务重启后计数清零，属预期行为（重启期间本来就该重新告警）。

### 6.2 响应示例：黑屏连续第 4 次

```json
{
  "code": 200,
  "message": "检测到黑屏！",
  "data": {
    "warning": true,
    "action_type": "black_screen",
    "action_label": "检测到黑屏",
    "warning_count": 0,
    "person_count": 1,
    "user_id": "u_10086",
    "exception_code": 1002,
    "exception_message": "重复告警",
    "notify": false
  }
}
```

### 6.3 Java 判断建议（伪代码）

```java
if (data.warning && data.notify) {
    // 新告警：记录报错、推送提示
    saveViolation(userId, data.actionType, data.exceptionCode);
} else if (data.warning) {
    // 重复告警（exception_code=1002）：不记报错
    log.debug("重复告警忽略: userId={}, type={}", userId, data.actionType);
}
```

### 6.4 行为变更说明（相对 v1.2.0）

| 场景       | 旧行为                 | 新行为                                              |
| -------- | ------------------- | ------------------------------------------------ |
| 黑屏       | 同一考生连续黑屏只报第 1 次     | 连续黑屏报前 3 次，之后返回 1002                             |
| 转头/多人等违规 | `notify` 恒为 `false` | 前 3 次 `notify=true`，第 4 次起 `notify=false` + 1002 |
| 正常画面     | —                   | 清空该考生连续计数                                        |

***

## 7. 对接备注

* 请求格式是 `multipart/form-data`（不是 JSON），因为要传输图片文件

* 本文档描述与 `openapi.json`（已一并附上）完全一致，需要机器可读格式或导入 Apifox/Postman 时可用后者

* 服务部署到测试环境后，地址变更会另行通知

