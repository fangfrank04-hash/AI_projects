package com.ccdc.proposal.controller;

import com.ccdc.proposal.service.HistoryService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/history")
@Slf4j
public class HistoryController {

    @Resource
    private HistoryService historyService;

    @GetMapping("/{userId}")
    public ResponseEntity<List<Map<String, Object>>> getUserHistory(
            @PathVariable String userId,
            @RequestParam(defaultValue = "5") int limit) {
        return ResponseEntity.ok(historyService.getUserHistory(userId, limit));
    }

    @GetMapping("/{userId}/recent")
    public ResponseEntity<List<Map<String, Object>>> getRecentHistory(
            @PathVariable String userId) {
        return ResponseEntity.ok(historyService.getUserHistory(userId, 5));
    }
}
