-- [v2.0] 初始化数据：项目 PJ-202603-S-068

-- 项目基本信息
INSERT INTO projects (id, name, dept, base_req, level, product_no, product_name, req_dept, change_req, pm_name, proposal_background, proposal_scope, status, created_at, updated_at)
SELECT 'PJ-202603-S-068', '验证主表单01221', '信息科技部', 'BD-2026-0078', 'S级', NULL, NULL, '信息科技部', NULL, '陈杰', NULL, NULL, '待确认', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM projects WHERE id = 'PJ-202603-S-068');

-- 团队成员：产品经理（张伟）
INSERT INTO team_members (project_id, role, name, user_id, nickname, role_ids, responsibilities, created_at)
SELECT 'PJ-202603-S-068', '产品经理', '张伟', 'zhangwei', '张伟', '["132969"]', '[{"name":"产品发布","checked":true},{"name":"业务方案可行性分析","checked":true},{"name":"需求评审","checked":true}]', CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM team_members WHERE project_id = 'PJ-202603-S-068' AND user_id = 'zhangwei');

-- 团队成员：项目经理（陈杰）
INSERT INTO team_members (project_id, role, name, user_id, nickname, role_ids, responsibilities, created_at)
SELECT 'PJ-202603-S-068', '项目经理', '陈杰', 'chenjie', '陈杰', '["132969","136823"]', '[{"name":"项目立项","checked":true},{"name":"进度管理","checked":true},{"name":"里程碑节点评审","checked":true}]', CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM team_members WHERE project_id = 'PJ-202603-S-068' AND user_id = 'chenjie');

-- 团队成员：开发负责人（李明）
INSERT INTO team_members (project_id, role, name, user_id, nickname, role_ids, responsibilities, created_at)
SELECT 'PJ-202603-S-068', '开发负责人', '李明', 'liming', '李明', '["136823"]', '[{"name":"技术方案设计","checked":true},{"name":"编码实现","checked":true},{"name":"代码评审","checked":true}]', CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM team_members WHERE project_id = 'PJ-202603-S-068' AND user_id = 'liming');

-- 团队成员：测试负责人（王芳）
INSERT INTO team_members (project_id, role, name, user_id, nickname, role_ids, responsibilities, created_at)
SELECT 'PJ-202603-S-068', '测试负责人', '王芳', 'wangfang', '王芳', '["136823"]', '[{"name":"测试用例设计","checked":true},{"name":"功能测试","checked":true},{"name":"回归测试","checked":true}]', CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM team_members WHERE project_id = 'PJ-202603-S-068' AND user_id = 'wangfang');

-- 团队成员：开发工程师（马伟华）
INSERT INTO team_members (project_id, role, name, user_id, nickname, role_ids, responsibilities, created_at)
SELECT 'PJ-202603-S-068', '开发工程师', '马伟华', 'maweihua', '马伟华', '["136823"]', '[{"name":"编码实现","checked":true},{"name":"代码评审","checked":true},{"name":"技术方案设计","checked":true}]', CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM team_members WHERE project_id = 'PJ-202603-S-068' AND user_id = 'maweihua');

-- 方案书
INSERT INTO proposals (project_id, current_step, completed_steps, status, confirmed_by, confirmed_at, created_at, updated_at)
SELECT 'PJ-202603-S-068', 1, NULL, '待确认', NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM proposals WHERE project_id = 'PJ-202603-S-068');

-- 方案书步骤
INSERT INTO proposal_steps (proposal_id, step_number, step_name, data, status, created_at, updated_at)
SELECT id, 1, '项目团队职责', '{"teamData":[]}', '草稿', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM proposals WHERE project_id = 'PJ-202603-S-068'
AND NOT EXISTS (SELECT 1 FROM proposal_steps ps JOIN proposals p ON ps.proposal_id = p.id WHERE p.project_id = 'PJ-202603-S-068' AND ps.step_number = 1);

INSERT INTO proposal_steps (proposal_id, step_number, step_name, data, status, created_at, updated_at)
SELECT id, 2, '管控方案', '{"controlData":[]}', '草稿', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM proposals WHERE project_id = 'PJ-202603-S-068'
AND NOT EXISTS (SELECT 1 FROM proposal_steps ps JOIN proposals p ON ps.proposal_id = p.id WHERE p.project_id = 'PJ-202603-S-068' AND ps.step_number = 2);

