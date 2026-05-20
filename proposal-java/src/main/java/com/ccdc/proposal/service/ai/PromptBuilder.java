package com.ccdc.proposal.service.ai;

import com.ccdc.proposal.dto.ProjectData;
import com.ccdc.proposal.dto.TeamMemberData;
import com.ccdc.proposal.dto.ResourceInput;
import com.ccdc.proposal.entity.Project;
import com.ccdc.proposal.entity.TeamMember;
import com.ccdc.proposal.exception.BusinessException;
import com.ccdc.proposal.repository.ProjectRepository;
import com.ccdc.proposal.repository.TeamMemberRepository;
import com.ccdc.proposal.service.HistoryService;
import com.ccdc.proposal.service.KnowledgeService;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Component
@Slf4j
public class PromptBuilder {

    // [MVP] 改为直接注入 Repository，避免循环依赖（修复 P0-4）
    @Resource
    private ProjectRepository projectRepository;

    @Resource
    private TeamMemberRepository teamMemberRepository;

    @Resource
    private KnowledgeService knowledgeService;

    @Resource
    private HistoryService historyService;

    @Resource
    private ObjectMapper objectMapper;

    public Map<String, Object> buildTeamRequest(String projectId) {
        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new BusinessException("项目不存在"));
        List<TeamMember> members = teamMemberRepository.findByProjectId(projectId);

        Map<String, Object> request = new HashMap<>();
        request.put("project_data", convertProjectData(project));
        request.put("team_data", convertTeamData(members));
        request.put("knowledge_rules", knowledgeService.getRules(project.getLevel(), "team"));
        request.put("history_data", historyService.getUserHistory(project.getPmName(), 5));
        return request;
    }

    public Map<String, Object> buildControlRequest(String projectId) {
        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new BusinessException("项目不存在"));

        Map<String, Object> request = new HashMap<>();
        request.put("project_data", convertProjectData(project));
        request.put("knowledge_rules", knowledgeService.getRules(project.getLevel(), "control"));
        request.put("history_data", historyService.getUserHistory(project.getPmName(), 5));
        return request;
    }

    public Map<String, Object> buildScheduleRequest(String projectId, String approveDate, String projectCycle) {
        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new BusinessException("项目不存在"));

        Map<String, Object> request = new HashMap<>();
        request.put("project_data", convertProjectData(project));
        request.put("approve_date", approveDate);
        request.put("project_cycle", projectCycle);
        request.put("knowledge_rules", knowledgeService.getRules(project.getLevel(), "schedule"));
        return request;
    }

    public Map<String, Object> buildResourceRequest(String projectId, ResourceInput input) {
        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new BusinessException("项目不存在"));
        List<TeamMember> members = teamMemberRepository.findByProjectId(projectId);

        Map<String, Object> request = new HashMap<>();
        request.put("project_data", convertProjectData(project));
        request.put("team_data", convertTeamData(members));
        request.put("input", input);
        request.put("knowledge_rules", knowledgeService.getRules(project.getLevel(), "resource"));
        request.put("history_data", historyService.getUserHistory(project.getPmName(), 5));
        return request;
    }

    public Map<String, Object> buildQualityRequest(String projectId) {
        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new BusinessException("项目不存在"));

        Map<String, Object> request = new HashMap<>();
        request.put("project_data", convertProjectData(project));
        request.put("knowledge_rules", knowledgeService.getRules(project.getLevel(), "quality"));
        request.put("history_data", historyService.getUserHistory(project.getPmName(), 5));
        return request;
    }

    // ==================== 数据转换方法 ====================

    private ProjectData convertProjectData(Project project) {
        ProjectData data = new ProjectData();
        data.setId(project.getId());
        data.setName(project.getName());
        data.setLevel(project.getLevel());
        data.setDept(project.getDept());
        data.setPmName(project.getPmName());
        data.setProductName(project.getProductName());
        data.setReqDept(project.getReqDept());
        return data;
    }

    private List<TeamMemberData> convertTeamData(List<TeamMember> members) {
        return members.stream().map(m -> {
            TeamMemberData data = new TeamMemberData();
            data.setRole(m.getRole());
            data.setName(m.getName());
            data.setResponsibilities(m.getResponsibilities());
            return data;
        }).collect(Collectors.toList());
    }
}
