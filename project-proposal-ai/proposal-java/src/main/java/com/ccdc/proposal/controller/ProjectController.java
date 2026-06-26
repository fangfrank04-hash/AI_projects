package com.ccdc.proposal.controller;

import com.ccdc.proposal.entity.Project;
import com.ccdc.proposal.entity.TeamMember;
import com.ccdc.proposal.service.HistoryService;
import com.ccdc.proposal.service.ProjectService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/project")
@Slf4j
public class ProjectController {

    @Resource
    private ProjectService projectService;

    @Resource
    private HistoryService historyService;

    /**
     * 获取项目基本信息
     */
    @GetMapping("/{projectId}")
    public ResponseEntity<Project> getProject(@PathVariable String projectId) {
        return ResponseEntity.ok(projectService.getProject(projectId));
    }

    /**
     * 获取项目团队信息
     */
    @GetMapping("/{projectId}/team")
    public ResponseEntity<List<TeamMember>> getTeam(@PathVariable String projectId) {
        return ResponseEntity.ok(projectService.getTeamMembers(projectId));
    }

    /**
     * 获取用户历史方案书列表
     */
    @GetMapping("/history")
    public ResponseEntity<List<Map<String, Object>>> getHistory(@RequestParam String userId) {
        return ResponseEntity.ok(historyService.getUserHistory(userId, 5));
    }
}