INSERT INTO proposal_steps (proposal_id, step_number, step_name, data, status, created_at, updated_at)
SELECT id, 3, '进度计划', '{"scheduleData":[]}', '草稿', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM proposals WHERE project_id = 'PJ-202603-S-068'
AND NOT EXISTS (SELECT 1 FROM proposal_steps ps JOIN proposals p ON ps.proposal_id = p.id WHERE p.project_id = 'PJ-202603-S-068' AND ps.step_number = 3);

INSERT INTO proposal_steps (proposal_id, step_number, step_name, data, status, created_at, updated_at)
SELECT id, 4, '资源计划', '{"resourceData":{}}', '草稿', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM proposals WHERE project_id = 'PJ-202603-S-068'
AND NOT EXISTS (SELECT 1 FROM proposal_steps ps JOIN proposals p ON ps.proposal_id = p.id WHERE p.project_id = 'PJ-202603-S-068' AND ps.step_number = 4);

INSERT INTO proposal_steps (proposal_id, step_number, step_name, data, status, created_at, updated_at)
SELECT id, 5, '质量保证计划', '{"qualityData":{}}', '草稿', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM proposals WHERE project_id = 'PJ-202603-S-068'
AND NOT EXISTS (SELECT 1 FROM proposal_steps ps JOIN proposals p ON ps.proposal_id = p.id WHERE p.project_id = 'PJ-202603-S-068' AND ps.step_number = 5);

-- 知识库规则：S级
INSERT INTO knowledge_rules (project_level, rule_type, rule_content, version, is_active, created_at)
SELECT 'S级', 'team', '{
  "projectLevel": "S级",
  "minRoles": 4,
  "standardRoles": ["产品经理", "项目经理", "开发负责人", "测试负责人"],
  "mandatoryRoles": ["产品经理", "项目经理", "开发负责人", "测试负责人"],
  "responsibilities": {
    "产品经理": ["产品发布", "业务方案可行性分析", "项目立项", "需求评审"],
    "项目经理": ["项目立项", "进度管理", "里程碑节点评审", "项目结项"],
    "开发负责人": ["技术方案设计", "编码实现", "代码评审"],
    "测试负责人": ["测试用例设计", "功能测试", "回归测试"]
  }
}', '1.0', TRUE, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM knowledge_rules WHERE project_level = 'S级' AND rule_type = 'team');

-- 知识库规则：A级
INSERT INTO knowledge_rules (project_level, rule_type, rule_content, version, is_active, created_at)
SELECT 'A级', 'control', '{
  "projectLevel": "A级",
  "phases": ["需求阶段", "开发阶段", "测试阶段", "项目评审", "结项阶段"],
  "mandatoryPhases": ["开发阶段", "测试阶段"],
  "rules": {
    "裁剪标准": "项目评审、部分测试可裁剪"
  }
}', '1.0', TRUE, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM knowledge_rules WHERE project_level = 'A级' AND rule_type = 'control');

-- 知识库规则：B级
INSERT INTO knowledge_rules (project_level, rule_type, rule_content, version, is_active, created_at)
SELECT 'B级', 'schedule', '{
  "projectLevel": "B级",
  "phases": ["需求阶段", "开发阶段", "测试阶段", "结项阶段"],
  "mandatoryPhases": ["开发阶段"],
  "rules": {
    "裁剪标准": "可裁剪需求评审、项目评审"
  }
}', '1.0', TRUE, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM knowledge_rules WHERE project_level = 'B级' AND rule_type = 'schedule');

-- 知识库规则：C级
INSERT INTO knowledge_rules (project_level, rule_type, rule_content, version, is_active, created_at)
SELECT 'C级', 'resource', '{
  "projectLevel": "C级",
  "phases": ["开发阶段", "测试阶段", "结项阶段"],
  "mandatoryPhases": ["开发阶段"],
  "rules": {
    "裁剪标准": "可大幅裁剪非核心阶段"
  }
}', '1.0', TRUE, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM knowledge_rules WHERE project_level = 'C级' AND rule_type = 'resource');

-- [V3] 阶段活动示例数据
INSERT INTO project_program_plans (project_id, task_no, task_name, phase, required, cut_result, cut_result_explain, parent_id, sort_order, created_at, updated_at)
SELECT 'PJ-202603-S-068', 'T001', '需求分析', '需求阶段', TRUE, '执行', NULL, NULL, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM project_program_plans WHERE project_id = 'PJ-202603-S-068' AND task_no = 'T001');

