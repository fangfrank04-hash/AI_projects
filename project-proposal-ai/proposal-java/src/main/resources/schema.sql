-- [MVP] 方案书AI系统表结构（JPA自动建表，此文件作为参考）
-- H2 Database Schema

CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    dept VARCHAR(100),
    base_req VARCHAR(50),
    level VARCHAR(10),
    product_no VARCHAR(50),
    product_name VARCHAR(200),
    req_dept VARCHAR(100),
    change_req VARCHAR(50),
    pm_name VARCHAR(50) NOT NULL,
    proposal_background TEXT,
    proposal_scope TEXT,
    status VARCHAR(20) DEFAULT '待确认',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_members (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(50) NOT NULL,
    role VARCHAR(50) NOT NULL,
    name VARCHAR(50) NOT NULL,
    user_id VARCHAR(50),
    nickname VARCHAR(50),
    role_ids TEXT,
    responsibilities TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS proposals (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(50) NOT NULL UNIQUE,
    current_step INT DEFAULT 1,
    completed_steps VARCHAR(50),
    status VARCHAR(20) DEFAULT '待确认',
    confirmed_by VARCHAR(50),
    confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS proposal_steps (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    proposal_id BIGINT NOT NULL,
    step_number INT NOT NULL,
    step_name VARCHAR(50) NOT NULL,
    data TEXT NOT NULL,
    status VARCHAR(20) DEFAULT '草稿',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (proposal_id) REFERENCES proposals(id) ON DELETE CASCADE,
    UNIQUE KEY uk_proposal_step (proposal_id, step_number)
);

CREATE TABLE IF NOT EXISTS knowledge_rules (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_level VARCHAR(10) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,
    rule_content TEXT NOT NULL,
    version VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS history_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    project_id VARCHAR(50) NOT NULL,
    project_name VARCHAR(200),
    project_level VARCHAR(10),
    snapshot TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(50),
    user_id VARCHAR(50) NOT NULL,
    operation VARCHAR(100) NOT NULL,
    details TEXT,
    ip_address VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_program_plans (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(50) NOT NULL,
    task_no VARCHAR(50),
    task_name VARCHAR(200) NOT NULL,
    phase VARCHAR(50),
    required BOOLEAN DEFAULT TRUE,
    cut_result VARCHAR(20),
    cut_result_explain TEXT,
    parent_id BIGINT,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_deliverables (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(50) NOT NULL,
    plan_id BIGINT NOT NULL,
    asset_name VARCHAR(200) NOT NULL,
    asset_type VARCHAR(50),
    required BOOLEAN DEFAULT TRUE,
    cut_result VARCHAR(20),
    cut_result_explain TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES project_program_plans(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS related_projects (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(50) NOT NULL,
    rel_project_id VARCHAR(50) NOT NULL,
    rel_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (rel_project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE KEY uk_project_rel (project_id, rel_project_id)
);

-- [MVP] 补充索引
CREATE INDEX IF NOT EXISTS idx_projects_pm_name ON projects(pm_name);
CREATE INDEX IF NOT EXISTS idx_team_members_project_id ON team_members(project_id);
CREATE INDEX IF NOT EXISTS idx_team_members_name ON team_members(name);
CREATE INDEX IF NOT EXISTS idx_team_members_user_id ON team_members(user_id);
CREATE INDEX IF NOT EXISTS idx_team_members_nickname ON team_members(nickname);
CREATE INDEX IF NOT EXISTS idx_proposals_project_id ON proposals(project_id);
CREATE INDEX IF NOT EXISTS idx_proposals_current_step ON proposals(current_step);
CREATE INDEX IF NOT EXISTS idx_proposal_steps_proposal_id ON proposal_steps(proposal_id);
CREATE INDEX IF NOT EXISTS idx_proposal_steps_status ON proposal_steps(status);
CREATE INDEX IF NOT EXISTS idx_knowledge_rules_level_type ON knowledge_rules(project_level, rule_type);
CREATE INDEX IF NOT EXISTS idx_history_records_user_id ON history_records(user_id);
CREATE INDEX IF NOT EXISTS idx_operation_logs_project_id ON operation_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_operation_logs_user_id ON operation_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_plan_project ON project_program_plans(project_id);
CREATE INDEX IF NOT EXISTS idx_plan_parent ON project_program_plans(parent_id);
CREATE INDEX IF NOT EXISTS idx_plan_sort ON project_program_plans(sort_order);
CREATE INDEX IF NOT EXISTS idx_deliver_project ON project_deliverables(project_id);
CREATE INDEX IF NOT EXISTS idx_deliver_plan ON project_deliverables(plan_id);
CREATE INDEX IF NOT EXISTS idx_rel_project ON related_projects(project_id);
CREATE INDEX IF NOT EXISTS idx_rel_project_id ON related_projects(rel_project_id);
