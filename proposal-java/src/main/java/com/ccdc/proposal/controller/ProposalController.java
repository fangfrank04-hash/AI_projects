package com.ccdc.proposal.controller;

import com.ccdc.proposal.dto.ProposalDTO;
import com.ccdc.proposal.dto.request.ChatRequest;
import com.ccdc.proposal.dto.request.UpdateProposalRequest;
import com.ccdc.proposal.dto.response.ChatResponse;
import com.ccdc.proposal.dto.response.CheckResponse;
import com.ccdc.proposal.dto.response.StepConfirmResult;
import com.ccdc.proposal.dto.response.StepDataResponse;
import com.ccdc.proposal.service.ProjectService;
import com.ccdc.proposal.service.ProposalService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/project")
@Slf4j
public class ProposalController {

    @Resource
    private ProposalService proposalService;

    @Resource
    private ProjectService projectService;

    /**
     * 获取方案书完整数据（已有接口）
     * [MVP] 开启只读事务，确保 Hibernate Session 在序列化时保持打开
     */
    @GetMapping("/{projectId}/proposal")
    @Transactional(readOnly = true)
    public ResponseEntity<ProposalDTO> getProposal(@PathVariable String projectId) {
        ProposalDTO proposal = proposalService.getProposal(projectId);
        return ResponseEntity.ok(proposal);
    }

    /**
     * AI生成指定步骤（新增接口）
     * [MVP] 增加用户身份和权限校验（修复 P0-2）
     */
    @PostMapping("/{projectId}/ai/generate/{step}")
    public ResponseEntity<StepDataResponse> generateStep(
            @PathVariable String projectId,
            @PathVariable int step,
            @RequestBody(required = false) Map<String, Object> params,
            @AuthenticationPrincipal String userId) {  // [MVP] 增加用户身份

        log.info("收到AI生成请求，项目: {}, 步骤: {}, 用户: {}", projectId, step, userId);

        // [MVP] 权限校验前置（修复 P0-2）
        projectService.validateProjectManager(projectId, userId);

        StepDataResponse result = proposalService.generateStep(projectId, step, params != null ? params : Map.of());
        return ResponseEntity.ok(result);
    }

    /**
     * 更新方案书（回填草稿）（已有接口）
     */
    @PutMapping("/{projectId}/proposal")
    public ResponseEntity<StepConfirmResult> updateProposal(
            @PathVariable String projectId,
            @RequestBody UpdateProposalRequest request,
            @AuthenticationPrincipal String userId) {

        StepConfirmResult result = proposalService.confirmStep(
                projectId, request.getStep(), request.getData(), userId);
        return ResponseEntity.ok(result);
    }

    /**
     * AI对话（新增接口）
     * [MVP] 补全实现 + 权限校验（修复 P0-6）
     */
    @PostMapping("/{projectId}/ai/chat")
    public ResponseEntity<ChatResponse> chat(
            @PathVariable String projectId,
            @RequestBody ChatRequest request,
            @AuthenticationPrincipal String userId) {  // [MVP] 增加鉴权

        log.info("收到AI对话请求，项目: {}", projectId);

        // [MVP] 权限校验
        projectService.validateProjectManager(projectId, userId);

        ChatResponse result = proposalService.chat(projectId, request);
        return ResponseEntity.ok(result);
    }

    /**
     * 方案书检查（新增接口）
     * [MVP] 补全实现 + 权限校验（修复 P0-6）
     */
    @PostMapping("/{projectId}/ai/check")
    public ResponseEntity<CheckResponse> checkProposal(
            @PathVariable String projectId,
            @AuthenticationPrincipal String userId) {

        log.info("收到方案书检查请求，项目: {}", projectId);

        // [MVP] 权限校验
        projectService.validateProjectManager(projectId, userId);

        CheckResponse result = proposalService.checkProposal(projectId);
        return ResponseEntity.ok(result);
    }

    /**
     * 确认整个方案书（已有接口）
     */
    @PutMapping("/{projectId}/confirm")
    public ResponseEntity<Void> confirmProposal(
            @PathVariable String projectId,
            @AuthenticationPrincipal String userId) {

        proposalService.confirmProposal(projectId, userId);
        return ResponseEntity.ok().build();
    }
}