INSERT INTO project_program_plans (project_id, task_no, task_name, phase, required, cut_result, cut_result_explain, parent_id, sort_order, created_at, updated_at)
SELECT 'PJ-202603-S-068', 'T002', '系统设计', '开发阶段', TRUE, '执行', NULL, NULL, 2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM project_program_plans WHERE project_id = 'PJ-202603-S-068' AND task_no = 'T002');

INSERT INTO project_program_plans (project_id, task_no, task_name, phase, required, cut_result, cut_result_explain, parent_id, sort_order, created_at, updated_at)
SELECT 'PJ-202603-S-068', 'T003', '编码实现', '开发阶段', TRUE, '执行', NULL, NULL, 3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM project_program_plans WHERE project_id = 'PJ-202603-S-068' AND task_no = 'T003');

INSERT INTO project_program_plans (project_id, task_no, task_name, phase, required, cut_result, cut_result_explain, parent_id, sort_order, created_at, updated_at)
SELECT 'PJ-202603-S-068', 'T004', '功能测试', '测试阶段', TRUE, '执行', NULL, NULL, 4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM project_program_plans WHERE project_id = 'PJ-202603-S-068' AND task_no = 'T004');

INSERT INTO project_program_plans (project_id, task_no, task_name, phase, required, cut_result, cut_result_explain, parent_id, sort_order, created_at, updated_at)
SELECT 'PJ-202603-S-068', 'T005', '项目评审', '评审阶段', FALSE, '裁剪', '本项目不涉及外部评审', NULL, 5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM project_program_plans WHERE project_id = 'PJ-202603-S-068' AND task_no = 'T005');

INSERT INTO project_program_plans (project_id, task_no, task_name, phase, required, cut_result, cut_result_explain, parent_id, sort_order, created_at, updated_at)
SELECT 'PJ-202603-S-068', 'T006', '结项归档', '结项阶段', TRUE, '执行', NULL, NULL, 6, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM project_program_plans WHERE project_id = 'PJ-202603-S-068' AND task_no = 'T006');

-- [V3] 交付物示例数据
INSERT INTO project_deliverables (project_id, plan_id, asset_name, asset_type, required, cut_result, cut_result_explain, created_at, updated_at)
SELECT 'PJ-202603-S-068', p.id, '需求规格说明书', '文档', TRUE, '执行', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM project_program_plans p WHERE p.project_id = 'PJ-202603-S-068' AND p.task_no = 'T001'
AND NOT EXISTS (SELECT 1 FROM project_deliverables d WHERE d.project_id = 'PJ-202603-S-068' AND d.asset_name = '需求规格说明书');

INSERT INTO project_deliverables (project_id, plan_id, asset_name, asset_type, required, cut_result, cut_result_explain, created_at, updated_at)
SELECT 'PJ-202603-S-068', p.id, '原型设计稿', '文档', TRUE, '执行', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM project_program_plans p WHERE p.project_id = 'PJ-202603-S-068' AND p.task_no = 'T001'
AND NOT EXISTS (SELECT 1 FROM project_deliverables d WHERE d.project_id = 'PJ-202603-S-068' AND d.asset_name = '原型设计稿');

INSERT INTO project_deliverables (project_id, plan_id, asset_name, asset_type, required, cut_result, cut_result_explain, created_at, updated_at)
SELECT 'PJ-202603-S-068', p.id, '源代码', '代码', TRUE, '执行', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM project_program_plans p WHERE p.project_id = 'PJ-202603-S-068' AND p.task_no = 'T003'
AND NOT EXISTS (SELECT 1 FROM project_deliverables d WHERE d.project_id = 'PJ-202603-S-068' AND d.asset_name = '源代码');

INSERT INTO project_deliverables (project_id, plan_id, asset_name, asset_type, required, cut_result, cut_result_explain, created_at, updated_at)
SELECT 'PJ-202603-S-068', p.id, '测试报告', '文档', TRUE, '执行', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM project_program_plans p WHERE p.project_id = 'PJ-202603-S-068' AND p.task_no = 'T004'
AND NOT EXISTS (SELECT 1 FROM project_deliverables d WHERE d.project_id = 'PJ-202603-S-068' AND d.asset_name = '测试报告');
