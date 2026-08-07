# 固定后方 45 度机位测试集设计

## 目标

把组长指定的固定后方约 45 度机位照片保存为可重复运行的独立测试集，用来记录当前代码在原部署机位下的表现。

## 范围

- 保存当前收到的 7 张原始 JPG，不裁剪、不增强、不改画质。
- 为每张照片记录人工确认的预期业务大类和动作说明。
- 使用现有严格答案加载器和验证脚本运行。
- 报告写入独立目录，不覆盖 305 张主测试报告。
- 不把照片加入 `assets/test_images/test_answers.csv`。
- 不修改 MediaPipe 模型、识别规则或阈值。

## 目录

```text
assets/test_images/fixed_rear_45deg/
  images/
  test_answers.csv

reports/fixed_rear_45deg/
  detection_report.md
  detection_results.csv
```

图片使用稳定、可读的文件名，不保留临时剪贴板随机名称。答案表沿用主测试的字段格式，但 `source_set` 固定为 `fixed_rear_45deg`，`split` 固定为 `field_check`。

## 标准答案

按照用户逐张提供的顺序记录：

1. 正常考试 -> 正常考试
2. 转头 -> 视线偏移
3. 转头加转身 -> 视线偏移
4. 起身站起来 -> 离开座位
5. 伸展胳膊 -> 伸胳膊
6. 伸展胳膊 -> 伸胳膊
7. 正常考试 -> 正常考试

## 验证脚本兼容性

现有 `verify_actions_v2.py` 已支持 `--answers` 和 `--output-dir`，但生成报告时标题仍引用默认主答案表。修正该通用报告参数传递，使报告写出实际使用的答案表路径。该修改只影响报告说明文字，不改变识别结果。

## 验收

- 独立答案表能通过现有严格校验，恰好加载 7 张照片。
- 运行独立测试不会改写 `reports/detection_report.md` 和 `reports/detection_results.csv`。
- 独立报告明确显示 `assets/test_images/fixed_rear_45deg/test_answers.csv`。
- 当前识别结果作为原始基线保存，不因不理想而修改答案或规则。
- 305 张主答案表行数和内容保持不变。
