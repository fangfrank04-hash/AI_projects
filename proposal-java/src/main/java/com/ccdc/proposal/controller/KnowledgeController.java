package com.ccdc.proposal.controller;

import com.ccdc.proposal.service.KnowledgeService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/knowledge")
@Slf4j
public class KnowledgeController {

    @Resource
    private KnowledgeService knowledgeService;

    /**
     * 获取知识库规则
     */
    @GetMapping("/rules")
    public ResponseEntity<List<Map<String, Object>>> getRules(
            @RequestParam String projectLevel) {
        log.info("查询知识库规则，级别: {}", projectLevel);
        return ResponseEntity.ok(knowledgeService.getAllRules(projectLevel));
    }
}
